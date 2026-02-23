import uvicorn
import webbrowser
from threading import Timer
from app.config import logger
from app.main import app

def open_browser():
    """
    Opens the default web browser to the application URL.
    """
    url = "http://localhost:5000"
    logger.info(f"Opening browser at {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")

if __name__ == "__main__":
    logger.info("Starting AI Interview Simulation Server...")
    
    # Timer to open browser after 1.5 seconds to ensure server is ready
    Timer(1.5, open_browser).start()
    
    # Run Uvicorn Server
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=False)
