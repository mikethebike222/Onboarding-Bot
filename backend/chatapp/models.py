from django.db import models

# Create your models here.
from django.contrib.auth.models import User
import uuid

class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    zip_code = models.CharField(max_length=5,null=True)
    full_name = models.CharField(max_length=200, null=True)
    email = models.EmailField(null=True)
    license_type = models.CharField(max_length=20,null=True)
    license_status = models.CharField(max_length=20, null=True, blank=True)
    
    current_step = models.CharField(max_length=50, default='zip')
    is_complete = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-started_at']

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']

class Vehicle(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='vehicles')
    vin = models.CharField(max_length=200)
    use_type = models.CharField(max_length=50)
    blind_spot = models.CharField(max_length=20)
    commute_days = models.CharField(max_length=50, null=True, blank=True)
    commute_miles = models.CharField(max_length=50, null=True, blank=True)
    annual_mileage = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['vin']