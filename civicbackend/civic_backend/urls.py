from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('health/', health_check),
    path('api/complaints/', include('complaints.urls')),   # correct
    path('api/admin/', include('complaints.admin_urls')),  # correct
]
