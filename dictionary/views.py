from collections import defaultdict
import unicodedata

from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import ExampleSentence, Headword, Language, Phrase, Sense, TrEnLink


def home(request):
    return render(request, 'dictionary/home.html')


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
        grouped[sense.part_of_speech].append(sense)

    phrases = Phrase.objects.filter(headword=headword).order_by('order_index', 'id')

    return render(
        request,
        'dictionary/en_tr_detail.html',
        {
            'headword': headword,
            'grouped_senses': dict(grouped),
            'phrases': phrases,
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
    return render(
        request,
        'dictionary/tr_en_detail.html',
        {
            'headword': tr_headword,
            'links': links,
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
