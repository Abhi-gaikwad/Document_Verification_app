import os
from google.cloud import documentai_v1 as documentai

# Dynamically construct the path to the JSON file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Goes up from /verification
KEY_PATH = os.path.join(BASE_DIR, "credentials", "supple-tracker-465911-a0-1365f4685754.json")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH

PROJECT_ID = "supple-tracker-465911-a0"
LOCATION = "us"
PROCESSOR_ID = "b9ca8e5b6dea7715"

def extract_text_with_document_ai(file_path: str):
    client = documentai.DocumentProcessorServiceClient()
    name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

    mime_map = {
        '.pdf': "application/pdf",
        '.jpg': "image/jpeg",
        '.jpeg': "image/jpeg",
        '.png': "image/png"
    }
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = mime_map.get(ext)
    if not mime_type:
        raise Exception(f"Unsupported file format: {ext}")

    with open(file_path, "rb") as f:
        file_content = f.read()

    document = {"content": file_content, "mime_type": mime_type}
    result = client.process_document(request={"name": name, "raw_document": document})
    return result.document.text
