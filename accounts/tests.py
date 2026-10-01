from django.test import TestCase
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import Profile

# Create your tests here.

class SignupTests(TestCase):
    def test_signup_creates_user_and_profile(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'newuser', 'email': 'new@example.com',
            'password1': 'ComplexPass123!', 'password2': 'ComplexPass123!',
            'role': Profile.Role.USER,
        })
        self.assertTrue(User.objects.filter(username='newuser').exists())
        user = User.objects.get(username='newuser')
        self.assertEqual(user.profile.role, Profile.Role.USER)

    def test_signup_redirects_to_onboarding(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'newuser2', 'email': 'new2@example.com',
            'password1': 'ComplexPass123!', 'password2': 'ComplexPass123!',
            'role': Profile.Role.ORGANIZER,
        })
        self.assertRedirects(response, reverse('accounts:onboarding'))

    def test_signup_assigns_organizer_role_correctly(self):
        self.client.post(reverse('accounts:signup'), {
            'username': 'orguser', 'email': 'org@example.com',
            'password1': 'ComplexPass123!', 'password2': 'ComplexPass123!',
            'role': Profile.Role.ORGANIZER,
        })
        user = User.objects.get(username='orguser')
        self.assertTrue(user.profile.is_organizer)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testlogin', password='pass12345')

    def test_login_succeeds_with_correct_credentials(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testlogin', 'password': 'pass12345',
        })
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_fails_with_wrong_password(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testlogin', 'password': 'wrongpassword',
        })
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_clears_session(self):
        self.client.login(username='testlogin', password='pass12345')
        self.client.post(reverse('accounts:logout'))
        response = self.client.get(reverse('events:dashboard'))
        self.assertNotEqual(response.status_code, 200)  # redirected to login, not authenticated


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='onboarder', password='pass12345')

    def test_onboarding_page_requires_login(self):
        response = self.client.get(reverse('accounts:onboarding'))
        self.assertNotEqual(response.status_code, 200)  # redirected to login

    def test_completed_onboarding_redirects_home(self):
        self.user.profile.onboarding_completed = True
        self.user.profile.save()
        self.client.login(username='onboarder', password='pass12345')
        response = self.client.get(reverse('accounts:onboarding'))
        self.assertRedirects(response, reverse('core:home'))