import uvicorn
import webbrowser
import threading
import time
import os

def open_browser():
    """
    Open the browser after a short delay to allow the server to start.
    """
    print("Opening browser in 2 seconds...")
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    # Ensure backend directories exist
    os.makedirs("static/uploads", exist_ok=True)
    
    print("Starting AI Interview Simulation System...")
    
    # Run browser opener in separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start Uvicorn Server
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
