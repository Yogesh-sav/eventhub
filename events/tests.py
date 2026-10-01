from django.test import TestCase
from datetime import date, time, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import Profile
from .models import Booking, Category, Event, TicketType

# Create your tests here.

def make_organizer(username='org1'):
    user = User.objects.create_user(username=username, password='pass12345')
    user.profile.role = Profile.Role.ORGANIZER
    user.profile.save()
    return user


def make_event(organizer, category, **overrides):
    defaults = {
        'title': 'Test Event', 'description': 'desc', 'category': category,
        'organizer': organizer, 'venue': 'Test Venue', 'city': 'Kathmandu',
        'date': date.today() + timedelta(days=10),
        'start_time': time(18, 0), 'end_time': time(20, 0),
        'status': Event.Status.PUBLISHED,
    }
    defaults.update(overrides)
    return Event.objects.create(**defaults)


class EventCRUDTests(TestCase):
    def setUp(self):
        self.organizer = make_organizer()
        self.other_organizer = make_organizer('org2')
        self.category = Category.objects.create(name='Music', slug='music')

    def test_organizer_can_create_event(self):
        self.client.login(username='org1', password='pass12345')
        response = self.client.post(reverse('events:event_create'), {
            'title': 'New Event', 'description': 'desc', 'category': self.category.id,
            'venue': 'Venue', 'city': 'Kathmandu', 'date': date.today() + timedelta(days=5),
            'start_time': '18:00', 'end_time': '20:00', 'status': Event.Status.PUBLISHED,
            'ticket_types-TOTAL_FORMS': '1', 'ticket_types-INITIAL_FORMS': '0',
            'ticket_types-0-name': 'General', 'ticket_types-0-price': '500', 'ticket_types-0-quantity_total': '50',
        })
        self.assertTrue(Event.objects.filter(title='New Event', organizer=self.organizer).exists())

    def test_organizer_can_edit_own_event(self):
        event = make_event(self.organizer, self.category)
        self.client.login(username='org1', password='pass12345')
        response = self.client.post(reverse('events:event_edit', args=[event.pk]), {
            'title': 'Updated Title', 'description': 'desc', 'category': self.category.id,
            'venue': event.venue, 'city': event.city, 'date': event.date,
            'start_time': '18:00', 'end_time': '20:00', 'status': Event.Status.PUBLISHED,
            'ticket_types-TOTAL_FORMS': '0', 'ticket_types-INITIAL_FORMS': '0',
        })
        event.refresh_from_db()
        self.assertEqual(event.title, 'Updated Title')

    def test_organizer_cannot_edit_others_event(self):
        event = make_event(self.other_organizer, self.category)
        self.client.login(username='org1', password='pass12345')
        response = self.client.get(reverse('events:event_edit', args=[event.pk]))
        self.assertEqual(response.status_code, 403)

    def test_organizer_can_delete_own_event(self):
        event = make_event(self.organizer, self.category)
        self.client.login(username='org1', password='pass12345')
        self.client.post(reverse('events:event_delete', args=[event.pk]))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_regular_user_cannot_access_dashboard(self):
        user = User.objects.create_user(username='plainuser', password='pass12345')
        self.client.login(username='plainuser', password='pass12345')
        response = self.client.get(reverse('events:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_invalid_event_data_rejected(self):
        self.client.login(username='org1', password='pass12345')
        response = self.client.post(reverse('events:event_create'), {
            'title': '', 'description': 'desc',  # missing required title
            'ticket_types-TOTAL_FORMS': '0', 'ticket_types-INITIAL_FORMS': '0',
        })
        self.assertEqual(Event.objects.filter(description='desc').count(), 0)


class EventVisibilityTests(TestCase):
    def setUp(self):
        self.organizer = make_organizer()
        self.category = Category.objects.create(name='Music', slug='music')

    def test_published_event_visible_in_list(self):
        make_event(self.organizer, self.category, title='Visible Event')
        response = self.client.get(reverse('events:event_list'))
        self.assertContains(response, 'Visible Event')

    def test_draft_event_hidden_from_list(self):
        make_event(self.organizer, self.category, title='Hidden Draft', status=Event.Status.DRAFT)
        response = self.client.get(reverse('events:event_list'))
        self.assertNotContains(response, 'Hidden Draft')

    def test_draft_event_detail_returns_404(self):
        event = make_event(self.organizer, self.category, status=Event.Status.DRAFT)
        response = self.client.get(reverse('events:event_detail', args=[event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_published_event_detail_increments_views(self):
        event = make_event(self.organizer, self.category)
        self.client.get(reverse('events:event_detail', args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.views, 1)

class BookingTests(TestCase):
    def setUp(self):
        self.organizer = make_organizer()
        self.user = User.objects.create_user(username='booker', password='pass12345')
        self.category = Category.objects.create(name='Music', slug='music')
        self.event = make_event(self.organizer, self.category)
        self.ticket_type = TicketType.objects.create(
            event=self.event, name='General', price=500, quantity_total=10
        )

    def test_user_can_book_available_ticket(self):
        self.client.login(username='booker', password='pass12345')
        self.client.post(reverse('events:event_book', args=[self.event.pk]), {
            'ticket_type': self.ticket_type.pk, 'quantity': 2,
        })
        self.assertTrue(Booking.objects.filter(user=self.user, event=self.event, quantity=2).exists())

    def test_cannot_book_more_than_available_capacity(self):
        self.client.login(username='booker', password='pass12345')
        self.client.post(reverse('events:event_book', args=[self.event.pk]), {
            'ticket_type': self.ticket_type.pk, 'quantity': 999,  # way over the 10 available
        })
        self.assertFalse(Booking.objects.filter(user=self.user, event=self.event).exists())

    def test_capacity_decreases_after_booking(self):
        self.client.login(username='booker', password='pass12345')
        self.client.post(reverse('events:event_book', args=[self.event.pk]), {
            'ticket_type': self.ticket_type.pk, 'quantity': 3,
        })
        self.ticket_type.refresh_from_db()
        self.assertEqual(self.ticket_type.tickets_available, 7)

    def test_anonymous_user_cannot_book(self):
        response = self.client.post(reverse('events:event_book', args=[self.event.pk]), {
            'ticket_type': self.ticket_type.pk, 'quantity': 1,
        })
        self.assertNotEqual(response.status_code, 200)  # redirected to login
        self.assertFalse(Booking.objects.filter(event=self.event).exists())

    def test_save_toggle_creates_and_removes(self):
        self.client.login(username='booker', password='pass12345')
        url = reverse('events:event_save_toggle', args=[self.event.pk])
        self.client.post(url)  # save
        self.assertTrue(self.user.saved_events.filter(event=self.event).exists())
        self.client.post(url)  # unsave (toggle)
        self.assertFalse(self.user.saved_events.filter(event=self.event).exists())