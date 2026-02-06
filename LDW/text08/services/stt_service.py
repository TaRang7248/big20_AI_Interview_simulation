from openai import AsyncOpenAI
import os

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# IT 면접을 위한 용어 사전 (Custom Vocabulary)
CUSTOM_VOCAB = "Python, Java, JavaScript, C++, SQL, NoSQL, Redis, MongoDB, AWS, Docker, Kubernetes, CI/CD, Git, GitHub, REST API, GraphQL, Microservices, TDD, Agile, Scrum, React, Vue, Angular, Node.js, Spring Boot, Django, Flask, FastAPI, TensorFlow, PyTorch, LLM, GPT, BERT, Transformer, RAG, Fine-tuning, Prompt Engineering"

async def transcribe_audio(file_path: str, context: str = ""):
    """
    Transcribe audio file using Whisper with Custom Vocabulary and Context.
    
    Args:
        file_path: Path to the audio file.
        context: Previous conversation context to improve accuracy (Contextual Bias).
    """
    try:
        # Construct the prompt with Custom Vocabulary and Context
        prompt_text = f"This is a technical interview. Keywords: {CUSTOM_VOCAB}. Context: {context}"
        
        # Limit prompt length (OpenAI limit is 244 tokens, rough check)
        if len(prompt_text) > 200:
            prompt_text = prompt_text[:200]

        with open(file_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko", # Force Korean
                prompt=prompt_text, # Custom Vocabulary & Contextual Bias
                temperature=0.2 # Lower temperature for more deterministic output
            )
        return transcript.text
    except Exception as e:
        print(f"STT Error: {e}")
        return ""

class STTService:
    def __init__(self):
        pass

    async def transcribe(self, file_path: str, context: str = ""):
        return await transcribe_audio(file_path, context)

    def start_recording(self):
        print("Warning: Server-side recording is not supported in this environment.")

    def stop_recording(self):
        print("Warning: Server-side recording is not supported in this environment.")
        return None
