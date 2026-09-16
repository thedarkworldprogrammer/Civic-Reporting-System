from django.contrib import admin
from .models import Department, Profile, Complaint, PredictionLog

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone")

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "status", "created_at")
    list_filter = ("department", "status")
    search_fields = ("title", "description")

@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = ("predicted_class", "confidence", "timestamp")

# If you want Profile in admin:
try:
    admin.site.register(Profile)
except Exception:
    pass
