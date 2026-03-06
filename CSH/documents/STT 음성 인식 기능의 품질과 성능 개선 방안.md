

---

## 오인식 원인 분석


### Deepgram 키워드 부스팅 미사용

현재 Deepgram 연결 설정에 **`keywords` 파라미터**가 없습니다. 면접 맥락에서 자주 등장하는 용어(비즈니스, 프로젝트, 아키텍처 등)를 부스팅하면 인식 정확도가 크게 향상됩니다.

---

## 개선 방안

**Deepgram keywords 부스팅** (integrated_interview_server.py)
   - 면접 도메인 키워드 + 세션별 질문 키워드를 Deepgram에 전달


수정 파일
- integrated_interview_server.py (keywords 부스팅)


| 파일 | 변경 | 부작용 |
|------|------|--------|
| integrated_interview_server.py | Deepgram keywords 부스팅 (면접 도메인 용어) | 없음 |
