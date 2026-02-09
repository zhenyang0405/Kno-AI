import os
from dotenv import load_dotenv

load_dotenv()

# Firebase Configuration (Auth only)
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")

# Google Cloud Storage Configuration
GCS_SERVICE_ACCOUNT_PATH = os.getenv("GCS_SERVICE_ACCOUNT_PATH")  # Optional: dedicated GCS service account
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# PostgreSQL Configuration
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")

# CORS Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
# Add common local development origins by default
DEFAULT_ORIGINS = [
    FRONTEND_URL,
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "https://ai-educate-gemini-3-hackathon.web.app",
    "https://ai-educate-gemini-3-hackathon.firebaseapp.com"
]
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(",")
ALLOWED_ORIGINS = [url.strip() for url in ALLOWED_ORIGINS if url.strip()]

# File Upload Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = set(os.getenv("ALLOWED_FILE_EXTENSIONS", "pdf,jpg,jpeg,png,txt,doc,docx").split(","))

# Validation Constraints
MAX_KNOWLEDGE_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500
MAX_USER_INPUT_LENGTH = 5000
