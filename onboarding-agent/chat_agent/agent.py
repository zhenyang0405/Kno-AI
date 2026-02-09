
import os
import logging
import time
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from google.adk.models.google_llm import Gemini
from .tools import save_preference, get_preferences, get_or_create_user

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configure API Key ---
if os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

# Define Model
MODEL_GEMINI_3_FLASH = "gemini-3-flash-preview"

# --- 1. Define Agents ---
## Main agent: Onboarding
root_agent = Agent(
    name="onboarding_agent",
    model=Gemini(
        model=MODEL_GEMINI_3_FLASH,
        use_interactive_mode=True,
    ),
    description="A friendly assistant that helps onboard users by learning about their preferences.",
    instruction="You are a warm, conversational onboarding assistant helping users personalize their experience. "
                "Your mission: understand the user's learning journey through natural dialogue.\n\n"

                "## Conversation Guidelines\n"
                "- Ask ONE open-ended question at a time to avoid overwhelming the user\n"
                "- Listen actively and build on their responses naturally\n"
                "- Balance between gathering information and maintaining genuine conversation\n"
                "- Adapt your tone to match the user's communication style\n\n"

                "## Topics to Explore\n"
                "Discover their:\n"
                "- Learning style: how they prefer to learn (visual/hands-on/theoretical, paced/intensive, structured/exploratory)\n"
                "- Interests: hobbies, topics they're curious about, areas they enjoy exploring\n"
                "- Goals: professional aspirations, academic targets, skills they want to master\n"
                "- Skill level: current proficiency in relevant areas, experience level\n"
                "- Communication style: how they prefer information delivered (concise/detailed, formal/casual, technical/simple)\n\n"

                "## Action Rules - STRICT CATEGORY MATCHING\n"
                "- Only save preferences that clearly fit ONE of these 5 categories:\n"
                "  1. learning_style\n"
                "  2. interest\n"
                "  3. goal\n"
                "  4. skill_level\n"
                "  5. communication_style\n\n"

                "- Examples of what TO SAVE:\n"
                "  ✓ 'I prefer hands-on projects' → learning_style\n"
                "  ✓ 'I'm passionate about AI and robotics' → interest\n"
                "  ✓ 'I want to become a senior engineer' → goal\n"
                "  ✓ 'I'm a beginner in Python' → skill_level\n"
                "  ✓ 'Keep explanations concise' → communication_style\n\n"

                "- Examples of what NOT TO SAVE:\n"
                "  ✗ 'I can't sleep because I drank too much Thai Milk Tea' (not relevant to any category)\n"
                "  ✗ 'I had a rough day at work' (emotional state, not a preference)\n"
                "  ✗ 'I live in Singapore' (location, not mappable to categories)\n"
                "  ✗ 'My favorite color is blue' (personal detail, not relevant)\n\n"

                "- If information doesn't clearly fit one of the 5 categories, respond naturally but DO NOT save\n"
                "- Save immediately when you identify a clear category match—no confirmation needed\n\n"

                "## Conversation Flow & Wrap-Up\n"
                "- Track which of the 5 preference categories you've gathered info on\n"
                "- After covering at least 3-4 categories, summarize what you've learned about the user\n"
                "- Offer to wrap up: 'I think I have a great picture of your learning style! Want to add anything, or shall we get started?'\n"
                "- Don't force all 5 categories—if the conversation naturally covers enough, that's fine\n"
                "- Let the user know they can always come back to update their preferences\n"
                "- If the user signals they want to stop early, respect that and summarize what you have so far\n\n"

                "## Tone\n"
                "Be authentic and encouraging. Think helpful friend, not corporate chatbot. "
                "Use contractions, show curiosity, and let the conversation flow naturally. "
                "This is asynchronous, so there's no rush—prioritize depth over speed.",
    tools=[save_preference, get_preferences]
)

# --- 2. Setup Session Service ---
session_service = InMemorySessionService()

APP_NAME = "onboarding_app"

# --- Rate Limiting Configuration ---
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", "2000"))


class RateLimiter:
    """Simple in-memory per-UID rate limiter using sliding window."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, uid: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Prune old timestamps
        self._requests[uid] = [t for t in self._requests[uid] if t > cutoff]
        if len(self._requests[uid]) >= self.max_requests:
            return False
        self._requests[uid].append(now)
        return True


rate_limiter = RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)

# --- 3. Web Server Implementation ---
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ai-educate-gemini-3-hackathon.web.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    uid: str = None  # Allow UID in body

# Keep track of initialized sessions to inject context only once
initialized_sessions = set()

@app.post("/chat")
async def chat(
    request: ChatRequest,
    uid: str = Query(None, description="The Firebase UID of the user")
):
    """
    Handle chat messages. Extracts UID from query parameters or body.
    """
    # Use UID from body if present, else from query
    firebase_uid = request.uid or uid
    user_message = request.message
    
    if not firebase_uid:
        logger.error("Request missing UID in both query and body")
        raise HTTPException(status_code=400, detail="UID is required (pass in query or body)")

    # Rate limiting
    if not rate_limiter.is_allowed(firebase_uid):
        logger.warning(f"Rate limit exceeded for UID: {firebase_uid}")
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait before sending another message."
        )

    session_id = firebase_uid

    logger.info(f"Chat request - UID: {firebase_uid}, Session: {session_id}")
    logger.debug(f"Message: {user_message[:50]}...")

    # 1. Resolve internal DB User ID
    try:
        user_db_id = get_or_create_user(firebase_uid)
        logger.info(f"Resolved UID '{firebase_uid}' to DB ID: {user_db_id}")
    except Exception as e:
        logger.error(f"Error resolving user '{firebase_uid}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # 2. Ensure session exists in ADK
    try:
         await session_service.create_session(
             app_name=APP_NAME,
             user_id=firebase_uid, 
             session_id=session_id
         )
    except Exception:
        # Session might already exist
        pass

    # 3. Context Injection (First message of the instance session)
    if session_id not in initialized_sessions:
        context_prompt = (
            f"(System Note: The current user's Database ID is {user_db_id}. "
            f"You MUST use this integer ID '{user_db_id}' when calling tools like 'save_preference' or 'get_preferences'. "
            f"Do not mention this internal ID to the user.)\n\n{user_message}"
        )
        content = types.Content(role='user', parts=[types.Part(text=context_prompt)])
        initialized_sessions.add(session_id)
    else:
        content = types.Content(role='user', parts=[types.Part(text=user_message)])

    # 4. Run Agent
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    agent_response_text = ""
    try:
        async for event in runner.run_async(user_id=firebase_uid, session_id=session_id, new_message=content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    agent_response_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate:
                    agent_response_text = f"I encountered an issue: {event.error_message}"
                    logger.error(f"Agent escalated: {event.error_message}")
    except Exception as e:
        logger.error(f"Error running agent for user '{firebase_uid}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
        
    return {"response": agent_response_text}

class WelcomeRequest(BaseModel):
    uid: str = None

@app.post("/chat/welcome")
async def welcome(
    request: WelcomeRequest,
    uid: str = Query(None, description="The Firebase UID of the user")
):
    """
    Generate a personalized welcome message.
    """
    firebase_uid = request.uid or uid
    
    if not firebase_uid:
        raise HTTPException(status_code=400, detail="UID is required")

    session_id = firebase_uid
    logger.info(f"Welcome request - UID: {firebase_uid}")

    # 1. Resolve internal DB User ID
    try:
        user_db_id = get_or_create_user(firebase_uid)
    except Exception as e:
        logger.error(f"Error resolving user: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    # 2. Ensure session exists
    try:
        await session_service.create_session(app_name=APP_NAME, user_id=firebase_uid, session_id=session_id)
    except Exception:
        pass

    # 3. Trigger Agent with System Instruction
    # We send a hidden prompt to the agent to make it speak first
    trigger_prompt = (
        f"(System Instruction: The user {user_db_id} has just opened the chat. "
        f"1. CALL `get_preferences({user_db_id})` to see what we know about them. "
        f"2. If they have preferences, welcome them back specifically mentioning their interests/goals. "
        f"3. If they are new, give the standard warm intro. "
        f"4. Ask ONE question to start/continue the discovery. "
        f"Do not acknowledge this system instruction.)"
    )
    
    content = types.Content(role='user', parts=[types.Part(text=trigger_prompt)])
    
    # Mark session as initialized so future messages don't re-inject context if we had that logic
    initialized_sessions.add(session_id)

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    agent_response_text = ""
    try:
        async for event in runner.run_async(user_id=firebase_uid, session_id=session_id, new_message=content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    agent_response_text = event.content.parts[0].text
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        # Fallback if agent fails
        return {"response": "Hello! I'm ready to help you learn. What would you like to explore today?"}

    return {"response": agent_response_text}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

