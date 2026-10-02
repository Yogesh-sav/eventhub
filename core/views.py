from datetime import date
from django.shortcuts import render
from events.models import Event
from recommendations.services import get_trending_events


def home(request):
    upcoming = Event.objects.filter(
        status=Event.Status.PUBLISHED, date__gte=date.today()
    ).order_by('date')[:6]
    trending = get_trending_events(limit=3)
    return render(request, 'core/home.html', {'upcoming': upcoming, 'trending': trending})

def terms(request):
    return render(request, 'core/terms.html')

def about(request):
    return render(request, 'core/about.html')


def contact(request):
    return render(request, 'core/contact.html')