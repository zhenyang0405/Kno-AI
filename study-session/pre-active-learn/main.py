"""
Pre-Active-Learn API - FastAPI Application

Main entry point for the Pre-Active-Learn Service.

This service handles workspace preparation before active learning:
- User authentication and database mapping
- Study session lifecycle management
- Material context caching (Gemini)
- Concept extraction from materials
- Workspace initialization
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Create FastAPI app
app = FastAPI(
    title="Pre-Active-Learn API",
    description="Workspace preparation service for AI Educate",
    version="1.0.0"
)

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

# Include routers
from routes import router
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Pre-Active-Learn API",
        "version": "1.0.0",
        "description": "Workspace preparation service",
        "endpoints": {
            "initialize": "/api/pre-active-learn/initialize-workspace",
            "study_sessions": "/api/pre-active-learn/study-sessions",
            "users": "/api/pre-active-learn/users/get-or-create",
            "health": "/api/pre-active-learn/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """Global health check"""
    return {"status": "healthy", "service": "pre-active-learn"}


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("🚀 Pre-Active-Learn Service Starting...")
    print("Services:")
    print("  ✓ User Management (Firebase UID mapping)")
    print("  ✓ Study Session Lifecycle")
    print("  ✓ Material Context Caching (Gemini)")
    print("  ✓ Concept Extraction")
    print("  ✓ Workspace Initialization")
    
    # Ensure users table exists
    try:
        from user_service import ensure_users_table
        ensure_users_table()
        print("✓ Users table ensured")
    except Exception as e:
        print(f"⚠ Warning: Could not ensure users table: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True
    )
