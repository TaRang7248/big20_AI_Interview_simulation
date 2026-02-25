// frontend/src/pages_yyr/mockInterviewResults.js

export const mockInterviewResults = {
    my_new_interview_01: {
        threadId: "my_new_interview_01",
        createdAt: "2026-02-25T10:30:00+09:00",
        job: { jobId: "JOB-001", title: "백엔드 개발자 (FastAPI)", status: "open" },
        applicant: { applicantId: "APP-001", displayName: "지원자 A" },
        overall: { score: 86, decision: "pass", summary: "기술 역량이 뛰어나며, 핵심 개념을 구조적으로 설명했습니다." },
        scores: {
            technical: { score: 5, feedback: "DB/인덱스/정규화 이해가 명확합니다." },
            problemSolving: { score: 4, feedback: "접근이 빠르나 엣지케이스 언급을 더 하면 좋습니다." },
            communication: { score: 3, feedback: "결론→근거→예시 구조를 더 명확히 하면 좋습니다." },
            attitude: { score: 4, feedback: "차분하고 협업적인 태도가 돋보입니다." }
        },
        evidence: {
            technical: [
                { quote: "인덱스는 조회 성능을 높이지만 쓰기 비용이 늘어납니다.", reason: "트레이드오프 인지", weight: 0.8 }
            ],
            communication: [
                { quote: "음… 그러니까…", reason: "답변 구조화 약함(예시)", weight: 0.5 }
            ]
        },
        adminMeta: {
            durationSec: 620,
            turns: 7,
            flags: [{ code: "LOW_STRUCTURE", label: "답변 구조화 약함", severity: "medium" }]
        }
    },

    my_new_interview_02: {
        threadId: "my_new_interview_02",
        createdAt: "2026-02-25T11:10:00+09:00",
        job: { jobId: "JOB-002", title: "데이터 분석가 (SQL/BI)", status: "open" },
        applicant: { applicantId: "APP-002", displayName: "지원자 B" },
        overall: { score: 74, decision: "fail", summary: "분석 접근은 좋았으나 SQL 최적화 근거가 약했습니다." },
        scores: {
            technical: { score: 3, feedback: "JOIN/집계는 가능하나 실행 계획 관점이 부족합니다." },
            problemSolving: { score: 4, feedback: "지표 정의는 명확합니다." },
            communication: { score: 3, feedback: "핵심만 먼저 말하는 습관이 필요합니다." },
            attitude: { score: 4, feedback: "피드백 수용이 좋습니다." }
        },
        evidence: {
            technical: [
                { quote: "실행 계획은… 잘 모르겠습니다.", reason: "핵심 개념 미흡", weight: 0.9 }
            ]
        },
        adminMeta: {
            durationSec: 540,
            turns: 6,
            flags: [{ code: "WEAK_OPT", label: "SQL 최적화 약함", severity: "high" }]
        }
    },

    my_new_interview_03: {
        threadId: "my_new_interview_03",
        createdAt: "2026-02-25T12:02:00+09:00",
        job: { jobId: "JOB-001", title: "백엔드 개발자 (FastAPI)", status: "open" },
        applicant: { applicantId: "APP-003", displayName: "지원자 C" },
        overall: { score: 92, decision: "pass", summary: "설계 의사결정이 명확하고 장애 대응 관점이 좋습니다." },
        scores: {
            technical: { score: 5, feedback: "캐시/큐/DB 분리 전략을 잘 설명합니다." },
            problemSolving: { score: 5, feedback: "문제를 분해하고 우선순위를 잘 잡습니다." },
            communication: { score: 4, feedback: "구조적 답변이 안정적입니다." },
            attitude: { score: 4, feedback: "압박 상황에서도 침착합니다." }
        },
        evidence: {},
        adminMeta: {
            durationSec: 700,
            turns: 8,
            flags: []
        }
    }
};