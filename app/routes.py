from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
# Correct import path based on your folder structure
from app.verification.pan_verifier import extract_pan_data

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
    This example specifically implements PAN verification.
    For Aadhaar, you would integrate a separate OCR/API logic.
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

        extracted_data_from_pan_verifier = {}
        raw_ocr_text = ""

        if doc_type == 'pan':
            result = extract_pan_data(filepath)
            extracted_data_from_pan_verifier = result["extracted_data"]
            raw_ocr_text = result["raw_ocr_text"]
        elif doc_type == 'aadhaar':
            # Placeholder: Call your Aadhaar verification logic here
            # For example: from app.verification.aadhaar_verifier import extract_aadhaar_data
            # result = extract_aadhaar_data(filepath)
            # extracted_data_from_pan_verifier = result["extracted_data"]
            # raw_ocr_text = result["raw_ocr_text"]
            extracted_data_from_pan_verifier = {"error": "Aadhaar verification logic not implemented yet."}
            raw_ocr_text = "" # No raw text if Aadhaar not implemented
        else:
            extracted_data_from_pan_verifier = {"error": "Invalid document type specified."}
            raw_ocr_text = ""

        # Clean up the uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

        is_verified = False
        status_message = "Verification Failed."

        if not extracted_data_from_pan_verifier.get("error"):
            # Basic comparison logic (you'll need to enhance this significantly)
            # For PAN, compare name, DOB, gender from extracted data with user input
            extracted_name = extracted_data_from_pan_verifier.get("name", "").strip().lower()
            extracted_dob = extracted_data_from_pan_verifier.get("dob", "").strip()
            extracted_gender = extracted_data_from_pan_verifier.get("gender", "").strip().lower()

            # Prepare user input for comparison
            user_name_lower = user_name.strip().lower()
            user_gender_lower = user_gender.strip().lower()

            # Name comparison: Case-insensitive and handles variations with/without spaces
            # Checks if user's name is in extracted name, or vice versa, or if they match after removing spaces
            name_match = (user_name_lower in extracted_name) or \
                         (extracted_name in user_name_lower) or \
                         (user_name_lower.replace(" ", "") == extracted_name.replace(" ", ""))

            dob_match = (user_dob == extracted_dob)
            
            # Gender comparison: Flexible for 'f'/'m' or 'female'/'male'
            gender_match = (user_gender_lower == extracted_gender) or \
                           (user_gender_lower == 'female' and extracted_gender == 'f') or \
                           (user_gender_lower == 'f' and extracted_gender == 'female') or \
                           (user_gender_lower == 'male' and extracted_gender == 'm') or \
                           (user_gender_lower == 'm' and extracted_gender == 'male')


            if name_match and dob_match and gender_match:
                is_verified = True
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
            status_message = extracted_data_from_pan_verifier.get("error", "An unknown error occurred during processing.")


        return jsonify({
            "entered_data": {
                "name": user_name,
                "dob": user_dob,
                "gender": user_gender
            },
            "extracted_data": extracted_data_from_pan_verifier,
            "raw_ocr_text": raw_ocr_text, # Include raw OCR text here
            "is_verified": is_verified,
            "status_message": status_message
        })
    return jsonify({"error": "File upload failed"}), 500