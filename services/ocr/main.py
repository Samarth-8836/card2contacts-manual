from fastapi import FastAPI, UploadFile, File
from paddleocr import PaddleOCR
import numpy as np
import cv2
import io
from PIL import Image
import json
import logging

# Initialize FastAPI
app = FastAPI(title="Standard OCR Service")

# --- INITIALIZATION ---
print("⏳ Loading OCR Model... (This may take ~30s to download on first run)")

# Initialize Global OCR Engine
# enable_mkldnn=True provides CPU acceleration. 
# Because we set OMP_NUM_THREADS=1 in Dockerfile, this is safe.
ocr_engine = PaddleOCR(
    use_angle_cls=True, 
    lang='en', 
    use_gpu=False,
    show_log=False, # We will handle logging manually
    enable_mkldnn=True 
)

print("✅ OCR Model Loaded and Ready.")

@app.get("/health")
def health():
    return {"status": "ocr_ready"}

@app.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    print(f"\n[{file.filename}] Processing...")
    
    # 1. Read and Convert Image
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    img_np = np.array(image)
    # RGB to BGR for OpenCV/Paddle
    img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # 2. Run Inference
    # cls=True enables angle classification (for rotated cards)
    result = ocr_engine.ocr(img_np, cls=True)

    extracted_data = []
    full_text = ""
    
    # 3. Parse Results
    # Structure: [ [ [ [x,y],..], ("text", conf) ], ... ]
    if result and result[0]:
        print(f"[{file.filename}] Raw Lines Detected:")
        print("-" * 40)
        
        for line in result[0]:
            coords = line[0]
            text = line[1][0]
            confidence = line[1][1]
            
            # Log specific line to console
            print(f"  -> ({confidence:.2f}) {text}")
            
            extracted_data.append({
                "text": text, 
                "conf": round(confidence, 4),
                "box": coords
            })
            full_text += text + " "
            
        print("-" * 40)
    else:
        print(f"[{file.filename}] No text detected.")

    # 4. Construct Response
    response_payload = {
        "full_text": full_text.strip(),
        "details": extracted_data
    }
    
    # 5. Full JSON Output Logging (As requested)
    # This prints the final JSON sent to the backend
    print(f"[{file.filename}] Full Output JSON:")
    print(json.dumps(response_payload, indent=2))
    print("=" * 60 + "\n")

    return response_payload