import tensorflow as tf
import os

# Path to your model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.h5")
FIXED_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model_fixed.h5")

print(f"🔍 Loading model from: {MODEL_PATH}")

try:
    model = tf.keras.models.load_model(MODEL_PATH)
    print("✅ Model loaded successfully!")

    # If model has multiple inputs, fix it
    if isinstance(model.input, list) and len(model.input) > 1:
        print(f"⚙️ Model has {len(model.input)} inputs — keeping only the first one.")

        # Use only the first input
        new_input = model.input[0]
        new_output = model.output

        # Rebuild single-input model
        fixed_model = tf.keras.Model(inputs=new_input, outputs=new_output)
        fixed_model.save(FIXED_MODEL_PATH)
        print(f"✅ Fixed model saved at: {FIXED_MODEL_PATH}")
    else:
        print("✅ Model already has a single input — nothing to fix.")
        model.save(FIXED_MODEL_PATH)

except Exception as e:
    print(f"❌ Error loading or fixing model: {e}")
