from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
import json

from .models import AdminSession, Complaint, Department

# -------------------------
# ADMIN LOGIN
# -------------------------
@csrf_exempt
def admin_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST request required"}, status=405)

    data = json.loads(request.body.decode("utf-8"))
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return JsonResponse({"error": "Missing credentials"}, status=400)

    try:
        user = User.objects.get(username=username)

        if not check_password(password, user.password):
            return JsonResponse({"error": "Invalid password"}, status=401)

        # Create session token
        session = AdminSession.objects.create(username=username)
        return JsonResponse({"token": session.token, "username": username})

    except User.DoesNotExist:
        return JsonResponse({"error": "Admin user not found"}, status=404)


# -------------------------
# ADMIN VALIDATE TOKEN
# -------------------------
def validate_admin_token(request):
    token = request.headers.get("Authorization")

    if not token:
        return JsonResponse({"valid": False})

    try:
        session = AdminSession.objects.get(token=token)

        if not session.is_valid():
            return JsonResponse({"valid": False})

        return JsonResponse({"valid": True, "username": session.username})

    except AdminSession.DoesNotExist:
        return JsonResponse({"valid": False})


# -------------------------
# ADMIN LOGOUT
# -------------------------
@csrf_exempt
def admin_logout(request):
    token = request.headers.get("Authorization")

    if not token:
        return JsonResponse({"error": "Token missing"}, status=400)

    try:
        session = AdminSession.objects.get(token=token)
        session.delete()
        return JsonResponse({"message": "Logged out"})
    except AdminSession.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=400)
