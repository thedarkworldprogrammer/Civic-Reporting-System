from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('api/complaints/', include('complaints.urls')),   # correct
    path('api/admin/', include('complaints.admin_urls')),  # correct
]
