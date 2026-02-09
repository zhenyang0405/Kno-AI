import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")

# Google Cloud Storage Configuration
# Google Cloud Storage Configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCS_SERVICE_ACCOUNT_PATH = os.getenv("GCS_SERVICE_ACCOUNT_PATH", "")
GCS_SERVICE_ACCOUNT_BASE64 = os.getenv("GCS_SERVICE_ACCOUNT_BASE64", "")
