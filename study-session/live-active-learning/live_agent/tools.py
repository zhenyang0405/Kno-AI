"""
Live Active Learning Tools

Implements tools for the live active learning agent to interact with the database:
1. get_user_preferences - Get user learning preferences
2. get_study_session - Retrieve study session details
3. get_material_concepts - Retrieve concepts for a material
4. get_material_context_cache - Retrieve active cache for a material
5. update_user_understanding - Update a student's understanding summary for a concept
6. get_user_firebase_uid - Get a user's Firebase UID from the users table
7. generate_image - Generate an image using Gemini and upload to GCS
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import sys
import os
import uuid
from datetime import datetime, timedelta

from google import genai
from google.cloud import storage
from google.oauth2 import service_account
import base64

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, GCS_BUCKET_NAME, GCS_SERVICE_ACCOUNT_BASE64

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)



def initialize_gcs_bucket():
    """Initialize Google Cloud Storage bucket."""
    gcs_cred_path = config.GCS_SERVICE_ACCOUNT_PATH
    gcs_base64 = config.GCS_SERVICE_ACCOUNT_BASE64

    client = None

    # 1. Try Base64 Env Var
    if gcs_base64:
        try:
            info = json.loads(base64.b64decode(gcs_base64))
            creds = service_account.Credentials.from_service_account_info(info)
            client = storage.Client(credentials=creds)
            print("[GCS] Using Base64 credentials")
        except Exception as e:
            print(f"[GCS] Error loading Base64 credentials: {e}")

    # 2. Try File Path
    if not client:
        if gcs_cred_path and os.path.exists(gcs_cred_path):
            print(f"[GCS] Using service account from: {gcs_cred_path}")
            client = storage.Client.from_service_account_json(gcs_cred_path)
        else:
            # 3. Fallback to Default Credentials
            print("[GCS] Using default credentials")
            client = storage.Client()
    
    if client:
        try:
            # Log the service account email being used
            email = getattr(client._credentials, 'service_account_email', 'Unknown')
            print(f"[GCS] Initialized with service account email: {email}")
        except Exception as e:
            print(f"[GCS] Could not determine service account email: {e}")

    return client.bucket(config.GCS_BUCKET_NAME)


# Initialize GCS bucket
gcs_bucket = initialize_gcs_bucket()


def get_db_connection():
    """Create database connection with RealDictCursor for dict results"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT,
        cursor_factory=RealDictCursor
    )


def get_user_preferences(user_id: int) -> str:
    """
    Get user learning preferences from user_preferences table.

    Args:
        user_id: ID of the user

    Returns:
        JSON string with user preferences grouped by category
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT category, preference_data
            FROM user_preferences
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY updated_at DESC
        """, (user_id,))

        preferences = cursor.fetchall()
        cursor.close()
        conn.close()

        if preferences:
            # Group preferences by category
            prefs_dict = {}
            for pref in preferences:
                category = pref['category']
                data = pref['preference_data']
                
                # If category already exists, merge the data
                if category in prefs_dict:
                    if isinstance(prefs_dict[category], dict) and isinstance(data, dict):
                        prefs_dict[category].update(data)
                    else:
                        prefs_dict[category] = data
                else:
                    prefs_dict[category] = data
            
            return json.dumps({"success": True, "preferences": prefs_dict})
        else:
            # No preferences found - agent should have no restrictions
            return json.dumps({
                "success": True, 
                "preferences": {}, 
                "note": "No user preferences found. Generate responses without preference restrictions."
            })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def get_study_session(session_id: int) -> str:
    """
    Retrieve study session details.

    Args:
        session_id: ID of the study session

    Returns:
        JSON string with session details including user_id, material_id, 
        weak_concepts, status, and timestamps
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, material_id, pre_assessment_id, post_assessment_id,
                   weak_concepts, status, started_at, completed_at, created_at, updated_at
            FROM study_sessions
            WHERE id = %s
        """, (session_id,))

        session = cursor.fetchone()
        cursor.close()
        conn.close()

        if session:
            # Convert datetime objects to strings
            session_dict = dict(session)
            for key in ['started_at', 'completed_at', 'created_at', 'updated_at']:
                if session_dict[key]:
                    session_dict[key] = session_dict[key].isoformat()
            
            return json.dumps({"success": True, "session": session_dict})
        else:
            return json.dumps({"success": False, "error": "Study session not found"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def get_material_concepts(material_id: int) -> str:
    """
    Retrieve all concepts for a material.

    Args:
        material_id: ID of the material

    Returns:
        JSON string with list of concepts including concept_id, concept_name,
        description, user_understanding, page ranges, and prerequisites
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, material_id, concept_id, concept_name, description,
                   user_understanding, page_start, page_end, prerequisite_concepts, created_at
            FROM material_concepts
            WHERE material_id = %s
            ORDER BY page_start
        """, (material_id,))

        concepts = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert datetime objects to strings
        concepts_list = []
        for concept in concepts:
            concept_dict = dict(concept)
            if concept_dict['created_at']:
                concept_dict['created_at'] = concept_dict['created_at'].isoformat()
            concepts_list.append(concept_dict)

        return json.dumps({"success": True, "concepts": concepts_list, "count": len(concepts_list)})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def get_material_context_cache(material_id: int) -> str:
    """
    Retrieve the active context cache for a material.

    Args:
        material_id: ID of the material

    Returns:
        JSON string with cache details including cache_name, created_at,
        expires_at, and status. Returns the most recent active cache.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, material_id, cache_name, created_at, expires_at, status
            FROM material_context_caches
            WHERE material_id = %s AND status = 'active' AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
        """, (material_id,))

        cache = cursor.fetchone()
        cursor.close()
        conn.close()

        if cache:
            # Convert datetime objects to strings
            cache_dict = dict(cache)
            for key in ['created_at', 'expires_at']:
                if cache_dict[key]:
                    cache_dict[key] = cache_dict[key].isoformat()
            
            return json.dumps({"success": True, "cache": cache_dict})
        else:
            return json.dumps({"success": True, "cache": None, "message": "No active cache found"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def update_user_understanding(material_concept_id: int, understanding_summary: str) -> str:
    """
    Update the user_understanding text summary for a specific material concept.

    Args:
        material_concept_id: The primary key (id) of the row in material_concepts
        understanding_summary: A descriptive text summary of the student's current
            understanding of this concept. Should be specific about what the student
            does and doesn't understand, including abilities, struggles, and
            misconceptions observed.

    Returns:
        JSON string with the updated concept id, concept_name, and
        user_understanding, or an error message.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE material_concepts
            SET user_understanding = %s
            WHERE id = %s
            RETURNING id, concept_name, user_understanding
        """, (understanding_summary, material_concept_id))

        updated = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if updated:
            return json.dumps({"success": True, "updated_concept": dict(updated)})
        else:
            return json.dumps({"success": False, "error": f"No material_concept found with id {material_concept_id}"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def get_user_firebase_uid(user_id: int) -> str:
    """
    Get a user's Firebase UID from the users table.

    Args:
        user_id: ID of the user

    Returns:
        JSON string with the user's firebase_uid, or an error message.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, firebase_uid
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return json.dumps({"success": True, "user_id": user['id'], "firebase_uid": user['firebase_uid']})
        else:
            return json.dumps({"success": False, "error": f"No user found with id {user_id}"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def generate_image(prompt: str, firebase_uid: str) -> str:
    """
    Generate an image using Gemini and upload it to Google Cloud Storage.

    Args:
        prompt: Text description of the image to generate. Should be detailed
            and descriptive, specifying what the image should show including
            labels, layout, and educational purpose.
        firebase_uid: The user's Firebase UID, used to organize uploaded
            images under the user's GCS path. Obtain this by calling
            get_user_firebase_uid first.

    Returns:
        JSON string with image_url (public GCS URL) and caption (any text
        Gemini produced alongside the image), or an error message.
    """
    try:
        logger.info(f"[generate_image] Called with prompt='{prompt[:80]}...', firebase_uid='{firebase_uid}'")

        # Validate inputs
        if not GCS_BUCKET_NAME:
            logger.error("[generate_image] ERROR: GCS_BUCKET_NAME is not set")
            return json.dumps({"success": False, "error": "GCS_BUCKET_NAME environment variable is not set"})
        if not firebase_uid:
            logger.error("[generate_image] ERROR: firebase_uid is empty")
            return json.dumps({"success": False, "error": "firebase_uid is required"})

        # Generate image with Gemini
        logger.info("[generate_image] Calling Gemini API...")
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
        )

        # Check response validity
        if not response.candidates:
            logger.error(f"[generate_image] ERROR: No candidates in response. Prompt feedback: {response.prompt_feedback}")
            return json.dumps({"success": False, "error": "No candidates returned. The prompt may have been blocked."})

        if not response.parts:
            logger.error(f"[generate_image] ERROR: No parts in response. Finish reason: {response.candidates[0].finish_reason}")
            return json.dumps({"success": False, "error": f"Empty response. Finish reason: {response.candidates[0].finish_reason}"})

        # Extract caption and image bytes from response parts
        caption = ""
        image_bytes = None
        mime_type = "image/png"

        for part in response.parts:
            if part.text is not None:
                caption = part.text
                logger.info(f"[generate_image] Got caption: '{caption[:100]}'")
            elif part.inline_data is not None:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/png"
                logger.info(f"[generate_image] Got image: {len(image_bytes)} bytes, mime_type={mime_type}")

        if not image_bytes:
            logger.error("[generate_image] ERROR: Response had parts but no image data")
            return json.dumps({"success": False, "error": "No image was generated by the model"})

        # Upload to GCS
        logger.info(f"[generate_image] Uploading to GCS bucket '{GCS_BUCKET_NAME}'...")
        extension = mime_type.split("/")[-1] if mime_type else "png"
        blob_name = f"users/{firebase_uid}/images/{uuid.uuid4()}.{extension}"
        blob = gcs_bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        # Generate signed URL (valid for 7 days)
        # Note: This requires the service account credential to be loaded in the client
        
        # Debugging: Log what we are using to sign
        try:
            signing_email = getattr(gcs_bucket.client._credentials, 'service_account_email', None)
            logger.info(f"[generate_image] Signing URL with email: {signing_email}")
        except:
            pass

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(days=1),
            method="GET",
            service_account_email=None, # Let the client determine this from credentials
            access_token=None,
        )

        logger.info(f"[generate_image] Upload complete. Signed URL generated: {signed_url}")
        return json.dumps({
            "success": True,
            "image_url": signed_url,
            "caption": caption,
        })

    except Exception as e:
        logger.error(f"[generate_image] EXCEPTION: {type(e).__name__}: {e}", exc_info=True)
        return json.dumps({"success": False, "error": f"{type(e).__name__}: {e}"})
