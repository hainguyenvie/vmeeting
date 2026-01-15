import onnx
import os
import sys

# Define path to the model we downloaded
APP_DATA = os.path.join(os.environ.get("APPDATA", ""), "com.meetily.ai", "models", "speaker-recognition")
MODEL_PATH = os.path.join(APP_DATA, "sherpa-onnx-wespeaker-voxceleb-resnet34-2024-03-20", "voxceleb-resnet34-2023.onnx")

def add_meta_data(filename: str, meta_data: dict):
    """Adds metadata to an ONNX model.
    """
    print(f"Loading model from {filename}")
    model = onnx.load(filename)
    
    print("Existing metadata:")
    for prop in model.metadata_props:
        print(f"  {prop.key}: {prop.value}")
        
    print("\nAdding/Updating metadata:")
    for key, value in meta_data.items():
        print(f"  {key}: {value}")
        
        # Check if exists
        found = False
        for prop in model.metadata_props:
            if prop.key == key:
                prop.value = str(value)
                found = True
                break
        
        if not found:
            meta = model.metadata_props.add()
            meta.key = key
            meta.value = str(value)

    print(f"\nSaving model to {filename}")
    onnx.save(model, filename)
    print("SUCCESS: Metadata added successfully!")

def main():
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at: {MODEL_PATH}")
        sys.exit(1)

    # Metadata required by sherpa-onnx for wespeaker voxceleb resnet34
    # Ref: https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/wespeaker/add_meta_data.py
    # and intuition from similar models.
    meta_data = {
        "framework": "wespeaker",
        "model_type": "resnet34", # Important!
        "embedding_dim": "256",
        "comment": "wespeaker-voxceleb-resnet34-2024-03-20",
        "language": "multilingual",
        "input_sample_rate": "16000",
        "sample_rate": "16000", # Explicitly requested by sherpa-onnx
        "normalize_samples": "1", # wespeaker usually expects normalized input
        "output_dim": "256", # Required by sherpa-onnx
    }
    
    try:
        add_meta_data(MODEL_PATH, meta_data)
    except Exception as e:
        print(f"ERROR: Failed to add metadata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
