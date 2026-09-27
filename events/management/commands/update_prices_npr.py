"""One-off: rescale existing synthetic ticket prices to NPR-appropriate values."""
import random
from django.core.management.base import BaseCommand
from events.models import TicketType

NPR_PRICE_RANGES = {
    'Sports': (500, 3000), 'Music': (500, 5000), 'Technology': (0, 1500),
    'Business': (0, 2000), 'Education': (0, 1000), 'Art': (0, 800),
    'Health': (0, 1000), 'Gaming': (300, 1500),
}


class Command(BaseCommand):
    help = 'Rescale existing TicketType prices to NPR-appropriate values, by category'

    def handle(self, *args, **options):
        random.seed(42)
        updated = 0
        for ticket_type in TicketType.objects.select_related('event__category'):
            category_name = ticket_type.event.category.name
            low, high = NPR_PRICE_RANGES.get(category_name, (200, 1000))
            ticket_type.price = round(random.uniform(low, high), 2)
            ticket_type.save(update_fields=['price'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} ticket prices to NPR.'))
        