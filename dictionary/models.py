from django.db import models
from django.utils.text import slugify


class Language(models.TextChoices):
    ENGLISH = 'en', 'English'
    TURKISH = 'tr', 'Turkish'


class PartOfSpeech(models.TextChoices):
    NOUN = 'noun', 'İsim'
    VERB = 'verb', 'Fiil'
    ADJECTIVE = 'adj', 'Sıfat'
    ADVERB = 'adv', 'Zarf'
    PRONOUN = 'pron', 'Zamir'
    PREPOSITION = 'prep', 'Edat'
    CONJUNCTION = 'conj', 'Bağlaç'
    INTERJECTION = 'interj', 'Ünlem'
    PHRASE = 'phrase', 'İfade'
    OTHER = 'other', 'Diğer'


class Headword(models.Model):
    language = models.CharField(max_length=2, choices=Language.choices)
    lemma = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180)
    pronunciation_text = models.CharField(max_length=200, blank=True)
    pronunciation_audio_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('language', 'lemma')
        indexes = [
            models.Index(fields=['language', 'lemma']),
            models.Index(fields=['language', 'slug']),
            models.Index(fields=['language', 'is_active']),
        ]
        ordering = ['lemma']

    def __str__(self):
        return f'{self.lemma} ({self.language})'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.lemma)[:160] or 'headword'
            candidate = base_slug
            counter = 1
            while Headword.objects.filter(language=self.language, slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base_slug}-{counter}'
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class Sense(models.Model):
    headword = models.ForeignKey(Headword, on_delete=models.CASCADE, related_name='senses')
    part_of_speech = models.CharField(max_length=10, choices=PartOfSpeech.choices, default=PartOfSpeech.OTHER)
    grammar_code = models.CharField(
        max_length=40,
        blank=True,
        help_text='Gramer kodu, ör: [C/U], [T], [I], [singular/U]',
    )
    definition = models.TextField(
        blank=True,
        help_text='Ingilizce tanim. Rich text desteklenir.',
    )
    translation = models.CharField(max_length=250)
    notes = models.CharField(max_length=255, blank=True)
    order_index = models.PositiveIntegerField(default=1)
    is_primary = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['headword', 'order_index']),
        ]
        ordering = ['order_index', 'id']

    def __str__(self):
        return f'{self.headword.lemma} -> {self.translation}'


class ExampleSentence(models.Model):
    sense = models.ForeignKey(Sense, on_delete=models.CASCADE, related_name='examples')
    sentence_source = models.TextField()
    sentence_target = models.TextField()
    audio_url = models.URLField(blank=True)
    order_index = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=['sense', 'order_index']),
        ]
        ordering = ['order_index', 'id']

    def __str__(self):
        return f'Örnek: {self.sense.headword.lemma}'


class Phrase(models.Model):
    headword = models.ForeignKey(Headword, on_delete=models.CASCADE, related_name='phrases')
    phrase_text = models.CharField(
        max_length=300,
        help_text='Deyim/kalip metni, ör: at/from a distance',
    )
    definition = models.TextField(
        blank=True,
        help_text='Ingilizce tanim. Rich text desteklenir.',
    )
    translation = models.CharField(
        max_length=300,
        blank=True,
        help_text='Turkce karsiligi',
    )
    example_source = models.TextField(blank=True)
    example_target = models.TextField(blank=True)
    order_index = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=['headword', 'order_index']),
        ]
        ordering = ['order_index', 'id']

    def __str__(self):
        return f'{self.headword.lemma}: {self.phrase_text}'


class PosGroupOrder(models.Model):
    headword = models.ForeignKey(Headword, on_delete=models.CASCADE, related_name='pos_group_orders')
    part_of_speech = models.CharField(max_length=10, choices=PartOfSpeech.choices)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('headword', 'part_of_speech')
        ordering = ['order_index', 'id']

    def __str__(self):
        return f'{self.headword.lemma} — {self.get_part_of_speech_display()} (#{self.order_index})'


class TrEnLink(models.Model):
    tr_headword = models.ForeignKey(
        Headword,
        on_delete=models.CASCADE,
        related_name='tr_to_en_links',
        limit_choices_to={'language': Language.TURKISH},
    )
    en_headword = models.ForeignKey(
        Headword,
        on_delete=models.CASCADE,
        related_name='en_from_tr_links',
        limit_choices_to={'language': Language.ENGLISH},
    )
    rank = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('tr_headword', 'en_headword')
        indexes = [
            models.Index(fields=['tr_headword', 'rank']),
        ]
        ordering = ['rank', 'id']

    def __str__(self):
        return f'{self.tr_headword.lemma} -> {self.en_headword.lemma}'


class AdSlot(models.Model):
    class SlotKey(models.TextChoices):
        HOME_TOP = 'home_top', 'Ana Sayfa Ust'
        HOME_TOP_MOBILE = 'home_top_mobile', 'Ana Sayfa Ust (Mobil)'
        HOME_BOTTOM = 'home_bottom', 'Ana Sayfa Alt'
        HOME_BOTTOM_MOBILE = 'home_bottom_mobile', 'Ana Sayfa Alt (Mobil)'
        EN_TR_INLINE = 'en_tr_inline', 'EN-TR Detay Ic'
        EN_TR_INLINE_MOBILE = 'en_tr_inline_mobile', 'EN-TR Detay Ic (Mobil)'
        TR_EN_BOTTOM = 'tr_en_bottom', 'TR-EN Detay Alt'
        TR_EN_BOTTOM_MOBILE = 'tr_en_bottom_mobile', 'TR-EN Detay Alt (Mobil)'

    key = models.CharField(max_length=40, choices=SlotKey.choices, unique=True)
    name = models.CharField(max_length=120)
    ad_code = models.TextField(
        blank=True,
        help_text='Reklam script/html kodu. Bos ise placeholder metni gosterilir.',
    )
    target_url = models.URLField(
        blank=True,
        help_text='Opsiyonel takipli reklam linki. Doluysa "Reklama git" baglantisi gosterilir.',
    )
    placeholder_text = models.CharField(max_length=200, default='Reklam alani')
    is_active = models.BooleanField(default=True)
    impression_count = models.PositiveBigIntegerField(default=0)
    click_count = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.name} ({self.key})'

    @property
    def ctr(self):
        if not self.impression_count:
            return 0.0
        return (self.click_count / self.impression_count) * 100


class AdSlotDailyStat(models.Model):
    ad_slot = models.ForeignKey(AdSlot, on_delete=models.CASCADE, related_name='daily_stats')
    day = models.DateField()
    impression_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('ad_slot', 'day')
        ordering = ['-day', 'ad_slot__key']

    def __str__(self):
        return f'{self.ad_slot.key} - {self.day}'

    @property
    def ctr(self):
        if not self.impression_count:
            return 0.0
        return (self.click_count / self.impression_count) * 100
