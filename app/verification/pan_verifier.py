import os
import re
import requests
from dotenv import load_dotenv
from .document_ai_ocr import extract_text_with_document_ai  # Google OCR

load_dotenv()
API_TOKEN = os.getenv("VITE_SUREPASS_BEARER_TOKEN")

def extract_pan_number(text):
    pan_match = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text)
    pan = pan_match.group(0) if pan_match else None
    print(f"\n[DEBUG] Extracted PAN Number: {pan}")
    return pan

def call_surepass_api(pan_number):
    print(f"\n[DEBUG] Calling Surepass API for PAN: {pan_number}")
    url = "https://sandbox.surepass.io/api/v1/pan/pan-comprehensive"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"id_number": pan_number}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        print(f"[DEBUG] Surepass API Response: {data}")
        if data.get("success") and data.get("data"):
            result = data["data"]
            return {
                "name": result.get("full_name", "").strip(),
                "dob": result.get("dob", "").strip(),
                "gender": result.get("gender", "").strip().lower(),
                "pan_number": pan_number,
                "aadhaar_linked": result.get("aadhaar_linked", None)
            }
        return {"error": data.get("message", "API verification failed"), "pan_number": pan_number, "aadhaar_linked": None}
    except requests.exceptions.Timeout:
        return {"error": "API request timed out", "pan_number": pan_number, "aadhaar_linked": None}
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {e}", "pan_number": pan_number, "aadhaar_linked": None}
    except Exception as e:
        return {"error": str(e), "pan_number": pan_number, "aadhaar_linked": None}

# --------- MAIN ENTRY ---------
def extract_pan_data(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    try:
        raw_ocr_text = extract_text_with_document_ai(file_path)
    except Exception as e:
        return {"extracted_data": {"error": f"Google Document AI failed: {str(e)}"}, "raw_ocr_text": ""}

    if not raw_ocr_text:
        return {"extracted_data": {"error": "No text found."}, "raw_ocr_text": ""}

    pan_number = extract_pan_number(raw_ocr_text)

    if not pan_number:
        surepass_result = {"error": "PAN number not found in document."}
    else:
        surepass_result = call_surepass_api(pan_number)

    surepass_result.setdefault("aadhaar_linked", None)
    return {"extracted_data": surepass_result, "raw_ocr_text": raw_ocr_text}
