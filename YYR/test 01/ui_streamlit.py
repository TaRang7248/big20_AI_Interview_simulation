import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Interview Demo", layout="centered")
st.title("AI Interview Demo (Streamlit)")
st.caption("FastAPI 엔진을 호출하는 빠른 데모 UI")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role": "ai"/"user", "content": "..."}]
if "turn" not in st.session_state:
    st.session_state.turn = 0

with st.sidebar:
    st.subheader("설정")
    use_llm = st.checkbox("use_llm", value=False)
    first_q = st.text_input("첫 질문", value="지원 직무의 특징과 역할에 대해 아는 대로 말해주세요! (700자)")
    if st.button("면접 시작 (/start)"):
        r = requests.post(f"{API_BASE}/start", json={"first_question": first_q, "use_llm": use_llm})
        r.raise_for_status()
        data = r.json()

        st.session_state.session_id = data["session_id"]
        st.session_state.turn = data["turn"]
        st.session_state.messages = [{"role": "ai", "content": data["question"]}]
        st.success(f"세션 시작: {st.session_state.session_id}")

st.divider()

# 채팅 표시
for m in st.session_state.messages:
    with st.chat_message("assistant" if m["role"] == "ai" else "user"):
        st.write(m["content"])

# 입력창
if st.session_state.session_id:
    user_text = st.chat_input("답변을 입력하세요")
    if user_text:
        st.session_state.messages.append({"role": "user", "content": user_text})

        r = requests.post(f"{API_BASE}/answer", json={"session_id": st.session_state.session_id, "answer": user_text})
        r.raise_for_status()
        data = r.json()

        st.session_state.turn = data["turn"]
        st.session_state.messages.append({"role": "ai", "content": data["question"]})
else:
    st.info("왼쪽 사이드바에서 '면접 시작'을 눌러주세요.")
