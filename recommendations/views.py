from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import get_recommendations
from .services import get_recommendations, get_trending_events

# Create your views here.

@login_required
def recommended_for_you(request):
    recommendations = get_recommendations(request.user, limit=12)
    return render(request, 'recommendations/recommended.html', {'recommendations': recommendations})

def trending_events(request):
    trending = get_trending_events(limit=12)
    return render(request, 'recommendations/trending.html', {'trending': trending})