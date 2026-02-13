from fastapi import FastAPI
from IMH.api.session import router as session_router
from IMH.api.admin import router as admin_router
from IMH.api.health import router as health_router # Assuming exists from TASK-004

def create_app() -> FastAPI:
    """
    Application Bootstrap.
    Initializes DI Container (implicitly via dependencies), Routers, and Middleware.
    """
    app = FastAPI(
        title="IMH AI Interview Simulation API",
        version="0.6.0", # Phase 6
        description="API Layer for IMH AI Interview System"
    )

    # Register Routers
    app.include_router(session_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    
    # Include Health Check (TASK-004) if compatible, or ensure base health
    # app.include_router(health_router) # Uncomment if TASK-004 provided a router object

    @app.get("/")
    def root():
        return {"message": "IMH Interview API is running"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    # For local testing/debugging only. Production uses external ASGI runner.
    uvicorn.run(app, host="0.0.0.0", port=8000)
