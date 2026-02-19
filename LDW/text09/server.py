import uvicorn
import webbrowser
from threading import Timer
from app.config import logger
from app.main import app

def open_browser():
    logger.info("Opening browser at http://localhost:5000")
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    logger.info("Starting AI Interview Simulation Server...")
    Timer(1, open_browser).start()
    uvicorn.run(app, host="0.0.0.0", port=5000)
