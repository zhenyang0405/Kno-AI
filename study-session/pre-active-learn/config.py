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
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_THINKING_MODEL = "gemini-3-pro-preview"
TEMPERATURE = 0.7
MAX_OUTPUT_TOKENS = 2048

# Content generation limits
MAX_TEXT_LENGTH = 1500  # characters
MAX_MATH_EXPRESSIONS = 20

# Active Learning Configuration
DEFAULT_ANCHOR_WIDTH = 40  # percentage
DEFAULT_WORKSHOP_WIDTH = 40  # percentage
DEFAULT_COPILOT_WIDTH = 20  # percentage

# Cache Configuration
CACHE_MODEL = "gemini-3-flash-preview"
CACHE_SYSTEM_INSTRUCTION = "You are an educational assistant analyzing this study material."

# Workspace State Constants
class WorkspaceState:
    READING = "reading"
    DEEP_DIVE = "deep_dive"
    INTERACTIVE = "interactive"
    SYNTHESIS = "synthesis"
    LOW_ENERGY = "low_energy"

class ConceptStatus:
    NOT_COVERED = "not_covered"
    IN_PROGRESS = "in_progress"
    WEAK = "weak"
    UNDERSTOOD = "understood"
    MASTERED = "mastered"

class ConceptSource:
    PRE_ASSESSMENT = "pre_assessment"
    MICRO_CHECKPOINT = "micro_checkpoint"
    POST_ASSESSMENT = "post_assessment"
    AI_EXPLANATION = "ai_explanation"
    USER_OVERRIDE = "user_override"

class EntryType:
    CHAT_USER = "chat_user"
    CHAT_AI = "chat_ai"
    NOTE = "note"
    AI_SUMMARY = "ai_summary"
    MICRO_CHECKPOINT = "micro_checkpoint"

class WorkshopContentType:
    TEXT = "text"
    ANIMATION = "animation"
    MATH = "math"
    CODE = "code"
    IMAGE = "image"
    VIDEO = "video"

class TriggerSource:
    USER_QUESTION = "user_question"
    AI_DECISION = "ai_decision"
    EXTRACTION_GESTURE = "extraction_gesture"
    USER_OVERRIDE = "user_override"

class ExtractedElementType:
    DIAGRAM = "diagram"
    EQUATION = "equation"
    CODE_BLOCK = "code_block"
    TABLE = "table"

class TransformedType:
    MODEL_3D = "3d_model"
    INTERACTIVE_DIAGRAM = "interactive_diagram"
    MATH_PLAYGROUND = "math_playground"
    CODE_PLAYGROUND = "code_playground"



