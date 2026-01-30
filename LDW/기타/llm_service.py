import os
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()

class InterviewLLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=self.api_key,
            temperature=0.7
        )
        self.data_path = os.path.join(os.path.dirname(__file__), "data", "interview_lsj.json")
        self.knowledge_base = self._load_data()
        
        # LangChain Memory - Using ChatMessageHistory as backup
        try:
            from langchain_community.chat_message_histories import ChatMessageHistory
            self.memory = ChatMessageHistory()
        except ImportError:
            # Fallback if even community fails (unlikely given debug)
            print("Warning: ChatMessageHistory import failed, using list")
            self.memory = None
            self.history_list = []

    def _load_data(self) -> List[Dict[str, str]]:
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def get_related_context(self, query: str, top_k: int = 3) -> str:
        """
        Simple keyword/similarity search in the knowledge base.
        """
        if not self.knowledge_base:
            return ""
        
        matches = []
        words = query.split()
        for item in self.knowledge_base:
            q_text = item.get("질문", "")
            a_text = item.get("답변", "")
            score = 0
            for word in words:
                if word in q_text or word in a_text:
                    score += 1
            if score > 0:
                matches.append((score, item))
        
        matches.sort(key=lambda x: x[0], reverse=True)
        context_items = matches[:top_k]
        
        context_str = "\n".join([f"참고 질문: {item[1].get('질문')}\n참고 답변: {item[1].get('답변')}" for item in context_items])
        return context_str

    def generate_next_question(self, last_answer: Optional[str] = None) -> str:
        """
        Generates a new question or a follow-up question based on the last answer.
        Uses LangChain Memory to keep track of the conversation.
        """
        
        # 1. Update Memory with User's Answer if provided
        if last_answer:
            if self.memory:
                self.memory.add_user_message(last_answer)
            else:
                self.history_list.append(HumanMessage(content=last_answer))
        
        # 2. Retrieve Context (RAG)
        context = ""
        messages_in_memory = self.memory.messages if self.memory else self.history_list
        
        if last_answer:
            context = self.get_related_context(last_answer)
        elif not messages_in_memory:
            # First question - get a random sample
            import random
            if self.knowledge_base:
                sample = random.choice(self.knowledge_base)
                context = f"참고 질문: {sample['질문']}\n참고 답변: {sample['답변']}"

        # 3. Construct Prompt
        system_prompt = """당신은 전문적인 테크니컬 면접관입니다.
지원자의 답변을 바탕으로 **꼬리 질문(Follow-up question)**을 하거나, 답변이 부족하다면 구체적인 사례를 묻는 등 **심층 질문**을 생성하세요.

[규칙]
1. 제발 **단 하나의 질문**만 하세요. 여러 질문을 나열하지 마세요.
2. 이전 대화 맥락을 고려하여 자연스럽게 질문을 이어가세요.
3. 지원자가 언급한 기술(Keywords)에 대해 깊이 있게 파고드세요.
4. 아래 [Knowledge Base]에 있는 질문을 **그대로 복사하지 마세요**. 해당 내용을 참고하여 **새로운 상황이나 심화된 질문**으로 변형하여 생성하세요.
5. 한국어로 정중하게 질문하세요.

[Knowledge Base]
{context}
"""
        
        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
        ]
        
        # Load History from Memory
        messages.extend(messages_in_memory)

        # 4. Invoke LLM
        response = self.llm.invoke(messages)
        question = response.content.strip()
        
        # 5. Update Memory with AI Question
        if self.memory:
            self.memory.add_ai_message(question)
        else:
            self.history_list.append(AIMessage(content=question))
        
        return question

    def evaluate_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """
        Evaluates the user's answer and returns a JSON response.
        """
        system_message = "당신은 면접관입니다. 지원자의 답변을 평가하여 JSON 형식으로 반환하세요."
        user_prompt = f"""
질문: {question}
답변: {answer}

위 답변을 다음 항목을 포함하여 평가해주세요:
1. 정확성 (Technical Accuracy)
2. 구체성 (Specificity)
3. 개선점 (Improvements)
4. 점수 (Score, 0-100)

응답은 반드시 아래 JSON 형식이어야 합니다:
{{
  "score": 0,
  "feedback": "전반적인 피드백",
  "improvements": "구체적인 개선 제안",
  "technical_accuracy": "기술적 정확성 평가"
}}
"""
        response = self.llm.invoke([
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ])
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"): # Handle cases where language identifier is missing
                 content = content[3:-3].strip()
            return json.loads(content)
        except Exception as e:
            print(f"JSON Parse Error: {e}, Content: {content}")
            return {
                "score": 0,
                "feedback": "평가 생성 중 오류가 발생했습니다.",
                "improvements": "N/A",
                "technical_accuracy": "N/A"
            }

# Singleton instance
interview_service = InterviewLLMService()

# Legacy functions for compatibility
def get_interview_question(file_path=None, last_answer=None):
    return interview_service.generate_next_question(last_answer)

def evaluate_answer(question, answer):
    return interview_service.evaluate_answer(question, answer)
