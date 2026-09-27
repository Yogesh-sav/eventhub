"""
REAL DATA: currently-scheduled events in Nepal (Oct-Dec 2026), added manually
from public event listings. Distinct from the synthetic seed_data.py events.
"""
from datetime import date, time
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from accounts.models import Profile
from events.models import Category, Event, TicketType

REAL_EVENTS = [
    # (title, category, venue, city, date, start_hour, price)
    ('XTREME East Side', 'Music', 'Dharan Cricket Ground', 'Dharan', date(2026, 10, 3), 17, 800),
    ('Bipul Chettri: Pravah Nepal Tour — Butwal', 'Music', 'BICC', 'Butwal', date(2026, 10, 14), 18, 1000),
    ('Astha Tamang-Maskey: Khula Aakash', 'Music', 'Moksh Bar', 'Lalitpur', date(2026, 10, 9), 19, 1500),
    ('Astha Tamang-Maskey: Sabai Thikai Huncha', 'Music', 'Trisara', 'Lazimpat', date(2026, 10, 11), 19, 1500),
    ('Nepathya Live — Kirtipur', 'Music', 'Lab School Ground', 'Kirtipur', date(2026, 10, 10), 18, 1000),
    ('Nepathya Live — Itahari', 'Music', 'Itahari Stadium', 'Itahari', date(2026, 11, 4), 18, 1000),
    ('Nepathya Live — Charali Jhapa', 'Music', 'Hatemalo Khel Maidan', 'Charali, Jhapa', date(2026, 11, 7), 18, 1000),
    ('Nepathya Live — Belchautara', 'Music', 'Bhanu Bhakta Campus Ground', 'Belchautara, Tanahun', date(2026, 11, 28), 18, 1000),
    ('Echoes of Bollywood ft. Monali Thakur', 'Music', 'Club NOVA', 'Thamel', date(2026, 11, 14), 19, 2000),
    ('HunterHood Live', 'Music', 'Bhrikuti Mandap', 'Kathmandu', date(2026, 12, 12), 18, 1200),
    ('Dashain Fest 2083', 'Art', 'Amar Singh Ground', 'Pokhara', date(2026, 10, 10), 16, 500),
    ('Dashain Changa Carnival 2083', 'Art', 'Chyasal Football Ground', 'Lalitpur', date(2026, 10, 11), 16, 500),
    ('Rewind Fest: Homecoming Dashain Edition', 'Music', 'Butwal International Convention Center', 'Butwal', date(2026, 10, 10), 17, 800),
    ('Godawari Mahotsav 2083', 'Art', 'Godawari Football Ground', 'Godawari', date(2026, 10, 10), 10, 500),
    ('Youth Music Fest', 'Music', 'BICC Ground', 'Butwal', date(2026, 10, 31), 15, 500),
]


class Command(BaseCommand):
    help = 'Add real, currently-scheduled Nepal events (Oct-Dec 2026)'

    def handle(self, *args, **options):
        organizer, created = User.objects.get_or_create(
            username='nepal_events_curator', defaults={'email': 'events@example.com'}
        )
        if created:
            organizer.set_password('eventhub123')
            organizer.save()
            organizer.profile.role = Profile.Role.ORGANIZER
            organizer.profile.save()

        added = 0
        for title, cat_name, venue, city, event_date, hour, price in REAL_EVENTS:
            if Event.objects.filter(title=title, date=event_date).exists():
                continue  # already added, skip (idempotent re-runs)
            category = Category.objects.get(name=cat_name)
            event = Event.objects.create(
                title=title, description=f'{title} at {venue}, {city}.',
                category=category, organizer=organizer, venue=venue, city=city,
                date=event_date, start_time=time(hour, 0), end_time=time((hour + 3) % 24, 0),
                status=Event.Status.PUBLISHED,
            )
            TicketType.objects.create(event=event, name='General', price=price, quantity_total=500)
            added += 1

        self.stdout.write(self.style.SUCCESS(f'Added {added} real events.'))