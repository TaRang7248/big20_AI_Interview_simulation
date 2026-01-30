import os
import json
from dotenv import load_dotenv

load_dotenv()
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# Ensure API key is set
# if not os.environ.get("OPENAI_API_KEY"):
#     print("WARNING: OPENAI_API_KEY not found in environment variables.")

llm = ChatOpenAI(temperature=0.7, model_name="gpt-4o")

class EvaluationResult(BaseModel):
    score: int = Field(description="Score out of 100")
    feedback: str = Field(description="Constructive feedback for the candidate")
    pass_fail: str = Field(description="'PASS' or 'FAIL'")
    needs_followup: bool = Field(description="True if the answer is vague or needs clarification")

def generate_interview_question(base_question: str) -> str:
    """Generates a variation of the interview question or a fresh one based on the topic."""
    prompt = PromptTemplate.from_template(
        "당신은 엄격한 기술 면접관입니다. \n"
        "다음은 데이터베이스에 있는 주제/질문입니다: '{base_question}'.\n"
        "이것을 실제 면접 질문처럼 격식 있게 다듬어서 질문해주세요. 단순히 따라 쓰지 마십시오. \n"
        "자연스럽고 전문적인 말투를 사용하세요."
    )
    chain = prompt | llm
    response = chain.invoke({"base_question": base_question})
    return response.content

def evaluate_answer(question: str, answer: str) -> dict:
    """Evaluates the user's answer and returns a JSON object."""
    parser = PydanticOutputParser(pydantic_object=EvaluationResult)
    
    prompt = PromptTemplate(
        template="당신은 지원자를 평가하는 기술 면접관입니다.\n"
                 "질문: {question}\n"
                 "지원자 답변: {answer}\n\n"
                 "기술적 정확성, 깊이, 명확성을 바탕으로 답변을 평가하세요.\n"
                 "답변이 너무 짧거나, 모호하거나, 핵심 개념을 설명 없이 언급만 했다면 `needs_followup`을 True로 설정하세요.\n"
                 "피드백(feedback)은 구체적으로 한국어로 작성하세요.\n\n"
                 "{format_instructions}\n",
        input_variables=["question", "answer"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    chain = prompt | llm | parser
    result = chain.invoke({"question": question, "answer": answer})
    return result.dict()

def generate_tail_question(previous_question: str, previous_answer: str) -> str:
    """Generates a follow-up question based on the previous answer."""
    prompt = PromptTemplate.from_template(
        "당신은 기술 면접관입니다.\n"
        "이전 질문: {previous_question}\n"
        "지원자 답변: {previous_answer}\n\n"
        "지원자의 답변이 모호하거나, 불완전하거나, 혹은 더 깊이 파고들 만한 흥미로운 내용이었습니다.\n"
        "지식의 깊이를 테스트하거나 모호한 점을 명확히 하기 위해 구체적인 꼬리 질문(follow-up question)을 하나 던지세요.\n"
        "한국어로 질문하고 간결하게 유지하세요."
    )
    chain = prompt | llm
    response = chain.invoke({"previous_question": previous_question, "previous_answer": previous_answer})
    return response.content
