import pytesseract
import cv2
import fitz  # PyMuPDF
import os
import re
import requests
from dotenv import load_dotenv
from PIL import Image
import numpy as np # Import numpy for image processing

# --- IMPORTANT: Configure Tesseract Path ---
# If Tesseract is not in your system's PATH, you MUST set the path to its executable here.
# For Windows example:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# For Linux example (usually not needed if installed via apt/yum, but specify if multiple versions exist):
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

load_dotenv()
API_TOKEN = os.getenv("VITE_SUREPASS_BEARER_TOKEN")

# --------- OCR UTILS ---------
def extract_text_from_image(image_path, preprocess_type="threshold"):
    """
    Extracts text from an image using Tesseract OCR with optional preprocessing.
    preprocess_type can be "none", "threshold", "denoise".
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise Exception(f"Image cannot be read from path: {image_path}. Check file existence and permissions.")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if preprocess_type == "threshold":
            # Apply binary thresholding with OTSU's method for automatic thresholding
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif preprocess_type == "denoise":
            # Apply non-local means denoising
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        # Add more preprocessing steps as needed (e.g., deskewing, scaling)

        # Tesseract configuration for better accuracy (optional)
        # 'psm 6' assumes a single uniform block of text. 'psm 3' is default (fully automatic page segmentation).
        # 'oem 3' uses the default OCR engine mode.
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(gray, config=custom_config)
        print("\n[DEBUG] OCR Text from Image:\n", text)
        return text
    except Exception as e:
        print(f"[ERROR] Error extracting text from image {image_path}: {e}")
        return ""

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a PDF. If the PDF is scanned (image-based),
    it will attempt to OCR each page.
    """
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            # Try to get text layer first (for searchable PDFs)
            page_text = page.get_text()
            if page_text.strip(): # If text is found, append it
                text += page_text
            else: # No text layer, so it's likely a scanned PDF, OCR it
                print(f"[DEBUG] No text layer found on page {page_num + 1} of PDF. Attempting OCR.")
                # Render page to an image (at 2x resolution for better OCR)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                
                # Convert to grayscale for OCR
                if pix.n == 3: # RGB
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                elif pix.n == 4: # RGBA
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGBA2GRAY)
                else: # Grayscale
                    gray = img_np
                
                # Apply preprocessing for OCR on the image
                _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                ocr_page_text = pytesseract.image_to_string(gray)
                text += ocr_page_text

        print("\n[DEBUG] OCR Text from PDF:\n", text)
        return text
    except Exception as e:
        print(f"[ERROR] Error extracting text from PDF {pdf_path}: {e}")
        return ""

def extract_pan_number(text):
    """
    Extracts PAN number using a regex pattern.
    """
    # Regex for PAN number: 5 uppercase letters, 4 digits, 1 uppercase letter
    pan_match = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text)
    pan = pan_match.group(0) if pan_match else None
    print(f"\n[DEBUG] Extracted PAN Number: {pan}")
    return pan

# --------- API ---------
def call_surepass_api(pan_number):
    """
    Calls the Surepass API to verify the PAN number.
    """
    print(f"\n[DEBUG] Calling Surepass API for PAN: {pan_number}")
    # IMPORTANT: Ensure this URL matches your Surepass token's environment (sandbox or production)
    # Using the production URL as a default suggestion based on previous error
    url = "https://sandbox.surepass.io/api/v1/pan/pan-comprehensive" # Example: production URL
    # If your token is for sandbox, use: url = "https://sandbox.surepass.io/api/v1/pan/pan" 
    
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
                "pan_number": pan_number
            }
        # If API call was successful but data not found or other API error message
        return {"error": data.get("message", "API verification failed"), "pan_number": pan_number}
    except requests.exceptions.Timeout:
        return {"error": "API request timed out", "pan_number": pan_number}
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {e}", "pan_number": pan_number}
    except Exception as e:
        return {"error": str(e), "pan_number": pan_number}

# --------- MAIN ENTRY ---------
def extract_pan_data(file_path):
    """
    Main function to extract PAN data from a file and verify it.
    Returns extracted data and raw OCR text.
    """
    ext = os.path.splitext(file_path)[1].lower()

    raw_ocr_text = ""
    if ext in ['.jpg', '.jpeg', '.png']:
        raw_ocr_text = extract_text_from_image(file_path)
    elif ext == '.pdf':
        raw_ocr_text = extract_text_from_pdf(file_path)
    else:
        return {"extracted_data": {"error": "Unsupported file format"}, "raw_ocr_text": ""}

    if not raw_ocr_text:
        return {"extracted_data": {"error": "Could not extract any text from the document. Please ensure it's clear and readable."}, "raw_ocr_text": ""}

    pan_number = extract_pan_number(raw_ocr_text)

    surepass_result = {}
    if not pan_number:
        surepass_result = {"error": "PAN number not found in document. Please ensure it's clearly visible."}
    else:
        surepass_result = call_surepass_api(pan_number)
    
    return {"extracted_data": surepass_result, "raw_ocr_text": raw_ocr_text}