import asyncio
import os
from dotenv import load_dotenv

# Ensure we can import from the current directory
import sys
sys.path.append(r'C:\big20\big20_AI_Interview_simulation\LDW\text08')

from services.llm_service import LLMService

async def test_llm_service():
    print("Testing LLMService...")
    service = LLMService()
    
    # Test 1: Embedding
    print("\n1. Testing Embedding...")
    emb = await service.get_embedding("테스트 텍스트입니다.")
    if emb and len(emb) > 0:
        print(f"Embedding successful. Length: {len(emb)}")
    else:
        print("Embedding failed.")

    # Test 2: Generate Question
    job_title = "Python 백엔드 개발자"
    print(f"\n2. Testing Generate Question for {job_title}...")
    question = await service.generate_question(job_title, "intro", None)
    print(f"Generated Question: {question}")
    
    # Test 3: Evaluate Answer
    print(f"\n3. Testing Evaluate Answer...")
    answer = "저는 3년차 백엔드 개발자입니다. Django와 FastAPI를 주로 사용했습니다."
    evaluation = await service.evaluate_and_next_action(job_title, question, answer, is_last_question=False)
    print("Evaluation Result:")
    print(evaluation)

if __name__ == "__main__":
    asyncio.run(test_llm_service())
