import os
import re
from datetime import datetime
from .document_ai_ocr import extract_text_with_document_ai  # Google Document AI

# --------- AADHAAR SPECIFIC LOGIC ---------
def is_aadhaar_card(text):
    keywords = ["aadhaar", "uidai", "government of india", "enrollment", "enrolment", "unique identification", "dob", "gender", "male", "female", "पुरुष", "महिला", "जन्म", "तारीख"]
    aadhaar_pattern = r'\b\d{4}\s?\d{4}\s?\d{4}\b'
    text_lower = text.lower()
    keyword_found = any(keyword in text_lower for keyword in keywords)
    aadhaar_number_found = re.search(aadhaar_pattern, text) is not None
    print(f"[DEBUG] Aadhaar Keyword Found: {keyword_found}, Aadhaar Number Pattern Found: {aadhaar_number_found}")
    if aadhaar_number_found and keyword_found:
        return True
    if "aadhaar" in text_lower:
        return True
    return False

def extract_aadhaar_details(text):
    extracted = {
        "aadhaar_number": None,
        "name": None,
        "dob": None,
        "gender": None
    }
    text_lines = text.split('\n')
    text_lower = text.lower()

    aadhaar_match = re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text)
    if aadhaar_match:
        extracted["aadhaar_number"] = aadhaar_match.group(0).replace(" ", "")

    name_keywords = ["name", "to", "रोहन"]
    dob_keywords = ["dob", "जन्म तारीख"]
    gender_keywords = ["male", "female", "पुरुष", "महिला"]
    name_candidates = []

    for i, line in enumerate(text_lines):
        line = line.strip()
        if not line:
            continue
        line_lower = line.lower()
        if "to" in text_lines[max(0, i-1)].lower() and len(line.split()) >= 2 and not any(kw in line_lower for kw in dob_keywords + gender_keywords):
            name_candidates.append(line)
        elif "name:" in text_lines[max(0, i-1)].lower() and len(line.split()) >= 2:
            name_candidates.append(line)
        elif "नाम:" in text_lines[max(0, i-1)].lower() and len(line.split()) >= 2:
            name_candidates.append(line)
        for kw in dob_keywords + gender_keywords:
            if kw in line_lower:
                for j in range(1, 3):
                    if i - j >= 0:
                        potential_name = text_lines[i-j].strip()
                        if re.match(r'^[A-Za-z\s\.]+$', potential_name) and len(potential_name.split()) >= 2:
                            name_candidates.append(potential_name)

    for line in text_lines:
        line_clean = line.strip()
        if re.match(r'^[A-Za-z\s\.]+$', line_clean) and len(line_clean.split()) >= 2:
            if not any(re.search(p, line_clean.lower()) for p in [
                r'government\s+of\s+india', r'unique\s+identification', r'authority', r'pin\s+code',
                r'mobile', r'dob', r'male', r'female', r'your\s+aadhaar']):
                if line_clean.istitle() or line_clean.isupper():
                    name_candidates.append(line_clean)

    if name_candidates:
        unique_candidates = list(set(name_candidates))
        unique_candidates.sort(key=lambda x: (x.istitle(), len(x)), reverse=True)
        selected_name = unique_candidates[0]
        selected_name = re.sub(r'[^A-Za-z\s]', '', selected_name)
        selected_name = re.sub(r'\s+', ' ', selected_name).strip()
        if "government" in selected_name.lower() or "india" in selected_name.lower():
            selected_name = None
        extracted["name"] = selected_name if selected_name else None

    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        if "dob" in line_lower or "जन्म तारीख" in line_lower:
            dob_match = re.search(r'(\d{2}[/-]\d{2}[/-](\d{4}))', line)
            if dob_match:
                extracted["dob"] = dob_match.group(1).replace('-', '/')
                break
            elif i + 1 < len(text_lines):
                dob_match_next_line = re.search(r'(\d{2}[/-]\d{2}[/-](\d{4}))', text_lines[i+1])
                if dob_match_next_line:
                    extracted["dob"] = dob_match_next_line.group(1).replace('-', '/')
                    break
        else:
            dob_match = re.search(r'(\d{2}[/-]\d{2}[/-](\d{4}))', line)
            if dob_match:
                try:
                    year = int(dob_match.group(2))
                    if 1900 < year <= datetime.now().year:
                        extracted["dob"] = dob_match.group(1).replace('-', '/')
                except:
                    pass

    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        if "male" in line_lower or "पुरुष" in line_lower:
            extracted["gender"] = "male"
            break
        elif "female" in line_lower or "महिला" in line_lower:
            extracted["gender"] = "female"
            break
        gender_match = re.search(r'\b(m|f)\b', line_lower)
        if gender_match:
            if gender_match.group(1) == 'm':
                extracted["gender"] = "male"
            elif gender_match.group(1) == 'f':
                extracted["gender"] = "female"
            break

    print(f"[DEBUG] Extracted Aadhaar Details: {extracted}")
    return extracted

# --------- MAIN ENTRY ---------
def extract_aadhaar_data(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    try:
        raw_ocr_text = extract_text_with_document_ai(file_path)
    except Exception as e:
        return {"extracted_data": {"error": f"Google Document AI failed: {str(e)}"}, "raw_ocr_text": "", "is_aadhaar": False}

    if not raw_ocr_text:
        return {"extracted_data": {"error": "No text found."}, "raw_ocr_text": "", "is_aadhaar": False}

    is_document_aadhaar = is_aadhaar_card(raw_ocr_text)

    if is_document_aadhaar:
        extracted_aadhaar_details = extract_aadhaar_details(raw_ocr_text)
    else:
        extracted_aadhaar_details = {"error": "This does not appear to be an Aadhaar card."}

    return {"extracted_data": extracted_aadhaar_details, "raw_ocr_text": raw_ocr_text, "is_aadhaar": is_document_aadhaar}
