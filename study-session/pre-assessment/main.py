"""
FastAPI application for pre-assessment question generation

Run with: uvicorn main:app --reload --port 8002
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router

app = FastAPI(
    title="Pre-Assessment API",
    description="API for generating MCQ questions from PDF materials using ADK agent",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ai-educate-gemini-3-hackathon.web.app"
    ],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Pre-Assessment API",
        "version": "1.0.0",
        "endpoints": {
            "generate_questions": "/api/pre-assessment/generate-questions",
            "mark_assessment": "/api/pre-assessment/mark-assessment",
            "health": "/api/pre-assessment/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
