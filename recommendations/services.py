"""
Phase 6 — Stage 1 rule-based recommendation scoring.
Computed on-demand, not cached — deliberately simple at this data scale.
"""
from collections import defaultdict
from datetime import date
from events.models import Event, EventInteraction
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import timedelta
from django.utils import timezone

WEIGHTS = {
    'interest': 5, 'interaction': 3, 'location': 2, 'freshness': 2, 'popularity': 1,
}
INTERACTION_WEIGHTS = {'view': 1, 'save': 2, 'book': 3}


def _interaction_scores_by_category(user):
    scores = defaultdict(int)
    interactions = EventInteraction.objects.filter(user=user).select_related('event__category')
    for interaction in interactions:
        weight = INTERACTION_WEIGHTS.get(interaction.interaction_type, 0)
        scores[interaction.event.category_id] += weight
    return scores

def get_recommendations(user, limit=10):
    content_based = get_content_based_recommendations(user, limit=limit)
    if content_based is not None:
        return content_based
    return get_rule_based_recommendations(user, limit=limit)

def get_rule_based_recommendations(user, limit=10):
    today = date.today()
    candidates = list(
        Event.objects.filter(status=Event.Status.PUBLISHED, date__gte=today)
        .exclude(organizer=user)
        .select_related('category')
    )
    if not candidates:
        return []

    max_views = max((e.views for e in candidates), default=0) or 1
    profile = getattr(user, 'profile', None)
    interest_ids = set(profile.interests.values_list('id', flat=True)) if profile else set()

    interaction_scores = _interaction_scores_by_category(user) if user.is_authenticated else {}
    max_interaction = max(interaction_scores.values(), default=0) or 1

    results = []
    for event in candidates:
        components = {
            'interest': 1.0 if event.category_id in interest_ids else 0.0,
            'interaction': interaction_scores.get(event.category_id, 0) / max_interaction,
            'popularity': event.views / max_views,
        }
        user_city = profile.city if profile and profile.city else None
        components['location'] = 1.0 if user_city and user_city.lower() == event.city.lower() else 0.0
        days_until = (event.date - today).days
        components['freshness'] = max(0.0, 1 - days_until / 60)

        total = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
        results.append({
            'event': event, 'score': round(total, 2),
            'reason': _build_reason(components, event),
        })

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def _build_reason(components, event):
    if components['interest'] > 0:
        return f'Because you like {event.category.name}'
    if components['interaction'] > 0.5:
        return 'Similar to events you\u2019ve viewed or saved'
    if components['location'] > 0:
        return f'Popular in {event.city}'
    if components['popularity'] > 0.6:
        return 'Trending now'
    return 'You might like this'


def _price_bucket(price):
    price = float(price)
    if price == 0:
        return 'free'
    if price < 1000:
        return 'low'
    if price < 3000:
        return 'mid'
    return 'high'


def _event_features(event, ticket_type):
    return {
        f'category={event.category.name}': 1,
        f'city={event.city}': 1,
        f'price={_price_bucket(ticket_type.price)}': 1,
        'weekend': int(event.date.weekday() >= 5),
    }


def get_content_based_recommendations(user, limit=10):
    """
    Stage 2 — content-based filtering via cosine similarity.
    Falls back to None if the user has no interaction history yet
    (nothing to build a user vector from) — caller should use the
    Stage 1 rule-based recommender in that case.
    """
    today = date.today()
    candidates = list(
        Event.objects.filter(status=Event.Status.PUBLISHED, date__gte=today)
        .exclude(organizer=user)
        .select_related('category')
        .prefetch_related('ticket_types')
    )
    candidates = [(e, e.ticket_types.first()) for e in candidates]
    candidates = [(e, t) for e, t in candidates if t is not None]
    if not candidates:
        return None

    interactions = (
        EventInteraction.objects.filter(user=user)
        .select_related('event__category')
        .prefetch_related('event__ticket_types')
    )
    if not interactions.exists():
        return None  # no history yet — let the caller fall back to Stage 1

    vectorizer = DictVectorizer(sparse=False)
    candidate_feature_dicts = [_event_features(e, t) for e, t in candidates]
    candidate_matrix = vectorizer.fit_transform(candidate_feature_dicts)

    weighted_vectors, total_weight = [], 0
    for interaction in interactions:
        ticket_type = interaction.event.ticket_types.first()
        if not ticket_type:
            continue
        weight = INTERACTION_WEIGHTS.get(interaction.interaction_type, 0)
        try:
            vec = vectorizer.transform([_event_features(interaction.event, ticket_type)])[0]
        except ValueError:
            continue  # feature seen in history but not in current candidates (e.g. old category)
        weighted_vectors.append(vec * weight)
        total_weight += weight

    if not weighted_vectors or total_weight == 0:
        return None

    user_vector = sum(weighted_vectors) / total_weight
    similarities = cosine_similarity([user_vector], candidate_matrix)[0]

    results = []
    for (event, ticket_type), sim in zip(candidates, similarities):
        results.append({
            'event': event,
            'score': round(float(sim) * 10, 2),  # scaled to roughly match Stage 1's score range
            'reason': _content_based_reason(event, interactions),
        })
    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def _content_based_reason(event, interactions):
    same_category = [i for i in interactions if i.event.category_id == event.category_id]
    if same_category:
        return f'Similar to {event.category.name} events you\u2019ve engaged with'
    return 'Matches your activity patterns'

TRENDING_WINDOW_DAYS = 14

def get_trending_events(limit=10):
    """
    Phase 9 — transparent trending score, NOT machine learning.
    Ranks by recent (last 14 days) weighted interaction count only —
    old high-view events naturally fall off once their interactions
    age out of the window; new events with fresh activity rise.
    """
    today = date.today()
    cutoff = timezone.now() - timedelta(days=TRENDING_WINDOW_DAYS)

    candidates = Event.objects.filter(status=Event.Status.PUBLISHED, date__gte=today)
    recent_interactions = (
        EventInteraction.objects.filter(event__in=candidates, timestamp__gte=cutoff)
        .select_related('event')
    )

    scores = defaultdict(float)
    for interaction in recent_interactions:
        scores[interaction.event_id] += INTERACTION_WEIGHTS.get(interaction.interaction_type, 0)

    results = []
    for event in candidates:
        score = scores.get(event.id, 0)
        if score > 0:  # only show events with genuine recent activity
            results.append({'event': event, 'score': round(score, 1)})

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]