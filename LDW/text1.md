```mermaid
graph TD
    %% 전체 스타일 설정 (검은색 바탕, 흰색 테두리 및 문자)
    classDef default fill:#000000,stroke:#ffffff,color:#ffffff;

    %% 노드 정의 및 기술 상세
    A[면접 참여자]
    B["면접관 페르소나 (LLM Brain)<br/>스타일 및 상황 생성"]
    C["질문 생성 모듈"]
    D["질문 답변 관리"]
    E["Main DB<br/>사용자 정보 및 기록 저장"]
    F["Vector DB (RAG)<br/>기업 인재상/질문 은행 참조"]
    G["면접 결과"]
    H["Task Queue<br/>리포트 생성 및 영상 인코딩"]

    %% 기술 기능 노드
    T1["VAD (Voice Activity Detection)<br/>사용자 말 감지 및 개입"]
    T2["추가 검증 질문 생성"]
    T3["STT (Whisper/Deepgram)<br/>음성을 텍스트로 변환"]
    T4["TTS (Text-to-Speech)<br/>LLM 토큰 실시간 음성 변환"]
    T5["Vision AI (OpenCV/MediaPipe)<br/>표정/시선/자세 분석 → 자신감 산출"]
    T6["면접자 기술 이해도 평가"]

    %% 연결 흐름 및 데이터 상호작용
    A --> C
    B  --> C
    T1  --- C
    C  --> T2
    C  --> T4
    T4 --> A
    
    A  --> T3
    T3  --> D
    D  --> T5
    D  --> T6
    
    %% DB 및 RAG 로직
    D  --> E
    E --> D
    D  --> F
    F --> D

    %% 결과 도출
    D --> G
    G -- "SWOT 분석 포함" --> H

    %% 개별 노드에 스타일 적용
    class A,B,C,D,E,F,G,H,T1,T2,T3,T4,T5,T6 default;
