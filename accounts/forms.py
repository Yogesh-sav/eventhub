# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from events.models import Category
from .models import Profile


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=Profile.Role.choices, widget=forms.RadioSelect)
    email = forms.EmailField(required=True)
    agree_to_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must accept the Terms & Conditions to create an account.'}
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'role']

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.profile.role = self.cleaned_data['role']
            user.profile.save()
        return user


class OnboardingForm(forms.Form):
    interests = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )