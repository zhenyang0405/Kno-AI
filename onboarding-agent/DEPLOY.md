# Deployment Guide for Onboarding Agent (Consolidated)

This agent is prepared for deployment on Google Cloud Run. It uses FastAPI to expose a REST endpoint and interacts with a PostgreSQL database.

## API Usage

The service exposes a `POST /chat` endpoint.

**Sample Request:**

```bash
curl -X POST "http://YOUR_SERVICE_URL/chat?uid=asbcdeddsc" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello!"}'
```

The `uid` parameter in the URL is used to resolve the user in the database.

## Environment Variables

- `GOOGLE_API_KEY`: Gemini API Key.
- `DB_HOST`: Database host.
- `DB_NAME`: Database name.
- `DB_USER`: Database user.
- `DB_PASS`: Database password.

## How the Conversation Works

The agent doesn't "stay open" like a live chat; instead, the frontend and backend talk to each other in a loop:

1.  **User sends message**: The user types a message in your frontend (e.g., at `http://localhost:5173/onboarding?uid=...`).
2.  **Frontend calls Cloud Run**: The frontend sends that message to your Cloud Run service's `/chat` endpoint, along with the `uid` from the URL.
3.  **Backend processes**:
    - The backend uses the `uid` to find the correct user in your PostgreSQL database.
    - It passes the message to the AI Agent.
    - The AI Agent decides if it needs to save a preference (using the tools we built).
4.  **Backend responds**: The backend sends the AI's response back to the frontend.
5.  **User sees response**: Your frontend displays the response to the user.

## Step-by-Step Deployment

### 1. Test Locally First

To make sure everything is configured correctly, run this in your terminal:

```bash
# Set your API key
export GOOGLE_API_KEY="your-gemini-api-key"

# Run the agent server
python3 -m chat_agent.agent
```

Then, use `curl` (or an app like Postman) to send a test message:

```bash
curl -X POST "http://localhost:8080/chat?uid=test_uid_123" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hi, I am interested in AI"}'
```

### 2. Deploy to Cloud Run

Once local testing works, run this one command to deploy to the web:

```bash
gcloud run deploy onboarding-agent --source . --allow-unauthenticated
```

- **Source**: `.` means "use the code in this folder".
- **Allow Unauthenticated**: This lets your frontend talk to the backend without complex login headers for now.

### 3. Set Environment Variables

The agent needs your database info and API key. You can set these in the Google Cloud Console for your Cloud Run service, or via command line:

```bash
gcloud run services update onboarding-agent \
  --set-env-vars GOOGLE_API_KEY=xxx,DB_HOST=xxx,DB_PASS=xxx
```

## Database Logic

The code in `chat_agent/tools.py` automatically looks for these variables. Ensure your database is accessible (e.g., using Cloud SQL or making sure the DB firewall allows Cloud Run).
