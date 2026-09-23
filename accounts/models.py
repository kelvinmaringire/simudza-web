from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password

from wagtail.images.models import Image


class CustomUser(AbstractUser):
    dob = models.DateField(null=True, blank=True)
    sex_choices = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    sex = models.CharField(max_length=1, choices=sex_choices, null=True, blank=True)
    physical_address = models.TextField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    pic = models.OneToOneField(Image, on_delete=models.SET_NULL, null=True, blank=True, related_name='profile_user')
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        # Hash password if it's in plain text
        if not self.password.startswith('pbkdf2_sha256$'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)
