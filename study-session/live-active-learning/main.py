import asyncio
import json
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from google.adk.agents.live_request_queue import LiveRequestQueue
from live_agent.agent import tutor_agent

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "ai-educate"
# USER_ID = "test_user"
# SESSION_ID = "audio_session"

app = FastAPI()

# Define Session
session_service = InMemorySessionService()

# Define Runner
runner = Runner(
    app_name=APP_NAME,
    agent=tutor_agent,
    session_service=session_service,
)

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    await websocket.accept()

    # RunConfig
    response_modalities = [types.Modality.AUDIO]
    run_config = RunConfig(
        response_modalities=response_modalities,
        streaming_mode=StreamingMode.BIDI,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig()
        # proactivity=types.ProactivityConfig(proactive_audio=True),
        # enable_proactive_audio=True
        # speech_config=types.SpeechConfig(
        #     voice_config=types.VoiceConfig(
        #         prebuild_voice_config=types.PrebuiltVoiceConfig(
        #             voice_name="Puck"
        #         )
        #     ),
        #     language_code="en-US"
        # )
    )

    # Get Session or create session - use dynamic user_id and session_id
    logger.info(f"Getting/creating session for user_id={user_id}, session_id={session_id}")
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if not session:
        logger.info(f"Creating new session for user_id={user_id}, session_id={session_id}")
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

    live_request_queue = LiveRequestQueue()

    context_message = types.Content(
        role="user",
        parts=[types.Part(text=f"System Note: The current user is {user_id} and the session is {session_id}.")]
    )

    live_request_queue.send_content(context_message)

    async def upstream_task():
        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message:
                    audio_data = message["bytes"]
                    audio_blob = types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=audio_data
                    )
                    live_request_queue.send_realtime(audio_blob)

                elif "text" in message:
                    text_data = message["text"]
                    logger.debug(f"Received text message: {text_data}")
                    json_message = json.loads(text_data)
                    msg_type = json_message.get("type")

                    if msg_type == "text":
                        content = types.Content(parts=[types.Part(text=json_message["text"])])
                        live_request_queue.send_content(content)
                        logger.info(f"📨 Sent text message: {json_message['text']}")
                    
                    elif msg_type == "image":
                        import base64
                        mime_type = json_message.get("mimeType")
                        base64_data = json_message.get("data")
                        
                        try:
                            image_bytes = base64.b64decode(base64_data)
                            image_blob = types.Blob(
                                mime_type=mime_type,
                                data=image_bytes
                            )
                            # Use send_realtime for video/image stream
                            # This sends the image as part of the session context
                            live_request_queue.send_realtime(image_blob)
                            # logger.info(f"🖼️ Sent image frame: {len(image_bytes)} bytes")
                        except Exception as e:
                            logger.error(f"Error processing image: {e}")
                
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
    
    async def downstream_task():
        try:
            logger.info("Starting downstream task (listening for agent responses)...")
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                # Send audio as binary frames for efficient playback
                # Audio is 24kHz, 16-bit PCM, mono - already decoded by ADK
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.mime_type.startswith("audio/pcm"):
                            await websocket.send_bytes(part.inline_data.data)

                # Send transcriptions and other events as text JSON
                if event.input_transcription or event.output_transcription:
                    event_json = event.model_dump_json(exclude_none=True, by_alias=True)
                    logger.debug(f"Sending transcription event: {event_json[:200]}")
                    await websocket.send_text(event_json)
        except Exception as e:
            logger.error(f"Error in downstream_task: {e}", exc_info=True)

    try:
        await asyncio.gather(upstream_task(), downstream_task(), return_exceptions=True)
    except WebSocketDisconnect:
        logger.debug("Client disconnected normally")
    except Exception as e:
        logger.error(f"Unexpected error in streaming tasks: {e}", exc_info=True)
    finally:
        logger.info("Closing live request queue")
        live_request_queue.close()
        logger.info("Live request queue closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
