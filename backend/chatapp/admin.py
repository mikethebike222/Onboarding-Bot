from django.contrib import admin
from .models import ChatSession, ChatMessage, Vehicle

# Register your models here.
class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    readonly_fields = ['timestamp', 'role', 'content']
    extra = 0

class VehicleInline(admin.TabularInline):
    model = Vehicle
    readonly_fields = ['vin', 'use_type', 'blind_spot', 'commute_days', 'commute_miles', 'annual_mileage']
    extra = 0

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'email', 'current_step', 'is_complete', 'started_at']
    list_filter = ['is_complete', 'current_step', 'started_at']
    search_fields = ['full_name', 'email', 'zip_code']
    readonly_fields = ['id', 'started_at', 'completed_at']
    inlines = [ChatMessageInline, VehicleInline]

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'content', 'timestamp']
    list_filter = ['role', 'timestamp']
    search_fields = ['content']