import csv
import io

from django import forms
from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.translation import gettext_lazy as tr

from .models import ExampleSentence, Headword, Language, PartOfSpeech, Phrase, Sense, TrEnLink


class SenseInline(admin.StackedInline):
    model = Sense
    extra = 1
    fields = ('part_of_speech', 'grammar_code', 'definition', 'translation', 'notes', 'order_index', 'is_primary')


class PhraseInline(admin.StackedInline):
    model = Phrase
    extra = 0
    fields = ('phrase_text', 'definition', 'translation', 'example_source', 'example_target', 'order_index')


class CsvImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV dosyasi')
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label='Sadece kontrol et (kaydetme)',
    )


@admin.register(Headword)
class HeadwordAdmin(admin.ModelAdmin):
    change_list_template = 'admin/dictionary/headword/change_list.html'
    list_display = ('lemma', 'language', 'is_active', 'updated_at')
    list_filter = ('language', 'is_active')
    search_fields = ('lemma', 'pronunciation_text')
    prepopulated_fields = {'slug': ('lemma',)}
    inlines = [SenseInline, PhraseInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='dictionary_headword_import_csv',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_csv_url'] = 'import-csv/'
        return super().changelist_view(request, extra_context=extra_context)

    @staticmethod
    def _normalize_pos(raw):
        value = (raw or '').strip().lower()
        if not value:
            return PartOfSpeech.OTHER

        direct = {choice for choice, _ in PartOfSpeech.choices}
        if value in direct:
            return value

        aliases = {
            'isim': PartOfSpeech.NOUN,
            'noun': PartOfSpeech.NOUN,
            'fiil': PartOfSpeech.VERB,
            'verb': PartOfSpeech.VERB,
            'sifat': PartOfSpeech.ADJECTIVE,
            'sıfat': PartOfSpeech.ADJECTIVE,
            'adjective': PartOfSpeech.ADJECTIVE,
            'zarf': PartOfSpeech.ADVERB,
            'adverb': PartOfSpeech.ADVERB,
            'zamir': PartOfSpeech.PRONOUN,
            'pronoun': PartOfSpeech.PRONOUN,
            'edat': PartOfSpeech.PREPOSITION,
            'preposition': PartOfSpeech.PREPOSITION,
            'baglac': PartOfSpeech.CONJUNCTION,
            'bağlaç': PartOfSpeech.CONJUNCTION,
            'conjunction': PartOfSpeech.CONJUNCTION,
            'unlem': PartOfSpeech.INTERJECTION,
            'ünlem': PartOfSpeech.INTERJECTION,
            'interjection': PartOfSpeech.INTERJECTION,
            'ifade': PartOfSpeech.PHRASE,
            'phrase': PartOfSpeech.PHRASE,
            'on ek': PartOfSpeech.OTHER,
            'ön ek': PartOfSpeech.OTHER,
            'prefix': PartOfSpeech.OTHER,
        }
        return aliases.get(value, PartOfSpeech.OTHER)

    def import_csv_view(self, request):
        if request.method == 'POST':
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                decoded = form.cleaned_data['csv_file'].read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(decoded))
                rows = list(reader)

                required_cols = {'section'}
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    self.message_user(
                        request,
                        tr('CSV dosyasi en az "section" kolonunu icermelidir.'),
                        level='error',
                    )
                    return redirect('..')

                created_headwords = 0
                created_senses = 0
                created_examples = 0
                created_links = 0

                for idx, row in enumerate(rows, start=2):
                    section = (row.get('section') or '').strip().lower()
                    if not section:
                        continue

                    if section == 'en_tr':
                        en_lemma = (row.get('en_lemma') or '').strip()
                        translation = (row.get('translation') or '').strip()
                        if not en_lemma or not translation:
                            self.message_user(
                                request,
                                tr(f'Satir {idx}: en_tr icin en_lemma ve translation zorunludur.'),
                                level='error',
                            )
                            continue

                        headword, created = Headword.objects.get_or_create(
                            language=Language.ENGLISH,
                            lemma=en_lemma,
                            defaults={
                                'pronunciation_text': (row.get('en_pronunciation') or '').strip(),
                                'pronunciation_audio_url': (row.get('en_audio_url') or '').strip(),
                                'is_active': True,
                            },
                        )
                        if created:
                            created_headwords += 1
                        elif not form.cleaned_data['dry_run']:
                            updated = False
                            new_pron = (row.get('en_pronunciation') or '').strip()
                            new_audio = (row.get('en_audio_url') or '').strip()
                            if new_pron and headword.pronunciation_text != new_pron:
                                headword.pronunciation_text = new_pron
                                updated = True
                            if new_audio and headword.pronunciation_audio_url != new_audio:
                                headword.pronunciation_audio_url = new_audio
                                updated = True
                            if updated:
                                headword.save()

                        if form.cleaned_data['dry_run']:
                            continue

                        sense = Sense.objects.create(
                            headword=headword,
                            part_of_speech=self._normalize_pos(row.get('part_of_speech')),
                            translation=translation,
                            notes=(row.get('notes') or '').strip(),
                            order_index=int((row.get('order_index') or '1').strip() or 1),
                            is_primary=(row.get('is_primary') or '').strip().lower() in ('1', 'true', 'yes', 'evet'),
                        )
                        created_senses += 1

                        example_en = (row.get('example_en') or '').strip()
                        example_tr = (row.get('example_tr') or '').strip()
                        if example_en and example_tr:
                            ExampleSentence.objects.create(
                                sense=sense,
                                sentence_source=example_en,
                                sentence_target=example_tr,
                                audio_url=(row.get('example_audio_url') or '').strip(),
                                order_index=1,
                            )
                            created_examples += 1

                    elif section == 'tr_en':
                        tr_lemma = (row.get('tr_lemma') or '').strip()
                        en_lemma = (row.get('en_lemma') or '').strip()
                        if not tr_lemma or not en_lemma:
                            self.message_user(
                                request,
                                tr(f'Satir {idx}: tr_en icin tr_lemma ve en_lemma zorunludur.'),
                                level='error',
                            )
                            continue

                        tr_headword, tr_created = Headword.objects.get_or_create(
                            language=Language.TURKISH,
                            lemma=tr_lemma,
                            defaults={'is_active': True},
                        )
                        en_headword, en_created = Headword.objects.get_or_create(
                            language=Language.ENGLISH,
                            lemma=en_lemma,
                            defaults={'is_active': True},
                        )
                        if tr_created:
                            created_headwords += 1
                        if en_created:
                            created_headwords += 1

                        if form.cleaned_data['dry_run']:
                            continue

                        _link, created_link = TrEnLink.objects.get_or_create(
                            tr_headword=tr_headword,
                            en_headword=en_headword,
                            defaults={'rank': int((row.get('rank') or '1').strip() or 1)},
                        )
                        if created_link:
                            created_links += 1
                    else:
                        self.message_user(
                            request,
                            tr(f'Satir {idx}: section degeri "en_tr" veya "tr_en" olmali.'),
                            level='error',
                        )

                mode = 'Dry-run tamamlandi' if form.cleaned_data['dry_run'] else 'Import tamamlandi'
                self.message_user(
                    request,
                    tr(
                        f'{mode}: headword={created_headwords}, sense={created_senses}, '
                        f'example={created_examples}, tr_en_link={created_links}'
                    ),
                    level='success',
                )
                return redirect('..')
        else:
            form = CsvImportForm()

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'CSV ile sozluk ice aktar',
            'form': form,
        }
        return render(request, 'admin/dictionary/headword/import_csv.html', context)


@admin.register(Sense)
class SenseAdmin(admin.ModelAdmin):
    list_display = ('headword', 'part_of_speech', 'grammar_code', 'translation', 'order_index', 'is_primary')
    list_filter = ('part_of_speech', 'is_primary', 'headword__language')
    search_fields = ('headword__lemma', 'translation', 'definition', 'notes')
    autocomplete_fields = ('headword',)


class ExampleSentenceAdminForm(forms.ModelForm):
    class Meta:
        model = ExampleSentence
        fields = '__all__'
        widgets = {
            'sentence_source': forms.Textarea(attrs={'rows': 4, 'data-richtext': 'true'}),
            'sentence_target': forms.Textarea(attrs={'rows': 3, 'data-richtext': 'true'}),
        }


@admin.register(ExampleSentence)
class ExampleSentenceAdmin(admin.ModelAdmin):
    form = ExampleSentenceAdminForm
    list_display = ('sense', 'short_source', 'order_index')
    search_fields = ('sense__headword__lemma', 'sentence_source', 'sentence_target')
    autocomplete_fields = ('sense',)

    class Media:
        css = {'all': ('dictionary/admin_richtext.css',)}
        js = ('dictionary/admin_richtext.js',)

    @staticmethod
    def short_source(obj):
        return (obj.sentence_source[:70] + '...') if len(obj.sentence_source) > 70 else obj.sentence_source


@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = ('headword', 'phrase_text', 'translation', 'order_index')
    search_fields = ('headword__lemma', 'phrase_text', 'translation')
    autocomplete_fields = ('headword',)


@admin.register(TrEnLink)
class TrEnLinkAdmin(admin.ModelAdmin):
    list_display = ('tr_headword', 'en_headword', 'rank')
    search_fields = ('tr_headword__lemma', 'en_headword__lemma')
    autocomplete_fields = ('tr_headword', 'en_headword')


