from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    # USER COMPLAINT APIs
    path("api/complaints/create/", views.create_complaint, name="create_complaint"),
    path("api/complaints/all/", views.list_all_complaints, name="all_complaints"),
    path("api/complaints/department/<str:dept_slug>/", views.list_complaints_by_department, name="list_by_dept"),
    path("api/complaints/update-status/<int:complaint_id>/", views.update_complaint_status, name="update_status"),


    # ADMIN APIs
    path("admin/login/", admin_views.admin_login),
    path("admin/logout/", admin_views.admin_logout),
    path("admin/validate/", admin_views.validate_admin_token),
]
