from tensorflow.keras.models import load_model
import numpy as np
import tensorflow as tf
from PIL import Image

MODEL_PATH = "ai_model/model.h5"
model = load_model(MODEL_PATH)

LABELS = ["potholes", "streetlight", "trash_bins", "water_leakage", "unknown"]

def classify_image(image_path):
    img = Image.open(image_path).resize((224, 224))
    img = np.array(img) / 255.0
    img = img.reshape(1, 224, 224, 3)

    predictions = model.predict(img)
    index = np.argmax(predictions)
    confidence = float(np.max(predictions))

    return LABELS[index], confidence
