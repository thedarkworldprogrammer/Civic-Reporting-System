from django.http import JsonResponse
from tensorflow.keras.preprocessing import image
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from django.views.decorators.csrf import csrf_exempt

import os
import io

# ---------- Load Model ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.h5")

print("📌 Loading AI Model from:", MODEL_PATH)

try:
    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    print("✅ Model loaded successfully!")
except Exception as e:
    print("❌ ERROR loading model:", e)
    model = None


CLASS_LABELS = [
    "potholes",
    "streetlight",
    "trash_bins",
    "unknown",
    "water_leakage"
]

IMG_HEIGHT = 224
IMG_WIDTH = 224


@csrf_exempt
# ---------- Prediction API ----------
def predict_issue(request):

    if request.method != "POST":
        return JsonResponse({"error": "POST request required"}, status=405)

    if model is None:
        return JsonResponse({"error": "AI model not loaded"}, status=500)

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    try:
        # Load image
        img = image.load_img(io.BytesIO(uploaded_file.read()), target_size=(IMG_HEIGHT, IMG_WIDTH))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        processed = preprocess_input(img_array)

        # Predict
        preds = model.predict(processed)

        # Debug prints (NOW preds exists)
        print("DEBUG prediction shape:", preds.shape)
        print("DEBUG values:", preds)

        # If model returns shape (1,5)
        preds = preds[0]

        index = np.argmax(preds)
        confidence = float(preds[index])
        predicted_class = CLASS_LABELS[index]

        return JsonResponse({
            "predicted_class": predicted_class,
            "confidence": confidence
        })

    except Exception as e:
        print("❌ Prediction error:", e)
        return JsonResponse({"error": str(e)}, status=500)
