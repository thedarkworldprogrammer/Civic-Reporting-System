from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta



class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username


class Complaint(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Solved', 'Solved'),
    ]

    title = models.CharField(max_length=200)
    predicted_class = models.CharField(max_length=100, blank=True, null=True)   # ✅ ADD THIS
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='complaint_images/')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    votes = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_complaints"
    )

    def __str__(self):
        return f"{self.title} - {self.status}"

class PredictionLog(models.Model):
    predicted_class = models.CharField(max_length=100)
    confidence = models.FloatField()
    image_path = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.predicted_class} ({self.confidence:.2f})"
    # complaints/models.py (append)

def generate_token():
    return uuid.uuid4().hex

def expiry_time():
    return timezone.now() + timedelta(hours=8)

class AdminSession(models.Model):
    username = models.CharField(max_length=150)
    token = models.CharField(max_length=64, unique=True, default=generate_token)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=expiry_time)

    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.username} - {self.token[:8]}"
class DepartmentAdmin(models.Model):
    department = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=100)  # store hashed later

    def __str__(self):
        return f"{self.username} ({self.department})"
class AdminUser(models.Model):
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=50)   # simple text for now
    department = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.username} ({self.department})"


