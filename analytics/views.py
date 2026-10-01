import json
from datetime import timedelta
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone
from events.decorators import organizer_required
from events.models import Booking, Event, EventInteraction
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

@organizer_required
def organizer_analytics(request):
    events = Event.objects.filter(organizer=request.user).prefetch_related('ticket_types', 'popularity_prediction')

    total_views = sum(e.views for e in events)
    total_registrations = sum(e.registration_count for e in events)

    event_stats = []
    utilizations = []
    for e in events:
        capacity = sum(t.quantity_total for t in e.ticket_types.all())
        utilization = (e.registration_count / capacity * 100) if capacity else 0
        if capacity:
            utilizations.append(utilization)
        event_stats.append({
            'event': e, 'capacity': capacity, 'utilization': round(utilization, 1),
            'prediction': getattr(e, 'popularity_prediction', None),
        })
    avg_utilization = round(sum(utilizations) / len(utilizations), 1) if utilizations else 0

    cutoff = timezone.now() - timedelta(days=30)
    bookings = Booking.objects.filter(event__organizer=request.user, booked_at__gte=cutoff, status='confirmed')
    trend = {}
    for b in bookings:
        day = b.booked_at.date().isoformat()
        trend[day] = trend.get(day, 0) + b.quantity
    trend_labels = sorted(trend.keys())
    trend_values = [trend[d] for d in trend_labels]

    return render(request, 'analytics/organizer_analytics.html', {
        'total_views': total_views, 'total_registrations': total_registrations,
        'avg_utilization': avg_utilization, 'event_count': events.count(),
        'event_stats': event_stats,
        'trend_labels': json.dumps(trend_labels), 'trend_values': json.dumps(trend_values),
    })


@login_required
def admin_analytics(request):
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    total_users = User.objects.filter(profile__role='user').count()
    total_organizers = User.objects.filter(profile__role='organizer').count()
    total_events = Event.objects.count()
    total_bookings = Booking.objects.filter(status='confirmed').count()

    category_counts = (
        Event.objects.values('category__name').annotate(count=Count('id')).order_by('-count')
    )
    most_viewed = Event.objects.select_related('category').order_by('-views')[:5]

    cutoff = timezone.now() - timedelta(days=30)
    interactions = EventInteraction.objects.filter(timestamp__gte=cutoff)
    engagement = {}
    for i in interactions:
        day = i.timestamp.date().isoformat()
        engagement[day] = engagement.get(day, 0) + 1
    engagement_labels = sorted(engagement.keys())
    engagement_values = [engagement[d] for d in engagement_labels]

    return render(request, 'analytics/admin_analytics.html', {
        'total_users': total_users, 'total_organizers': total_organizers,
        'total_events': total_events, 'total_bookings': total_bookings,
        'category_counts': category_counts, 'most_viewed': most_viewed,
        'engagement_labels': json.dumps(engagement_labels), 'engagement_values': json.dumps(engagement_values),
    })