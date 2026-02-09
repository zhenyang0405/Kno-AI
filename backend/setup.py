import firebase_admin
from firebase_admin import credentials
from google.cloud import storage
from google.oauth2 import service_account
import os
import json
import base64
from dotenv import load_dotenv
import config

load_dotenv()

def initialize_firebase_auth():
    """Initialize Firebase for Auth only."""
    # 1. Try Base64 Env Var (for Cloud Run without Secret Manager)
    firebase_base64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if firebase_base64:
        try:
            cred_dict = json.loads(base64.b64decode(firebase_base64))
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin initialized with Base64 credentials")
            return
        except Exception as e:
            print(f"❌ Error loading Firebase Base64 credentials: {e}")

    # 2. Try File Path
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print(f"✅ Firebase Admin initialized with file: {cred_path}")
    else:
        # 3. Fallback to Default Credentials (Workload Identity)
        print("⚠️ No Firebase credentials found, using default credentials")
        firebase_admin.initialize_app()

def initialize_gcs_bucket():
    """Initialize Google Cloud Storage bucket."""
    client = None
    
    # 1. Try Base64 Env Var
    gcs_base64 = os.getenv("GCS_SERVICE_ACCOUNT_BASE64")
    if gcs_base64:
        try:
            info = json.loads(base64.b64decode(gcs_base64))
            creds = service_account.Credentials.from_service_account_info(info)
            client = storage.Client(credentials=creds)
            print("✅ GCS Client initialized with Base64 credentials")
        except Exception as e:
            print(f"❌ Error loading GCS Base64 credentials: {e}")

    # 2. Try File Path
    if not client:
        gcs_cred_path = os.getenv("GCS_SERVICE_ACCOUNT_PATH")
        if gcs_cred_path and os.path.exists(gcs_cred_path):
            client = storage.Client.from_service_account_json(gcs_cred_path)
            print(f"✅ GCS Client initialized with file: {gcs_cred_path}")
        else:
            # 3. Fallback to Default Credentials
            print("⚠️ No GCS credentials found, using default credentials")
            client = storage.Client()
    
    return client.bucket(config.GCS_BUCKET_NAME)

# Initialize Firebase Auth
initialize_firebase_auth()

# Initialize GCS bucket
bucket = initialize_gcs_bucket()

def set_bucket_cors(bucket_obj):
    """Sets the CORS configuration for the bucket."""
    print(f"Setting CORS for bucket: {bucket_obj.name}")
    cors_configuration = [
        {
            "origin": ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "https://ai-educate-gemini-3-hackathon.web.app"],
            "method": ["GET", "HEAD", "OPTIONS"],
            "responseHeader": ["Content-Type", "Access-Control-Allow-Origin", "Authorization", "x-goog-resumable"],
            "maxAgeSeconds": 3600
        }
    ]
    bucket_obj.cors = cors_configuration
    bucket_obj.patch()
    print(f"✅ CORS configuration set for bucket {bucket_obj.name}")

if bucket:
    try:
        set_bucket_cors(bucket)
    except Exception as e:
        print(f"❌ Failed to set CORS: {e}")


