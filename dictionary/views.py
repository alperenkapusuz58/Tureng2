from collections import defaultdict
import unicodedata

from django.db.models import F, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AdSlot, AdSlotDailyStat, ExampleSentence, Headword, Language, Sense, TrEnLink


def home(request):
    ads = _ad_slots_map(
        [
            AdSlot.SlotKey.HOME_TOP,
            AdSlot.SlotKey.HOME_TOP_MOBILE,
            AdSlot.SlotKey.HOME_BOTTOM,
            AdSlot.SlotKey.HOME_BOTTOM_MOBILE,
        ]
    )
    _increase_ad_impressions(ads)
    return render(request, 'dictionary/home.html', {'ads': ads})


def _normalize_text(value):
    normalized = unicodedata.normalize('NFKD', (value or '').strip().lower())
    stripped = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    translation_table = str.maketrans(
        {
            'ı': 'i',
            'ğ': 'g',
            'ş': 's',
            'ç': 'c',
            'ö': 'o',
            'ü': 'u',
        }
    )
    return stripped.translate(translation_table)


def _query_variants(query):
    base = (query or '').strip()
    if not base:
        return []

    variants = {base, base.lower(), _normalize_text(base)}
    swap_map = str.maketrans({'i': 'ı', 's': 'ş', 'g': 'ğ', 'c': 'ç', 'o': 'ö', 'u': 'ü'})
    variants.add(base.lower().translate(swap_map))
    return [v for v in variants if v]


def _headword_detail_url(direction, item):
    return f"/en-tr/{item.slug}/" if direction == 'en-tr' else f"/tr-en/{item.slug}/"


def _search_headwords(language, query, limit=10):
    variants = _query_variants(query)
    if not variants:
        return []

    qs = Headword.objects.filter(language=language, is_active=True)
    db_q = Q()
    for variant in variants:
        db_q |= Q(lemma__istartswith=variant)
    direct = list(qs.filter(db_q).order_by('lemma')[:limit])

    if len(direct) >= limit:
        return direct

    # Fallback: compare normalized values in Python for keyboard/layout differences.
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return direct

    seen_ids = {item.id for item in direct}
    fallback = []
    for item in qs.order_by('lemma')[:500]:
        if item.id in seen_ids:
            continue
        if _normalize_text(item.lemma).startswith(normalized_query):
            fallback.append(item)
        if len(direct) + len(fallback) >= limit:
            break

    return direct + fallback


def _best_headword_match(language, query):
    candidates = _search_headwords(language, query, limit=20)
    if not candidates:
        return None
    lowered = (query or '').strip().lower()
    for item in candidates:
        if item.lemma.lower() == lowered:
            return item
    return candidates[0]


def _ad_slots_map(keys):
    slots = {
        slot.key: slot
        for slot in AdSlot.objects.filter(key__in=keys, is_active=True)
    }
    return slots


def _increase_ad_impressions(ads_map):
    keys = list(ads_map.keys())
    if not keys:
        return
    AdSlot.objects.filter(key__in=keys, is_active=True).update(impression_count=F('impression_count') + 1)
    _increase_daily_stats(ads_map, event='impression')


def _increase_daily_stats(ads_map, event='impression'):
    day = timezone.localdate()
    for slot in ads_map.values():
        stat, _created = AdSlotDailyStat.objects.get_or_create(
            ad_slot=slot,
            day=day,
            defaults={'impression_count': 0, 'click_count': 0},
        )
        if event == 'click':
            AdSlotDailyStat.objects.filter(pk=stat.pk).update(click_count=F('click_count') + 1)
        else:
            AdSlotDailyStat.objects.filter(pk=stat.pk).update(impression_count=F('impression_count') + 1)


def ad_click(request, key):
    slot = get_object_or_404(AdSlot, key=key, is_active=True)
    AdSlot.objects.filter(pk=slot.pk).update(click_count=F('click_count') + 1)
    _increase_daily_stats({slot.key: slot}, event='click')
    if slot.target_url:
        return redirect(slot.target_url)
    return redirect('/')


def autocomplete(request):
    direction = request.GET.get('direction', 'en-tr')
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': []})

    language = Language.ENGLISH if direction == 'en-tr' else Language.TURKISH
    headwords = _search_headwords(language=language, query=query, limit=10)
    results = [
        {
            'lemma': item.lemma,
            'url': _headword_detail_url(direction, item),
        }
        for item in headwords
    ]

    return JsonResponse({'results': results})


def en_tr_detail(request, slug):
    headword = get_object_or_404(
        Headword.objects.filter(language=Language.ENGLISH, is_active=True),
        slug=slug,
    )
    senses = (
        Sense.objects.filter(headword=headword)
        .prefetch_related(Prefetch('examples', queryset=ExampleSentence.objects.order_by('order_index', 'id')))
        .order_by('part_of_speech', 'order_index', 'id')
    )
    grouped = defaultdict(list)
    for sense in senses:
        grouped[sense.get_part_of_speech_display()].append(sense)

    ads = _ad_slots_map([AdSlot.SlotKey.EN_TR_INLINE, AdSlot.SlotKey.EN_TR_INLINE_MOBILE])
    _increase_ad_impressions(ads)
    return render(
        request,
        'dictionary/en_tr_detail.html',
        {
            'headword': headword,
            'grouped_senses': dict(grouped),
            'ads': ads,
        },
    )


def tr_en_detail(request, slug):
    tr_headword = get_object_or_404(
        Headword.objects.filter(language=Language.TURKISH, is_active=True),
        slug=slug,
    )
    links = (
        TrEnLink.objects.select_related('en_headword')
        .filter(tr_headword=tr_headword, en_headword__is_active=True)
        .order_by('rank', 'en_headword__lemma')
    )
    ads = _ad_slots_map([AdSlot.SlotKey.TR_EN_BOTTOM, AdSlot.SlotKey.TR_EN_BOTTOM_MOBILE])
    _increase_ad_impressions(ads)
    return render(
        request,
        'dictionary/tr_en_detail.html',
        {
            'headword': tr_headword,
            'links': links,
            'ads': ads,
        },
    )


def search_redirect(request):
    direction = request.GET.get('direction', 'en-tr')
    query = request.GET.get('q', '').strip()
    if not query:
        return render(request, 'dictionary/not_found.html', {'query': query, 'suggestions': []})

    if direction == 'en-tr':
        headword = _best_headword_match(language=Language.ENGLISH, query=query)
        if headword:
            return en_tr_detail(request, headword.slug)
    else:
        headword = _best_headword_match(language=Language.TURKISH, query=query)
        if headword:
            return tr_en_detail(request, headword.slug)

    language = Language.ENGLISH if direction == 'en-tr' else Language.TURKISH
    suggestions = _search_headwords(language=language, query=query, limit=5)
    suggestion_items = [
        {
            'lemma': item.lemma,
            'url': _headword_detail_url(direction, item),
        }
        for item in suggestions
    ]
    return render(
        request,
        'dictionary/not_found.html',
        {
            'query': query,
            'suggestions': suggestion_items,
        },
    )
