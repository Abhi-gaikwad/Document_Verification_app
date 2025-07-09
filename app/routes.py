from flask import Flask, render_template, request
from app.verification.aadhaar_verifier import extract_aadhaar_data
from app.verification.pan_verifier import extract_pan_data
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'app/static/uploads'
app.secret_key = "supersecretkey"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/aadhaar')
def aadhaar():
    return render_template('aadhaar_form.html')

@app.route('/pan')
def pan():
    return render_template('pan_form.html')

@app.route('/verify_aadhaar', methods=['POST'])
def verify_aadhaar():
    name = request.form['name'].strip().lower()
    dob = request.form['dob'].strip()
    gender = request.form['gender'].strip().lower()
    file = request.files['aadhaar_file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    extracted_data = extract_aadhaar_data(file_path)

    user_data = {"name": name, "dob": dob, "gender": gender}

    verified = (
        name == extracted_data["name"].lower() and
        dob == extracted_data["dob"] and
        gender == extracted_data["gender"].lower()
    )

    return render_template('result.html', user_data=user_data, extracted_data=extracted_data, verified=verified)

@app.route('/verify_pan', methods=['POST'])
def verify_pan():
    name = request.form['name'].strip().lower()
    dob = request.form['dob'].strip()
    gender = request.form['gender'].strip().lower()
    file = request.files['pan_file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    extracted_data = extract_pan_data(file_path)

    user_data = {"name": name, "dob": dob, "gender": gender}

    verified = (
        name == extracted_data["name"].lower() and
        dob == extracted_data["dob"] and
        gender == extracted_data["gender"].lower()
    )

    return render_template('result.html', user_data=user_data, extracted_data=extracted_data, verified=verified)
