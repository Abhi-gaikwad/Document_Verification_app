import pytesseract
import cv2
import fitz  # PyMuPDF
import os
import re
from PIL import Image
import numpy as np
from datetime import datetime # Import datetime for better date handling

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
    keywords = ["aadhaar", "uidai", "government of india", "enrollment", "enrolment", "unique identification", "dob", "gender", "male", "female", "पुरुष", "महिला", "जन्म", "तारीख"]
    
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
    
    # 2. Extract Name - Enhanced Logic
    name_keywords = ["name", "to", "रोहन"] # Added common pre-name indicators
    dob_keywords = ["dob", "जन्म तारीख"]
    gender_keywords = ["male", "female", "पुरुष", "महिला"]
    
    name_candidates = []
    
    for i, line in enumerate(text_lines):
        line = line.strip()
        if not line:
            continue
            
        line_lower = line.lower()

        # Look for name directly after "To" or "Name:" or similar patterns
        if "to" in text_lines[max(0, i-1)].lower() and len(line.split()) >= 2 and not any(kw in line_lower for kw in dob_keywords + gender_keywords):
            name_candidates.append(line)
        elif "name:" in text_lines[max(0, i-1)].lower() and len(line.split()) >= 2 and not any(kw in line_lower for kw in dob_keywords + gender_keywords):
            name_candidates.append(line)
        elif "नाम:" in text_lines[max(0, i-1)].lower() and len(line.split()) >= 2 and not any(kw in line_lower for kw in dob_keywords + gender_keywords):
            name_candidates.append(line)

        # Look for names directly above DOB or Gender
        # Iterate backwards from DOB/Gender lines to find name
        for kw in dob_keywords + gender_keywords:
            if kw in line_lower:
                for j in range(1, 3): # Check 1 or 2 lines above
                    if i - j >= 0:
                        potential_name = text_lines[i-j].strip()
                        potential_name_lower = potential_name.lower()
                        # Ensure it's not another known field or a generic phrase
                        if re.match(r'^[A-Za-z\s\.]+$', potential_name) and \
                           len(potential_name.split()) >= 2 and \
                           not any(exclude_kw in potential_name_lower for exclude_kw in ["government", "india", "authority", "identification", "enrollment", "enrolment", "pin code", "mobile", "address", "state", "district", "village"]):
                            name_candidates.append(potential_name)
    
    # Also look for a strong name pattern (e.g., Title Case, multiple words, not a common keyword)
    for line in text_lines:
        line_clean = line.strip()
        line_clean_lower = line_clean.lower()
        if re.match(r'^[A-Za-z\s\.]+$', line_clean) and len(line_clean.split()) >= 2:
            # Exclude known non-name lines
            exclude_patterns = [
                r'government\s+of\s+india', r'unique\s+identification', r'authority\s+of\s+india',
                r'enrollment\s+no', r'enrolment\s+no', r'station\s+road', r'pin\s+code',
                r'sub\s+district', r'district', r'state', r'vtc', r'po', r'mobile',
                r'dob', r'male', r'female', r'your\s+aadhaar', r'validity\s+unknown'
            ]
            if not any(re.search(pattern, line_clean_lower) for pattern in exclude_patterns):
                if line_clean.istitle() or line_clean.isupper(): # Prefer title case or all caps for names
                    name_candidates.append(line_clean)

    if name_candidates:
        # Sort by length (longer often better) and prioritize title case
        unique_candidates = list(set(name_candidates))
        unique_candidates.sort(key=lambda x: (x.istitle(), len(x)), reverse=True) # Prioritize title-case and then length
        
        selected_name = ""
        if unique_candidates:
            selected_name = unique_candidates[0]

        selected_name = re.sub(r'[^A-Za-z\s]', '', selected_name) # Remove non-alphabetic, non-space
        selected_name = re.sub(r'\s+', ' ', selected_name).strip() # Normalize spaces
        
        # Heuristic to remove common OCR errors seen in "Government of India" area
        if "government" in selected_name.lower() or "india" in selected_name.lower() or "serene" in selected_name.lower() :
            selected_name = None # Discard if it looks like the header
        
        extracted["name"] = selected_name if selected_name else None # Ensure it's None if empty after cleaning


    # 3. Extract DOB - Improved patterns and context
    dob_found = False
    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        # Look for "DOB:" or "जन्म तारीख:"
        if "dob" in line_lower or "जन्म तारीख" in line_lower:
            # Look for date in the same line or next line
            dob_match = re.search(r'(\d{2}[/-]\d{2}[/-](\d{4}))', line) # Capture year in group 2
            if dob_match:
                extracted["dob"] = dob_match.group(1).replace('-', '/')
                dob_found = True
                break # Found a DOB with a label, prioritize it
            elif i + 1 < len(text_lines):
                dob_match_next_line = re.search(r'(\d{2}[/-]\d{2}[/-](\d{4}))', text_lines[i+1]) # Capture year in group 2
                if dob_match_next_line:
                    extracted["dob"] = dob_match_next_line.group(1).replace('-', '/')
                    dob_found = True
                    break # Found a DOB with a label, prioritize it
        
        # Fallback: Just look for a date pattern if no explicit label found yet and not yet found
        if not dob_found:
            dob_match = re.search(r'(\d{2}[/-]\d{2}[/-](\d{4}))', line) # Capture year in group 2
            if dob_match:
                dob_candidate = dob_match.group(1)
                try:
                    year_str = dob_match.group(2) # Access group 2 for the year
                    year = int(year_str)
                    current_year = datetime.now().year
                    # Basic validation: DOB should be reasonable (e.g., not future, not too old)
                    if 1900 < year <= current_year: # Assuming DOB between 1900 and current year
                        extracted["dob"] = dob_candidate.replace('-', '/')
                        dob_found = True
                        # Don't break immediately, might find a more specific DOB label later if multiple dates exist
                except (ValueError, IndexError):
                    # Handle cases where year extraction or conversion fails
                    pass
    
    # If a DOB was found but not explicitly labeled, we might need to verify its context.
    # For robust production systems, consider a stricter validation or context check here.

    # 4. Extract Gender - Improved logic
    gender_found = False
    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        if "male" in line_lower or "पुरुष" in line_lower:
            # Ensure it's not part of an address or other non-gender text
            if not any(addr_word in line_lower for addr_word in ['road', 'district', 'state', 'pin', 'code', 'vtc', 'po']):
                extracted["gender"] = "male"
                gender_found = True
                break
        elif "female" in line_lower or "महिला" in line_lower:
            if not any(addr_word in line_lower for addr_word in ['road', 'district', 'state', 'pin', 'code', 'vtc', 'po']):
                extracted["gender"] = "female"
                gender_found = True
                break
        # Sometimes gender is just "M" or "F" next to DOB, or a standalone line
        if not gender_found:
            gender_match = re.search(r'\b(m|f)\b', line_lower) # Look for standalone 'm' or 'f'
            if gender_match:
                # Add context check: Is it near a DOB or name?
                # This makes it more likely to be a gender indicator
                is_near_dob_or_name = False
                for j in range(max(0, i-2), min(len(text_lines), i+3)):
                    if j != i:
                        if any(kw in text_lines[j].lower() for kw in dob_keywords + name_keywords):
                            is_near_dob_or_name = True
                            break
                
                if is_near_dob_or_name:
                    if gender_match.group(1) == 'm':
                        extracted["gender"] = "male"
                        gender_found = True
                        break
                    elif gender_match.group(1) == 'f':
                        extracted["gender"] = "female"
                        gender_found = True
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
    else:
        extracted_aadhaar_details = {"error": "The uploaded document does not appear to be an Aadhaar card."}

    return {"extracted_data": extracted_aadhaar_details, "raw_ocr_text": raw_ocr_text, "is_aadhaar": is_document_aadhaar}