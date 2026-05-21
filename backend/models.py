from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

# Create your models here.
class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("analyst", "Analyst")
    ]

    google_id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="analyst"),
    avatar_url = models.URLField(blank=True)
    google_login = models.CharField(max_length=50, blank=True)

    def__str__(self):
        return f"{self.username} ({self.role})"
