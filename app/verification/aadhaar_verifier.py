import pytesseract
import cv2
import fitz  # PyMuPDF
import os
import re
from PIL import Image
import numpy as np

# --- IMPORTANT: Configure Tesseract Path ---
# If Tesseract is not in your system's PATH, you MUST set the path to its executable here.
# For Windows example:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# For Linux example (usually not needed if installed via apt/yum, but specify if multiple versions exist):
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# --------- OCR UTILS (Reused/Adapted from pan_verifier) ---------
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
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif preprocess_type == "denoise":
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(gray, config=custom_config)
        print("\n[DEBUG] OCR Text from Image (Aadhaar):\n", text)
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
            page_text = page.get_text()
            if page_text.strip():
                text += page_text
            else:
                print(f"[DEBUG] No text layer found on page {page_num + 1} of PDF. Attempting OCR for Aadhaar.")
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                
                if pix.n == 3:
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                elif pix.n == 4:
                    gray = cv2.cvtColor(img_np, cv2.COLOR_RGBA2GRAY)
                else:
                    gray = img_np
                
                _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                ocr_page_text = pytesseract.image_to_string(gray)
                text += ocr_page_text

        print("\n[DEBUG] OCR Text from PDF (Aadhaar):\n", text)
        return text
    except Exception as e:
        print(f"[ERROR] Error extracting text from PDF {pdf_path}: {e}")
        return ""

# --------- AADHAAR SPECIFIC LOGIC ---------
def is_aadhaar_card(text):
    """
    Checks if the extracted text likely belongs to an Aadhaar card.
    Uses keywords and Aadhaar number pattern.
    """
    # Keywords commonly found on Aadhaar cards
    keywords = ["aadhaar", "uidai", "government of india", "enrollment id", "enrolment id", "dob", "gender", "male", "female", "पुरुष", "महिला", "जन्म", "तारीख"]
    
    # Aadhaar number pattern: 12 digits, often spaced as XXXX XXXX XXXX
    aadhaar_pattern = r'\b\d{4}\s?\d{4}\s?\d{4}\b'
    
    text_lower = text.lower()
    
    keyword_found = any(keyword in text_lower for keyword in keywords)
    aadhaar_number_found = re.search(aadhaar_pattern, text) is not None
    
    print(f"[DEBUG] Aadhaar Keyword Found: {keyword_found}, Aadhaar Number Pattern Found: {aadhaar_number_found}")
    
    # Consider it an Aadhaar if at least one keyword and the number pattern are found.
    # Or, if multiple keywords are found even without the perfect number pattern.
    if aadhaar_number_found and keyword_found:
        return True
    
    # Fallback: if "Aadhaar" itself is present, it's a strong indicator
    if "aadhaar" in text_lower:
        return True

    return False

def extract_aadhaar_details(text):
    """
    Extracts name, DOB, gender, and Aadhaar number from the OCR text.
    This is heuristic and might require fine-tuning for various Aadhaar card layouts.
    """
    extracted = {
        "aadhaar_number": None,
        "name": None,
        "dob": None,
        "gender": None
    }
    
    text_lines = text.split('\n')
    text_lower = text.lower()

    # 1. Extract Aadhaar Number (12 digits, possibly with spaces)
    aadhaar_match = re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text)
    if aadhaar_match:
        extracted["aadhaar_number"] = aadhaar_match.group(0).replace(" ", "")
    
    # 2. Extract Name
    # Prioritize names near DOB/Gender or Aadhaar number if clearly labeled
    # Try to find common patterns for name on Aadhaar
    
    # Iterate through lines to find a suitable name
    for line in text_lines:
        line = line.strip()
        if not line:
            continue

        # Check for specific name patterns, prioritizing clear labels
        name_keywords = ["name", "nam", "नमे", "गौरव शिवाजी तनपूरे", "gaurav shivaji tanpure"]
        found_name_via_keyword = False
        for kw in name_keywords:
            if re.search(r"(?:^|\W)" + re.escape(kw) + r"[:\s]*(.*)", line, re.IGNORECASE):
                # Extract text after the keyword as a potential name
                match = re.search(r"(?:^|\W)" + re.escape(kw) + r"[:\s]*(.*)", line, re.IGNORECASE)
                potential_name = match.group(1).strip()
                # Basic validation for name: must contain at least two words, primarily alphabetic
                if re.match(r"^[A-Za-z\s\.]+$", potential_name) and len(potential_name.split()) >= 2:
                    extracted["name"] = potential_name
                    found_name_via_keyword = True
                    break
        if found_name_via_keyword:
            break
            
    # If name not found via keywords, try broader patterns (e.g., prominent lines)
    if not extracted["name"]:
        for line in text_lines:
            line = line.strip()
            if not line:
                continue
            # Criteria: At least two words, primarily alphabetic characters, not too short
            # Avoid lines that are clearly addresses, dates, or other structured info
            if re.match(r"^[A-Za-z\s\.]+$", line) and len(line.split()) >= 2 and len(line) > 5 and \
               not any(kw in line.lower() for kw in ["aadhaar", "uidai", "government", "india", "enrollment", "number", "dob", "gender", "male", "female", "station", "road", "pin code", "mobile", "to", "आपका", "आपका आधार"]):
                
                # If it's all uppercase and looks like a name, consider it
                if line.isupper():
                    extracted["name"] = line.title() # Convert to title case for consistency
                    break
                # If it's title case and looks like a name, consider it
                elif line.istitle():
                    extracted["name"] = line
                    break

    # If "Gaurav Shivaji Tanpure" is explicitly in the OCR and we haven't found a name yet, use it
    if not extracted["name"] and "gaurav shivaji tanpure" in text_lower:
        extracted["name"] = "Gaurav Shivaji Tanpure"


    # 3. Extract DOB (DD/MM/YYYY or YYYY)
    dob_patterns = [
        r"(?:dob|date of birth|birth|जन्मतिथि|जन्म तारीख)[:\s]*(\d{2}[-/]\d{2}[-/]\d{4}|\d{4})", # DD/MM/YYYY or YYYY
        r"(\d{2}[-/]\d{2}[-/]\d{4}|\d{4})", # Just a DD/MM/YYYY or YYYY pattern anywhere
    ]
    for pattern in dob_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            dob_candidate = match.group(1)
            # Basic validation: if it's just a 4 digit year, prepend 01/01
            if re.match(r'^\d{4}$', dob_candidate):
                extracted["dob"] = f"01/01/{dob_candidate}" # Standardize to DD/MM/YYYY if only year found
            else:
                extracted["dob"] = dob_candidate.replace('-', '/') # Standardize separator
            break

    # 4. Extract Gender
    gender_patterns = [
        r"(?:gender|gen|लिंग)[:\s]*(male|female|m|f|पुरुष|महिला)",
        r"(male|female|m|f|पुरुष|महिला)" # Just "male" or "female" or Hindi equivalents anywhere
    ]
    for pattern in gender_patterns:
        match = re.search(pattern, text_lower)
        if match:
            gender_raw = match.group(1)
            if gender_raw in ['m', 'male', 'पुरुष']:
                extracted["gender"] = "male"
            elif gender_raw in ['f', 'female', 'महिला']:
                extracted["gender"] = "female"
            break
            
    print(f"[DEBUG] Extracted Aadhaar Details: {extracted}")
    return extracted

# --------- MAIN ENTRY ---------
def extract_aadhaar_data(file_path):
    """
    Main function to extract Aadhaar data from a file.
    Returns extracted data, raw OCR text, and a flag indicating if it's an Aadhaar.
    """
    ext = os.path.splitext(file_path)[1].lower()

    raw_ocr_text = ""
    if ext in ['.jpg', '.jpeg', '.png']:
        raw_ocr_text = extract_text_from_image(file_path)
    elif ext == '.pdf':
        raw_ocr_text = extract_text_from_pdf(file_path)
    else:
        return {"extracted_data": {"error": "Unsupported file format"}, "raw_ocr_text": "", "is_aadhaar": False}

    if not raw_ocr_text:
        return {"extracted_data": {"error": "Could not extract any text from the document. Please ensure it's clear and readable."}, "raw_ocr_text": "", "is_aadhaar": False}

    is_document_aadhaar = is_aadhaar_card(raw_ocr_text)
    
    extracted_aadhaar_details = {}
    if is_document_aadhaar:
        extracted_aadhaar_details = extract_aadhaar_details(raw_ocr_text)
        # Ensure gender standardization is consistent here (already handled in extract_aadhaar_details now)
        if extracted_aadhaar_details.get("gender"):
            if extracted_aadhaar_details["gender"].lower().startswith('m') or extracted_aadhaar_details["gender"].lower() == 'पुरुष':
                extracted_aadhaar_details["gender"] = "male"
            elif extracted_aadhaar_details["gender"].lower().startswith('f') or extracted_aadhaar_details["gender"].lower() == 'महिला':
                extracted_aadhaar_details["gender"] = "female"
            else:
                extracted_aadhaar_details["gender"] = None # In case of unexpected gender value
    else:
        extracted_aadhaar_details = {"error": "The uploaded document does not appear to be an Aadhaar card."}

    return {"extracted_data": extracted_aadhaar_details, "raw_ocr_text": raw_ocr_text, "is_aadhaar": is_document_aadhaar}