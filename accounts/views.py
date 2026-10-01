# accounts/views.py
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from .forms import OnboardingForm
from .forms import SignUpForm
from django.contrib import messages


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('accounts:onboarding')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def onboarding(request):
    if request.user.profile.onboarding_completed:
        return redirect('core:home')

    if request.method == 'POST':
        form = OnboardingForm(request.POST)
        if form.is_valid():
            request.user.profile.interests.set(form.cleaned_data['interests'])
            request.user.profile.onboarding_completed = True
            request.user.profile.save()
            messages.success(request, 'Thanks! We\u2019ll use this to personalize your recommendations.')
            return redirect('core:home')
    else:
        form = OnboardingForm()
    return render(request, 'accounts/onboarding.html', {'form': form})