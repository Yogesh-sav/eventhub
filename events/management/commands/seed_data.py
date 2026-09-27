"""
Seed EventHub with data for Phase 5+.

REAL (from venue_data.csv, downloaded from Hugging Face: rebrowser/seatgeek-dataset):
    - venue names, cities, capacities

REAL-DERIVED (from performers_data.csv taxonomy):
    - Sports and Music categories exist because the real data shows those taxonomies

SYNTHETIC (generated here, not from any external source):
    - event titles/descriptions, 6 additional categories (Technology, Business,
      Education, Art, Health, Gaming), all users, all interactions/bookings/saves,
      prices, dates. Interaction patterns are weighted by synthetic per-user
      category preference, not uniform-random, so they carry a learnable signal
      for later recommendation phases.
"""
import csv
import random
from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from accounts.models import Profile
from events.models import Category, Event, TicketType, Booking, SavedEvent, EventInteraction

# ---- SYNTHETIC: category list (Sports/Music are real-derived, rest are synthetic) ----
CATEGORIES = ['Sports', 'Music', 'Technology', 'Business', 'Education', 'Art', 'Health', 'Gaming']

# ---- SYNTHETIC: title templates per category, used to generate fake event names ----
TITLE_TEMPLATES = {
    'Sports': ['{venue} Championship Night', 'Live Game Day at {venue}', '{venue} Rivalry Match'],
    'Music': ['Live at {venue}', '{venue} Concert Night', 'Acoustic Sessions at {venue}'],
    'Technology': ['Tech Summit at {venue}', 'AI & Innovation Meetup', 'Developer Conference {venue}'],
    'Business': ['Startup Networking Night', 'Business Leaders Forum', 'Entrepreneurship Workshop'],
    'Education': ['Career Development Seminar', 'Learning & Skills Workshop', 'Public Lecture Series'],
    'Art': ['Gallery Opening Night', 'Local Artists Showcase', 'Art & Culture Fair'],
    'Health': ['Wellness & Fitness Expo', 'Yoga in the Park', 'Community Health Fair'],
    'Gaming': ['Esports Tournament', 'Gaming Convention', 'LAN Party Night'],
}

# ---- SYNTHETIC: rough price ranges per category (min, max) ----
PRICE_RANGES = {
    'Sports': (500, 3000), 'Music': (500, 5000), 'Technology': (0, 1500),
    'Business': (0, 2000), 'Education': (0, 1000), 'Art': (0, 800),
    'Health': (0, 1000), 'Gaming': (300, 1500),
}


class Command(BaseCommand):
    help = 'Seed the database with real venue data + synthetic events/users/interactions'

    def add_arguments(self, parser):
        parser.add_argument('--events', type=int, default=150)
        parser.add_argument('--users', type=int, default=60)

    def handle(self, *args, **options):
        random.seed(42)  # reproducible runs, documented for the report
        n_events = options['events']
        n_users = options['users']

        categories = self._create_categories()
        venues = self._load_real_venues()
        organizers = self._create_organizers(count=15)
        events = self._create_events(n_events, categories, venues, organizers)
        users = self._create_users(n_users, categories)
        self._create_interactions(users, events)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(categories)} categories, {len(venues)} real venues used, '
            f'{len(organizers)} organizers, {len(events)} events, {len(users)} users.'
        ))

    def _create_categories(self):
        cats = []
        for name in CATEGORIES:
            slug = slugify(name)
            cat, created = Category.objects.get_or_create(slug=slug, defaults={'name': name})
            if not created and cat.name != name:
                cat.name = name  # normalize casing from earlier manual testing
                cat.save()
            cats.append(cat)
        return cats

    def _load_real_venues(self):
        # REAL DATA — read straight from the downloaded CSV, no modification
        path = Path(settings.BASE_DIR) / 'dataset' / 'venue_data.csv'
        venues = []
        with open(path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['name'] and row['addressCity']:
                    venues.append({
                        'name': row['name'],
                        'city': row['addressCity'],
                        'capacity': int(row['capacity']) if row['capacity'] else 500,
                    })
        return venues

    def _create_organizers(self, count):
        organizers = []
        for i in range(1, count + 1):
            user, created = User.objects.get_or_create(
                username=f'organizer{i}', defaults={'email': f'organizer{i}@example.com'}
            )
            if created:
                user.set_password('eventhub123')
                user.save()
                user.profile.role = Profile.Role.ORGANIZER
                user.profile.save()
            organizers.append(user)
        return organizers

    def _create_events(self, n_events, categories, venues, organizers):
        events = []
        today = date.today()
        for _ in range(n_events):
            category = random.choice(categories)
            venue = random.choice(venues)
            title = random.choice(TITLE_TEMPLATES[category.name]).format(venue=venue['name'])
            event_date = today + timedelta(days=random.randint(-30, 90))  # some past, mostly future
            start_hour = random.choice([10, 14, 18, 19, 20])

            event = Event.objects.create(
                title=title,
                description=f'A {category.name.lower()} event at {venue["name"]}, {venue["city"]}.',
                category=category,
                organizer=random.choice(organizers),
                venue=venue['name'],
                city=venue['city'],
                date=event_date,
                start_time=time(start_hour, 0),
                end_time=time((start_hour + 2) % 24, 0),
                status=Event.Status.PUBLISHED,
                views=random.randint(0, 300),
            )
            low, high = PRICE_RANGES[category.name]
            capacity = min(venue['capacity'] or 500, 2000)  # cap synthetic ticket volume sensibly
            TicketType.objects.create(
                event=event, name='General', price=round(random.uniform(low, high), 2),
                quantity_total=max(20, capacity // 10),
            )
            events.append((event, category))
        return events

    def _create_users(self, n_users, categories):
        users = []
        for i in range(1, n_users + 1):
            user, created = User.objects.get_or_create(
                username=f'user{i}', defaults={'email': f'user{i}@example.com'}
            )
            if created:
                user.set_password('eventhub123')
                user.save()
            # SYNTHETIC: each user prefers 1-3 categories — this is the signal
            # later recommendation phases will learn from.
            prefs = random.sample(categories, k=random.randint(1, 3))
            user.profile.interests.set(prefs)
            users.append((user, prefs))
        return users

    def _create_interactions(self, users, events):
        for user, prefs in users:
            pref_names = {c.name for c in prefs}
            for event, category in events:
                # Higher interaction probability if the event matches a preferred category
                base_chance = 0.35 if category.name in pref_names else 0.05
                if random.random() < base_chance:
                    EventInteraction.objects.create(user=user, event=event, interaction_type='view')
                    if random.random() < 0.4:
                        SavedEvent.objects.get_or_create(user=user, event=event)
                        EventInteraction.objects.create(user=user, event=event, interaction_type='save')
                    if random.random() < 0.2:
                        ticket_type = event.ticket_types.first()
                        if ticket_type and ticket_type.tickets_available > 0:
                            Booking.objects.create(
                                user=user, event=event, ticket_type=ticket_type, quantity=1
                            )
                            EventInteraction.objects.create(user=user, event=event, interaction_type='book')