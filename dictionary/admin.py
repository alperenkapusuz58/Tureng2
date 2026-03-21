import csv
import io
from datetime import timedelta

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as tr
from django.utils import timezone

from .models import AdSlot, AdSlotDailyStat, ExampleSentence, Headword, Language, PartOfSpeech, Sense, TrEnLink


class SenseInline(admin.TabularInline):
    model = Sense
    extra = 1


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
    inlines = [SenseInline]

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
    list_display = ('headword', 'part_of_speech', 'translation', 'order_index', 'is_primary')
    list_filter = ('part_of_speech', 'is_primary', 'headword__language')
    search_fields = ('headword__lemma', 'translation', 'notes')
    autocomplete_fields = ('headword',)


@admin.register(ExampleSentence)
class ExampleSentenceAdmin(admin.ModelAdmin):
    list_display = ('sense', 'short_source', 'order_index')
    search_fields = ('sense__headword__lemma', 'sentence_source', 'sentence_target')
    autocomplete_fields = ('sense',)

    @staticmethod
    def short_source(obj):
        return (obj.sentence_source[:70] + '...') if len(obj.sentence_source) > 70 else obj.sentence_source


@admin.register(TrEnLink)
class TrEnLinkAdmin(admin.ModelAdmin):
    list_display = ('tr_headword', 'en_headword', 'rank')
    search_fields = ('tr_headword__lemma', 'en_headword__lemma')
    autocomplete_fields = ('tr_headword', 'en_headword')


class PageGroupFilter(admin.SimpleListFilter):
    title = 'Sayfa Grubu'
    parameter_name = 'page_group'

    def lookups(self, request, model_admin):
        return (
            ('home', 'Home'),
            ('en_tr', 'EN-TR Detail'),
            ('tr_en', 'TR-EN Detail'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'home':
            return queryset.filter(key__startswith='home_')
        if value == 'en_tr':
            return queryset.filter(key__startswith='en_tr_')
        if value == 'tr_en':
            return queryset.filter(key__startswith='tr_en_')
        return queryset


class DeviceGroupFilter(admin.SimpleListFilter):
    title = 'Cihaz Grubu'
    parameter_name = 'device_group'

    def lookups(self, request, model_admin):
        return (
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'mobile':
            return queryset.filter(key__contains='_mobile')
        if value == 'desktop':
            return queryset.exclude(key__contains='_mobile')
        return queryset


class AdSlotAdminForm(forms.ModelForm):
    class Meta:
        model = AdSlot
        fields = '__all__'
        widgets = {
            'ad_code': forms.Textarea(attrs={'rows': 10, 'style': 'font-family: monospace;'}),
        }

    def clean_ad_code(self):
        code = (self.cleaned_data.get('ad_code') or '').strip()
        lowered = code.lower()
        if 'javascript:' in lowered:
            raise ValidationError('ad_code icinde javascript: baglantisi kullanilamaz.')
        if '<script' in lowered and '</script>' not in lowered:
            raise ValidationError('Script etiketi acilip kapanmiyor gibi gorunuyor.')
        if '<iframe' in lowered and '</iframe>' not in lowered:
            raise ValidationError('Iframe etiketi acilip kapanmiyor gibi gorunuyor.')
        return code

    def clean(self):
        cleaned = super().clean()
        is_active = cleaned.get('is_active')
        ad_code = (cleaned.get('ad_code') or '').strip()
        placeholder = (cleaned.get('placeholder_text') or '').strip()
        if is_active and not ad_code and not placeholder:
            raise ValidationError('Aktif bir slotta ad_code veya placeholder_text dolu olmali.')
        return cleaned


@admin.register(AdSlot)
class AdSlotAdmin(admin.ModelAdmin):
    form = AdSlotAdminForm
    list_display = (
        'name',
        'key',
        'page_label',
        'device_label',
        'is_active',
        'impression_count',
        'click_count',
        'ctr_percent',
        'updated_at',
    )
    list_filter = ('is_active', 'key', PageGroupFilter, DeviceGroupFilter)
    search_fields = ('key', 'name')
    readonly_fields = ('ad_preview', 'impression_count', 'click_count', 'ctr_percent')
    fieldsets = (
        (
            'Temel Bilgiler',
            {
                'fields': ('key', 'name', 'is_active'),
            },
        ),
        (
            'Reklam Icerigi',
            {
                'fields': ('ad_code', 'target_url', 'placeholder_text', 'ad_preview'),
                'description': 'ad_code bos ise sayfada placeholder_text gosterilir.',
            },
        ),
        (
            'Takip',
            {
                'fields': ('impression_count', 'click_count', 'ctr_percent'),
            },
        ),
    )

    @admin.display(description='Sayfa')
    def page_label(self, obj):
        key = obj.key or ''
        if key.startswith('home_'):
            return 'Home'
        if key.startswith('en_tr_'):
            return 'EN-TR Detail'
        if key.startswith('tr_en_'):
            return 'TR-EN Detail'
        return 'Other'

    @admin.display(description='Cihaz')
    def device_label(self, obj):
        return 'Mobile' if '_mobile' in (obj.key or '') else 'Desktop'

    @admin.display(description='Onizleme')
    def ad_preview(self, obj):
        if not obj or not obj.pk:
            return 'Kayit sonrasi onizleme gorunur.'
        if obj.ad_code:
            return format_html(
                (
                    '<iframe style="width:100%;height:180px;border:1px solid #ccc;background:#fff;" '
                    'sandbox="allow-scripts allow-popups" srcdoc="{}"></iframe>'
                ),
                obj.ad_code,
            )
        return format_html(
            '<div style="border:1px dashed #999;padding:12px;color:#666;">{}</div>',
            obj.placeholder_text or 'Reklam alani',
        )

    @admin.display(description='CTR')
    def ctr_percent(self, obj):
        return f'{obj.ctr:.2f}%'


@admin.register(AdSlotDailyStat)
class AdSlotDailyStatAdmin(admin.ModelAdmin):
    change_list_template = 'admin/dictionary/adslotdailystat/change_list.html'
    list_display = ('day', 'ad_slot', 'impression_count', 'click_count', 'ctr_percent')
    list_filter = ('day', 'ad_slot__key')
    search_fields = ('ad_slot__key', 'ad_slot__name')
    autocomplete_fields = ('ad_slot',)
    readonly_fields = ('day', 'ad_slot', 'impression_count', 'click_count', 'ctr_percent')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'summary/',
                self.admin_site.admin_view(self.summary_view),
                name='dictionary_adslotdailystat_summary',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['summary_url'] = 'summary/'
        return super().changelist_view(request, extra_context=extra_context)

    def summary_view(self, request):
        today = timezone.localdate()
        from_day = today - timedelta(days=6)
        rows = (
            AdSlotDailyStat.objects.filter(day__gte=from_day, day__lte=today)
            .values('ad_slot__key', 'ad_slot__name')
            .annotate(
                total_impressions=Sum('impression_count'),
                total_clicks=Sum('click_count'),
            )
            .order_by('-total_impressions', 'ad_slot__key')
        )

        summary_rows = []
        total_impressions = 0
        total_clicks = 0
        for row in rows:
            impressions = row['total_impressions'] or 0
            clicks = row['total_clicks'] or 0
            ctr = (clicks / impressions * 100) if impressions else 0
            total_impressions += impressions
            total_clicks += clicks
            summary_rows.append(
                {
                    'key': row['ad_slot__key'],
                    'name': row['ad_slot__name'],
                    'impressions': impressions,
                    'clicks': clicks,
                    'ctr': ctr,
                }
            )

        total_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Reklam Ozeti (Son 7 Gun)',
            'from_day': from_day,
            'to_day': today,
            'rows': summary_rows,
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_ctr': total_ctr,
        }
        return render(request, 'admin/dictionary/adslotdailystat/summary.html', context)

    @admin.display(description='CTR')
    def ctr_percent(self, obj):
        return f'{obj.ctr:.2f}%'
