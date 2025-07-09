from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
# Correct import path based on your folder structure
from app.verification.pan_verifier import extract_pan_data
from app.verification.aadhaar_verifier import extract_aadhaar_data # Import aadhaar verifier
import re # Import re for regex in routes

app = Flask(__name__, template_folder='templates') # Corrected templates folder path
app.config['UPLOAD_FOLDER'] = 'uploads/' # Create this folder in your project root

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def index():
    """Renders the main index page."""
    return render_template('index.html')

@app.route('/verify-document', methods=['POST'])
def verify_document():
    """
    Handles document verification requests (PAN or Aadhaar).
    """
    if 'document' not in request.files:
        return jsonify({"error": "No document file provided"}), 400

    file = request.files['document']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    doc_type = request.form.get('docType') # 'pan' or 'aadhaar'
    user_name = request.form.get('name')
    user_dob = request.form.get('dob')
    user_gender = request.form.get('gender')

    if not all([doc_type, user_name, user_dob, user_gender]):
        return jsonify({"error": "Missing form data (docType, name, dob, gender)"}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        extracted_data_for_response = {}
        raw_ocr_text = ""
        is_document_verified = False
        status_message = ""

        if doc_type == 'pan':
            result = extract_pan_data(filepath)
            extracted_data_for_response = result["extracted_data"]
            raw_ocr_text = result["raw_ocr_text"]

            if not extracted_data_for_response.get("error"):
                extracted_name = extracted_data_for_response.get("name", "").strip().lower()
                extracted_dob = extracted_data_for_response.get("dob", "").strip()
                extracted_gender = extracted_data_for_response.get("gender", "").strip().lower()

                user_name_lower = user_name.strip().lower()
                user_gender_lower = user_gender.strip().lower()

                name_match = (user_name_lower in extracted_name) or \
                             (extracted_name in user_name_lower) or \
                             (user_name_lower.replace(" ", "") == extracted_name.replace(" ", ""))

                dob_match = (user_dob == extracted_dob)
                
                gender_match = (user_gender_lower == extracted_gender) or \
                               (user_gender_lower == 'female' and extracted_gender == 'f') or \
                               (user_gender_lower == 'f' and extracted_gender == 'female') or \
                               (user_gender_lower == 'male' and extracted_gender == 'm') or \
                               (user_gender_lower == 'm' and extracted_gender == 'male')

                if name_match and dob_match and gender_match:
                    is_document_verified = True
                    status_message = "Document Successfully Verified! All entered details match extracted details."
                else:
                    mismatch_details = []
                    if not name_match:
                        mismatch_details.append("Name mismatch.")
                    if not dob_match:
                        mismatch_details.append("Date of Birth mismatch.")
                    if not gender_match:
                        mismatch_details.append("Gender mismatch.")
                    status_message = "Information mismatch: " + " ".join(mismatch_details)
            else:
                status_message = extracted_data_for_response.get("error", "An unknown error occurred during PAN processing.")

        elif doc_type == 'aadhaar':
            result = extract_aadhaar_data(filepath)
            extracted_data_for_response = result["extracted_data"]
            raw_ocr_text = result["raw_ocr_text"]
            is_aadhaar_document = result["is_aadhaar"] # Flag from aadhaar_verifier

            if not is_aadhaar_document:
                is_document_verified = False
                status_message = extracted_data_for_response.get("error", "The uploaded document could not be identified as an Aadhaar card.")
            elif extracted_data_for_response.get("error"):
                is_document_verified = False
                status_message = extracted_data_for_response.get("error", "An unknown error occurred during Aadhaar extraction.")
            else:
                extracted_name = extracted_data_for_response.get("name", "").strip().lower()
                extracted_dob = extracted_data_for_response.get("dob", "").strip()
                extracted_gender = extracted_data_for_response.get("gender", "").strip().lower()

                user_name_lower = user_name.strip().lower()
                # Format user DOB to match expected DD/MM/YYYY if it's YYYY-MM-DD
                user_dob_formatted = user_dob
                if re.match(r'^\d{4}-\d{2}-\d{2}$', user_dob):
                    parts = user_dob.split('-')
                    user_dob_formatted = f"{parts[2]}/{parts[1]}/{parts[0]}"
                
                user_gender_lower = user_gender.strip().lower()

                name_match = (user_name_lower in extracted_name) or \
                             (extracted_name in user_name_lower) or \
                             (user_name_lower.replace(" ", "") == extracted_name.replace(" ", ""))

                dob_match = (user_dob_formatted == extracted_dob)
                
                gender_match = (user_gender_lower == extracted_gender) or \
                               (user_gender_lower == 'female' and extracted_gender == 'f') or \
                               (user_gender_lower == 'f' and extracted_gender == 'female') or \
                               (user_gender_lower == 'male' and extracted_gender == 'm') or \
                               (user_gender_lower == 'm' and extracted_gender == 'male')

                if name_match and dob_match and gender_match:
                    is_document_verified = True
                    status_message = "Aadhaar Card Successfully Verified! All entered details match extracted details."
                else:
                    mismatch_details = []
                    if not name_match:
                        mismatch_details.append("Name mismatch.")
                    if not dob_match:
                        mismatch_details.append("Date of Birth mismatch.")
                    if not gender_match:
                        mismatch_details.append("Gender mismatch.")
                    status_message = "Information mismatch: " + " ".join(mismatch_details)
        else:
            is_document_verified = False
            status_message = "Invalid document type specified."

        # Clean up the uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

        return jsonify({
            "entered_data": {
                "name": user_name,
                "dob": user_dob,
                "gender": user_gender
            },
            "extracted_data": extracted_data_for_response,
            "raw_ocr_text": raw_ocr_text,
            "is_verified": is_document_verified,
            "status_message": status_message
        })
    return jsonify({"error": "File upload failed"}), 500