from django.conf import settings
from django.db import models

# Create your models here.

class Profile(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ORGANIZER = 'organizer', 'Organizer'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    city = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    interests = models.ManyToManyField('events.Category', blank=True, related_name='interested_profiles')
    onboarding_completed = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} ({self.role})'

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANIZER

