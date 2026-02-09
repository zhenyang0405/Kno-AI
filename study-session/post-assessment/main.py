"""
FastAPI application for post-assessment question generation

Run with: uvicorn main:app --reload --port 8004
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router

app = FastAPI(
    title="Post-Assessment API",
    description="API for generating post-assessment MCQ questions targeting weak concepts with comparative feedback",
    version="1.0.0"
)

# CORS middleware
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

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Post-Assessment API",
        "version": "1.0.0",
        "endpoints": {
            "generate_questions": "/api/post-assessment/generate-questions",
            "mark_assessment": "/api/post-assessment/mark-assessment",
            "start_assessment": "/api/post-assessment/start-assessment",
            "health": "/api/post-assessment/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
