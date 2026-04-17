from collections import defaultdict
import difflib
import unicodedata

from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import ExampleSentence, Headword, Language, PosGroupOrder, Phrase, Sense, TrEnLink


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


def _fuzzy_headword_suggestions(language, query, limit=6):
    """Return 'did you mean' suggestions using difflib close-match on lemmas.

    Used when prefix search produces no result; catches typos like 'fley' -> 'fly'.
    """
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    lemmas = list(
        Headword.objects.filter(language=language, is_active=True).values_list('id', 'lemma', 'slug')
    )
    if not lemmas:
        return []

    normalized_map = {}
    norm_list = []
    for hw_id, lemma, slug in lemmas:
        norm = _normalize_text(lemma)
        if not norm:
            continue
        normalized_map.setdefault(norm, (hw_id, lemma, slug))
        norm_list.append(norm)

    matches = difflib.get_close_matches(normalized_query, norm_list, n=limit, cutoff=0.6)
    seen = set()
    results = []
    for match in matches:
        entry = normalized_map.get(match)
        if not entry or entry[0] in seen:
            continue
        seen.add(entry[0])
        _hw_id, lemma, slug = entry
        results.append({'lemma': lemma, 'url': f'/en-tr/{slug}/'})
    return results


def _fuzzy_tr_suggestions(query, limit=6):
    """Return 'did you mean' suggestions for TR query by matching against
    unique tr_keywords/translation tokens pulled from Sense rows."""
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    rows = (
        Sense.objects.filter(headword__language=Language.ENGLISH, headword__is_active=True)
        .exclude(tr_keywords='', translation='')
        .values_list('translation', 'tr_keywords', 'headword__lemma', 'headword__slug')
    )

    tokens = {}
    for translation, tr_keywords, lemma, slug in rows:
        raw_terms = []
        for source in (translation or '', tr_keywords or ''):
            for piece in source.replace(';', ',').split(','):
                piece = piece.strip()
                if piece:
                    raw_terms.append(piece)
        for term in raw_terms:
            norm = _normalize_text(term)
            if not norm or len(norm) < 2:
                continue
            tokens.setdefault(norm, {'term': term, 'lemma': lemma, 'slug': slug})

    if not tokens:
        return []

    matches = difflib.get_close_matches(normalized_query, list(tokens.keys()), n=limit * 2, cutoff=0.65)
    seen_lemma = set()
    results = []
    for match in matches:
        entry = tokens[match]
        if entry['lemma'] in seen_lemma:
            continue
        seen_lemma.add(entry['lemma'])
        results.append({
            'lemma': entry['lemma'],
            'term': entry['term'],
            'url': f"/en-tr/{entry['slug']}/",
        })
        if len(results) >= limit:
            break
    return results


def _sample_headwords(language, limit=8):
    """Return a small list of headwords to surface on empty-state pages."""
    qs = (
        Headword.objects.filter(language=language, is_active=True)
        .order_by('-updated_at')[:limit]
    )
    return [{'lemma': hw.lemma, 'url': f'/en-tr/{hw.slug}/'} for hw in qs]



def _search_tr_keywords(query, limit=80):
    """Search Sense.tr_keywords for Turkish query, return flat sense-level rows grouped by POS."""
    variants = _query_variants(query)
    if not variants:
        return []

    db_q = Q()
    for v in variants:
        db_q |= Q(tr_keywords__icontains=v)

    senses = (
        Sense.objects
        .filter(db_q, headword__language=Language.ENGLISH, headword__is_active=True)
        .select_related('headword')
        .order_by('part_of_speech', 'headword__lemma', 'order_index', 'id')[:limit]
    )

    seen = set()
    pos_groups = defaultdict(list)
    for sense in senses:
        key = (sense.headword_id, sense.translation, sense.part_of_speech)
        if key in seen:
            continue
        seen.add(key)
        pos_groups[sense.part_of_speech].append(sense)

    return dict(pos_groups)


def _autocomplete_tr_keywords(query, limit=10):
    """Return autocomplete suggestions for TR-EN by searching tr_keywords."""
    variants = _query_variants(query)
    if not variants:
        return []

    db_q = Q()
    for v in variants:
        db_q |= Q(tr_keywords__icontains=v)

    senses = (
        Sense.objects
        .filter(db_q, headword__language=Language.ENGLISH, headword__is_active=True)
        .select_related('headword')
        .order_by('headword__lemma')[:limit * 3]
    )

    seen = set()
    results = []
    for sense in senses:
        hw = sense.headword
        if hw.id in seen:
            continue
        seen.add(hw.id)
        results.append({
            'lemma': hw.lemma,
            'translation': sense.translation,
            'url': f'/en-tr/{hw.slug}/',
        })
        if len(results) >= limit:
            break
    return results


def autocomplete(request):
    direction = request.GET.get('direction', 'en-tr')
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': []})

    if direction == 'tr-en':
        results = _autocomplete_tr_keywords(query, limit=10)
        return JsonResponse({'results': results})

    headwords = _search_headwords(language=Language.ENGLISH, query=query, limit=10)
    results = [
        {
            'lemma': item.lemma,
            'url': f'/en-tr/{item.slug}/',
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
        .order_by('order_index', 'id')
    )
    grouped = defaultdict(list)
    for sense in senses:
        grouped[sense.part_of_speech].append(sense)

    pos_group_qs = PosGroupOrder.objects.filter(headword=headword)
    pos_order_map = {pg.part_of_speech: pg.order_index for pg in pos_group_qs}
    pos_forms_map = {pg.part_of_speech: pg.irregular_forms for pg in pos_group_qs}

    sorted_grouped = dict(
        sorted(grouped.items(), key=lambda item: pos_order_map.get(item[0], 9999))
    )

    phrases = Phrase.objects.filter(headword=headword).order_by('order_index', 'id')

    return render(
        request,
        'dictionary/en_tr_detail.html',
        {
            'headword': headword,
            'grouped_senses': sorted_grouped,
            'pos_forms_map': pos_forms_map,
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
        return render(
            request,
            'dictionary/not_found.html',
            {
                'query': query,
                'direction': direction,
                'suggestions': [],
                'did_you_mean': [],
                'sample_words': _sample_headwords(Language.ENGLISH, limit=8),
            },
            status=404,
        )

    if direction == 'en-tr':
        headword = _best_headword_match(language=Language.ENGLISH, query=query)
        if headword:
            return en_tr_detail(request, headword.slug)
        suggestions = _search_headwords(language=Language.ENGLISH, query=query, limit=5)
        suggestion_items = [
            {'lemma': item.lemma, 'url': f'/en-tr/{item.slug}/'}
            for item in suggestions
        ]
        did_you_mean = [] if suggestion_items else _fuzzy_headword_suggestions(
            Language.ENGLISH, query, limit=6
        )
        return render(
            request,
            'dictionary/not_found.html',
            {
                'query': query,
                'direction': direction,
                'suggestions': suggestion_items,
                'did_you_mean': did_you_mean,
                'sample_words': _sample_headwords(Language.ENGLISH, limit=8),
            },
            status=404,
        )

    pos_groups = _search_tr_keywords(query, limit=80)
    if pos_groups:
        total = sum(len(rows) for rows in pos_groups.values())
        return render(request, 'dictionary/tr_en_results.html', {
            'query': query,
            'pos_groups': pos_groups,
            'total': total,
        })

    tr_suggestions = _autocomplete_tr_keywords(query, limit=5)
    did_you_mean = [] if tr_suggestions else _fuzzy_tr_suggestions(query, limit=6)
    return render(
        request,
        'dictionary/not_found.html',
        {
            'query': query,
            'direction': direction,
            'suggestions': tr_suggestions,
            'did_you_mean': did_you_mean,
            'sample_words': _sample_headwords(Language.ENGLISH, limit=8),
        },
        status=404,
    )
