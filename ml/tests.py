from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from events.models import Category, Event, TicketType


def make_event(organizer, category, **overrides):
    defaults = {
        'title': 'Test Event', 'description': 'desc', 'category': category,
        'organizer': organizer, 'venue': 'Venue', 'city': 'Kathmandu',
        'date': date.today() + timedelta(days=10),
        'start_time': time(18, 0), 'end_time': time(20, 0),
        'status': Event.Status.PUBLISHED,
    }
    defaults.update(overrides)
    return Event.objects.create(**defaults)


class ModelFileTests(TestCase):
    def test_trained_model_file_exists(self):
        """Confirms Phase 7's training step has actually produced a saved model."""
        model_path = Path(settings.BASE_DIR) / 'ml' / 'trained_models' / 'popularity_model.joblib'
        self.assertTrue(model_path.exists(), 'Run `python manage.py train_popularity_model` first.')

    def test_trained_model_loads_correctly(self):
        import joblib
        model_path = Path(settings.BASE_DIR) / 'ml' / 'trained_models' / 'popularity_model.joblib'
        if not model_path.exists():
            self.skipTest('No trained model file to load.')
        saved = joblib.load(model_path)
        self.assertIn('pipeline', saved)
        self.assertIn('model_name', saved)


class DataframeBuildingTests(TestCase):
    """Preprocessing test — confirms the training command's feature-building
    logic produces sane output on a minimal, known dataset."""

    def setUp(self):
        self.organizer = User.objects.create_user(username='mlorg', password='pass12345')
        self.category = Category.objects.create(name='Music', slug='music')

    def test_build_dataframe_produces_expected_columns(self):
        from ml.management.commands.train_popularity_model import Command
        event = make_event(self.organizer, self.category)
        TicketType.objects.create(event=event, name='General', price=500, quantity_total=10)

        df = Command()._build_dataframe()
        self.assertIn('is_popular', df.columns)
        self.assertIn('category', df.columns)
        self.assertIn('organizer_track_record', df.columns)

    def test_build_dataframe_excludes_leakage_features(self):
        """Confirms views/registration_count never end up as model inputs."""
        from ml.management.commands.train_popularity_model import NUMERIC_FEATURES
        self.assertNotIn('views', NUMERIC_FEATURES)
        self.assertNotIn('registration_count', NUMERIC_FEATURES)

    def test_event_with_zero_capacity_excluded(self):
        """Invalid/degenerate input handling: an event with 0-quantity tickets
        shouldn't produce a divide-by-zero or a garbage row."""
        from ml.management.commands.train_popularity_model import Command
        event = make_event(self.organizer, self.category)
        TicketType.objects.create(event=event, name='General', price=500, quantity_total=0)

        df = Command()._build_dataframe()
        self.assertEqual(len(df), 0)  # correctly excluded, not crashed