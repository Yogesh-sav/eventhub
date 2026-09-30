"""Phase 7B — generate and store popularity predictions for all published events."""
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from events.models import Event
from ml.models import PopularityPrediction


class Command(BaseCommand):
    help = 'Generate popularity predictions for all events using the trained model'

    def handle(self, *args, **options):
        model_path = Path(settings.BASE_DIR) / 'ml' / 'trained_models' / 'popularity_model.joblib'
        if not model_path.exists():
            self.stdout.write(self.style.ERROR('No trained model found. Run train_popularity_model first.'))
            return

        saved = joblib.load(model_path)
        pipeline, model_name = saved['pipeline'], saved['model_name']

        events = list(Event.objects.filter(status=Event.Status.PUBLISHED).select_related('category', 'organizer').prefetch_related('ticket_types'))
        rows, event_objs = [], []
        for event in events:
            ticket_type = event.ticket_types.first()
            if not ticket_type or ticket_type.quantity_total == 0:
                continue
            rows.append({
                'category': event.category.name,
                'city_bucket': event.city,  # unseen cities handled by OneHotEncoder(handle_unknown='ignore')
                'price': float(ticket_type.price),
                'capacity': ticket_type.quantity_total,
                'days_lead_time': max(0, (event.date - event.created_at.date()).days),
                'day_of_week': event.date.weekday(),
                'is_weekend': int(event.date.weekday() >= 5),
                'month': event.date.month,
                'organizer_track_record': 0.3,  # neutral prior at prediction time for new/unseen events
            })
            event_objs.append(event)

        if not rows:
            self.stdout.write(self.style.WARNING('No eligible events to predict on.'))
            return

        df = pd.DataFrame(rows)
        probs = pipeline.predict_proba(df)[:, 1]
        labels = probs > 0.5

        for event, label, prob in zip(event_objs, labels, probs):
            PopularityPrediction.objects.update_or_create(
                event=event,
                defaults={'predicted_label': bool(label), 'predicted_probability': float(prob), 'model_version': model_name},
            )

        self.stdout.write(self.style.SUCCESS(f'Generated predictions for {len(event_objs)} events.'))