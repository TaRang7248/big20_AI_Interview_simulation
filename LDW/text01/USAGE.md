# Text Interview Vertical Slice

This is a functional vertical slice of the text-based AI interview system.

## Components
*   **Backend**: FastAPI (`app.py`), SQLAlchemy (`database.py`, `models.py`).
*   **Database**: SQLite (`interview_vertical_slice.db`). Pre-loaded with data from `interview_lsj.json`.
*   **AI**: LangChain + OpenAI (`llm_service.py`).
*   **Frontend**: HTML/JS (`templates/index.html`, `static/script.js`).

## Prerequisites
*   Python 3.10+
*   OpenAI API Key set in environment variables (`OPENAI_API_KEY`).

## Setup & Run

1.  **Install Dependencies** (if not already installed):
    ```bash
    pip install fastapi uvicorn sqlalchemy langchain langchain-openai pydantic
    ```

2.  **Navigate to Directory**:
    ```bash
    cd LDW/text01
    ```

3.  **Run the App**:
    ```bash
    python app.py
    ```
    *   This will start the server and automatically open your web browser.

## Features
*   **Fully Korean Interface & Interaction**: All questions, feedback, and UI elements are in Korean.
*   Start a new interview session.
*   Get a generated interview question (based on real topics).
*   Submit an answer and get real-time evaluation.
*   **Adaptive Follow-up (꼬리 질문)**: If your answer is vague or needs clarification, the AI will ask a specific follow-up question before grading.
