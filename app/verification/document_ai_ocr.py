import os
import json
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Google Cloud configuration
PROJECT_ID = "supple-tracker-465911-a0"
LOCATION = "us"
PROCESSOR_ID = "b9ca8e5b6dea7715"

# Load credentials from environment variable
raw_creds = os.environ["GOOGLE_CREDENTIALS_JSON"]
service_account_info = json.loads(raw_creds)

# Replace escaped newline characters with actual newlines for private_key
service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

# Create credentials object
credentials = service_account.Credentials.from_service_account_info(service_account_info)

def extract_text_with_document_ai(file_path: str):
    # Create a client using the credentials
    client = documentai.DocumentProcessorServiceClient(credentials=credentials)
    processor_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

    # Determine the file type
    mime_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png"
    }

    ext = os.path.splitext(file_path)[1].lower()
    mime_type = mime_map.get(ext)

    if not mime_type:
        raise Exception(f"Unsupported file format: {ext}")

    # Read file content
    with open(file_path, "rb") as f:
        file_content = f.read()

    # Prepare document payload
    document = {"content": file_content, "mime_type": mime_type}

    # Send request to Document AI
    response = client.process_document(request={"name": processor_path, "raw_document": document})

    # Return extracted text
    return response.document.text
