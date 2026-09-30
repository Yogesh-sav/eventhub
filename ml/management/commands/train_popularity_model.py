"""
Phase 7 — train and evaluate a popularity-prediction classifier.

Target: is_popular = 1 if an event's fill rate (bookings / capacity) is
above the dataset median, else 0.

Deliberately excludes `views` and `registration_count` as features, since
they are components of (or closely tied to) the target itself — using them
would be data leakage per the project brief's explicit warning.

Limitation documented here for the report: ~165 events is a small dataset
for ML; metrics below are real (from an actual train/test split), but
should be read with that sample size in mind.
"""
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from events.models import Event

NUMERIC_FEATURES = ['price', 'capacity', 'days_lead_time', 'day_of_week', 'is_weekend', 'month', 'organizer_track_record']
CATEGORICAL_FEATURES = ['category', 'city_bucket']


class Command(BaseCommand):
    help = 'Train and evaluate the event popularity prediction model'

    def handle(self, *args, **options):
        df = self._build_dataframe()
        if len(df) < 20:
            self.stdout.write(self.style.ERROR('Not enough events to train on. Run seed_data first.'))
            return

        X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        y = df['is_popular']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        preprocessor = ColumnTransformer([
            ('num', StandardScaler(), NUMERIC_FEATURES),
            ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL_FEATURES),
        ])

        candidates = {
            'LogisticRegression': LogisticRegression(max_iter=1000),
            'RandomForest': RandomForestClassifier(n_estimators=200, random_state=42),
        }

        self.stdout.write(self.style.WARNING(f'Training on {len(X_train)} events, testing on {len(X_test)}.'))
        best_name, best_pipeline, best_score = None, None, -1

        for name, clf in candidates.items():
            pipeline = Pipeline([('prep', preprocessor), ('clf', clf)])
            pipeline.fit(X_train, y_train)
            preds = pipeline.predict(X_test)
            probs = pipeline.predict_proba(X_test)[:, 1]

            acc = accuracy_score(y_test, preds)
            f1 = f1_score(y_test, preds)
            auc = roc_auc_score(y_test, probs)

            self.stdout.write(f'\n--- {name} ---')
            self.stdout.write(f'Accuracy: {acc:.3f}  F1: {f1:.3f}  ROC-AUC: {auc:.3f}')
            self.stdout.write(classification_report(y_test, preds, target_names=['not popular', 'popular']))

            if auc > best_score:
                best_name, best_pipeline, best_score = name, pipeline, auc

        self.stdout.write(self.style.SUCCESS(f'\nSelected model: {best_name} (ROC-AUC {best_score:.3f})'))

        # Refit the winning model type on the FULL dataset for production use —
        # standard practice: the train/test split above is only for model
        # selection/evaluation, the final saved model uses all available data.
        final_pipeline = Pipeline([('prep', preprocessor), ('clf', candidates[best_name])])
        final_pipeline.fit(X, y)

        model_dir = Path(settings.BASE_DIR) / 'ml' / 'trained_models'
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump({'pipeline': final_pipeline, 'model_name': best_name}, model_dir / 'popularity_model.joblib')
        self.stdout.write(self.style.SUCCESS(f'Saved model to {model_dir / "popularity_model.joblib"}'))

    def _build_dataframe(self):
        events = list(Event.objects.select_related('category', 'organizer').prefetch_related('ticket_types'))
        rows = []
        for event in events:
            ticket_type = event.ticket_types.first()
            if not ticket_type:
                continue
            capacity = ticket_type.quantity_total
            if capacity == 0:
                continue
            fill_rate = event.registration_count / capacity
            rows.append({
                'event_id': event.id,
                'category': event.category.name,
                'city': event.city,
                'price': float(ticket_type.price),
                'capacity': capacity,
                'days_lead_time': max(0, (event.date - event.created_at.date()).days),
                'day_of_week': event.date.weekday(),
                'is_weekend': int(event.date.weekday() >= 5),
                'month': event.date.month,
                'organizer_id': event.organizer_id,
                'fill_rate': fill_rate,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df

        median_fill = df['fill_rate'].median()
        df['is_popular'] = (df['fill_rate'] > median_fill).astype(int)

        top_cities = df['city'].value_counts().nlargest(10).index
        df['city_bucket'] = df['city'].where(df['city'].isin(top_cities), 'Other')

        global_mean = df['fill_rate'].mean()

        def track_record(row):
            others = df[(df['organizer_id'] == row['organizer_id']) & (df['event_id'] != row['event_id'])]
            return others['fill_rate'].mean() if len(others) > 0 else global_mean

        df['organizer_track_record'] = df.apply(track_record, axis=1)
        return df