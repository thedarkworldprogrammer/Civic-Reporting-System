from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static




urlpatterns = [
    path("create/", views.create_complaint),
    path("department/<str:dept_slug>/", views.list_complaints_by_department),
    path("admin/login/", views.admin_login), 
    path("predict/", views.predict_image, name="predict"),
    path("counts/", views.complaint_counts),
    path(
        "<int:complaint_id>/update-status/",
        views.update_complaint_status,
        name="update_complaint_status"
    ),
    path("all/", views.list_all_complaints),
     path(
        "<int:complaint_id>/vote-up/",
        views.vote_up_complaint,
        name="vote_up_complaint"
    ),
    path("heatmap/", views.complaint_heatmap_data),
    path("check-duplicate/", views.check_duplicate_complaint),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)