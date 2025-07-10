from app.routes import app
import os

if __name__ == "__main__":
    # Ensure the upload directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, host="0.0.0.0", port=5000)