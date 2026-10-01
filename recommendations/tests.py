from django.test import TestCase
from datetime import date, time, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from events.models import Category, Event, EventInteraction
from .services import get_recommendations, get_content_based_recommendations, get_rule_based_recommendations

# Create your tests here.

def make_event(organizer, category, city='Kathmandu', **overrides):
    defaults = {
        'title': 'Test Event', 'description': 'desc', 'category': category,
        'organizer': organizer, 'venue': 'Venue', 'city': city,
        'date': date.today() + timedelta(days=10),
        'start_time': time(18, 0), 'end_time': time(20, 0),
        'status': Event.Status.PUBLISHED,
    }
    defaults.update(overrides)
    return Event.objects.create(**defaults)


class RecommendationTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(username='org', password='pass12345')
        self.music = Category.objects.create(name='Music', slug='music')
        self.sports = Category.objects.create(name='Sports', slug='sports')
        self.user = User.objects.create_user(username='recuser', password='pass12345')

    def test_new_user_gets_fallback_recommendations(self):
        """Cold start: no interests, no history — should still get results, not an error or empty list."""
        make_event(self.organizer, self.music)
        make_event(self.organizer, self.sports)
        results = get_recommendations(self.user)
        self.assertGreater(len(results), 0)

    def test_new_user_uses_rule_based_not_content_based(self):
        make_event(self.organizer, self.music)
        content_based = get_content_based_recommendations(self.user)
        self.assertIsNone(content_based)  # confirms fallback trigger condition is correct

    def test_interaction_history_affects_recommendations(self):
        """A user who only interacts with Music events should get content-based results
        that favor Music once they have at least one interaction."""
        music_event = make_event(self.organizer, self.music, title='Music Event')
        make_event(self.organizer, self.sports, title='Sports Event')

        EventInteraction.objects.create(user=self.user, event=music_event, interaction_type='book')
        # need a ticket type for content-based vectorization to work
        from events.models import TicketType
        TicketType.objects.create(event=music_event, name='General', price=500, quantity_total=10)
        TicketType.objects.create(event=Event.objects.get(title='Sports Event'), name='General', price=500, quantity_total=10)

        results = get_content_based_recommendations(self.user)
        self.assertIsNotNone(results)
        top_event_titles = [r['event'].title for r in results[:1]]
        self.assertIn('Music Event', top_event_titles)

    def test_past_events_excluded_from_recommendations(self):
        make_event(self.organizer, self.music, title='Past Event', date=date.today() - timedelta(days=5))
        results = get_rule_based_recommendations(self.user)
        titles = [r['event'].title for r in results]
        self.assertNotIn('Past Event', titles)

    def test_own_events_excluded_from_recommendations(self):
        """An organizer shouldn't see their own events recommended back to them."""
        own_event = make_event(self.organizer, self.music, title='My Own Event')
        results = get_rule_based_recommendations(self.organizer)
        titles = [r['event'].title for r in results]
        self.assertNotIn('My Own Event', titles)