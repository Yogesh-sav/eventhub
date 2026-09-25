# events/forms.py
from django import forms
from django.forms import inlineformset_factory

from .models import Event, TicketType


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'category', 'venue', 'city',
                   'date', 'start_time', 'end_time', 'image', 'status']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


TicketTypeFormSet = inlineformset_factory(
    Event,
    TicketType,
    fields=['name', 'price', 'quantity_total'],
    extra=1,
    can_delete=True,
)