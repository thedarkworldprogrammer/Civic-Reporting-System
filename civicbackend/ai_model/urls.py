from django.urls import path
from .views import predict_issue

urlpatterns = [
    path('predict/', predict_issue, name='predict'),
]
