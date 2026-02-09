import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Core imports
from packages.imh_core.config import IMHConfig
from packages.imh_core.logging import get_logger
from packages.imh_core.errors import IMHBaseError

# API Routers
from IMH.api.health import router as health_router
from IMH.api.playground import router as playground_router

# Configuration Load
config = IMHConfig.load()
logger = get_logger("IMH.main")

def setup_runtime_logging():
    """
    Configure runtime logging to logs/runtime/.
    Adds a file handler specifically for runtime logs.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
    log_dir = os.path.join(base_dir, "logs", "runtime")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "runtime.log")
    
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Attach to root logger to capture all events including uvicorn
    logging.getLogger().addHandler(file_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_runtime_logging()
    logger.info(f"Starting {config.PROJECT_NAME} v{config.VERSION}...")
    
    yield
    
    # Shutdown
    logger.info("Server shutting down...")

def create_app() -> FastAPI:
    app = FastAPI(
        title=config.PROJECT_NAME,
        version=config.VERSION,
        lifespan=lifespan,
        docs_url="/docs",       # Dev only
        redoc_url=None
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],    # Allow all for now (Dev)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router, prefix="", tags=["Status"])
    app.include_router(playground_router, prefix="/api/v1/playground", tags=["Playground"])

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("IMH.main:app", host="0.0.0.0", port=8000, reload=True)
