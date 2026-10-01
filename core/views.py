from django.shortcuts import render
from events.models import Event
from recommendations.services import get_trending_events


def home(request):
    upcoming = Event.objects.filter(status=Event.Status.PUBLISHED).order_by('date')[:6]
    trending = get_trending_events(limit=3)
    return render(request, 'core/home.html', {'upcoming': upcoming, 'trending': trending})