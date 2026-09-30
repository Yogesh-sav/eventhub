from django.db import models
from events.models import Event
# Create your models here.

class PopularityPrediction(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='popularity_prediction')
    predicted_label = models.BooleanField()  # True = predicted popular
    predicted_probability = models.FloatField()  # model's confidence, 0-1
    model_version = models.CharField(max_length=50)
    predicted_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.event.title}: {"popular" if self.predicted_label else "not popular"} ({self.predicted_probability:.0%})'