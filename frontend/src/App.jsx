// frontend/src/App.jsx
import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";

import RequireAuth_yyr from "./pages_yyr/RequireAuth_yyr";
import LoginPage_yyr from "./pages_yyr/LoginPage_yyr";
import AdminPage_yyr from "./pages_yyr/AdminPage_yyr";

import UserHomePage_yyr from "./pages_yyr/UserHomePage_yyr";
import InterviewPage_yyr from "./pages_yyr/InterviewPage_yyr";
import ResultRoutePage_yyr from "./pages_yyr/ResultRoutePage_yyr";

// 백엔드 주소
const API_BASE_URL = "http://127.0.0.1:8001";

// ✅ 새 세션ID 생성 함수
function createSessionId() {
  return `session_${Date.now()}`;
}

function App() {
  const location = useLocation();
  const nav = useNavigate();

  const [visionResult, setVisionResult] = useState("분석 대기 중...");
  const [chatLog, setChatLog] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isResumeUploaded, setIsResumeUploaded] = useState(false);

  // ✅ 면접 진행 단계 (lobby | ready | live | report)
  const [interviewPhase, setInterviewPhase] = useState("lobby");

  // ✅ 면접 세션(thread_id)
  const [sessionId, setSessionId] = useState(null);

  // 리포트 모달 상태
  const [showReport, setShowReport] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const audioPlayerRef = useRef(null);

  /* =========================================================
     ✅ 세션 초기화 공통 함수
     - 로비 진입 / 새 면접 시작(리셋) 둘 다 여기로 모으기
  ========================================================= */
  const resetSessionState = (newId) => {
    setSessionId(newId);

    // 로비 시작점 기준 초기화
    setChatLog([]);
    setIsResumeUploaded(false);

    setShowReport(false);
    setReportData(null);
    setLoadingReport(false);

    setVisionResult("분석 대기 중...");
    setInterviewPhase("lobby");
    setIsProcessing(false);

    console.log("✅ Session reset:", newId);
  };

  /* =========================================================
     ✅ /user/home 진입 시: sessionId가 없으면 1회만 발급
     - 새로고침/재진입해도 동일 세션 유지(중요)
     - "새 이력서로 다시 시작"은 별도의 reset 버튼으로 처리
  ========================================================= */
  useEffect(() => {
    if (location.pathname !== "/user/home") return;
    if (sessionId) return; // 이미 세션 있으면 재발급 X

    const newId = createSessionId();
    resetSessionState(newId);
  }, [location.pathname, sessionId]);

  /* =========================================================
     1) 비전 분석 (WebcamView에서 3초마다 스냅샷 전달)
  ========================================================= */
  const handleVideoFrame = async (imageBlob) => {
    if (isProcessing) return;

    try {
      const formData = new FormData();
      formData.append("file", imageBlob, "snapshot.jpg");

      const response = await axios.post(`${API_BASE_URL}/analyze/face`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      if (response.data?.status === "success") {
        const emotion = response.data.analysis?.dominant_emotion;
        if (emotion) setVisionResult(String(emotion).toUpperCase());
      }
    } catch (error) {
      // 조용히 실패 처리
    }
  };

  /* =========================================================
     2) 이력서 업로드 (PDF) + thread_id(sessionId) 연동
     - 성공 시 interviewPhase = "ready"
  ========================================================= */
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!sessionId) {
      alert("세션이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.");
      return;
    }

    if (file.type !== "application/pdf") {
      alert("PDF 파일만 업로드 가능합니다.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API_BASE_URL}/upload/resume`, formData, {
        params: { thread_id: sessionId },
        headers: { "Content-Type": "multipart/form-data" },
      });

      if (response.data?.status === "success") {
        setIsResumeUploaded(true);
        setInterviewPhase("ready");
        setChatLog((prev) => [
          ...prev,
          { sender: "system", text: "✅ 이력서 분석이 완료되었습니다. 이제 맞춤형 질문이 시작됩니다." },
        ]);
        alert("이력서가 등록되었습니다!");
      }
    } catch (error) {
      console.error("업로드 실패:", error);
      alert("이력서 업로드에 실패했습니다. 백엔드 로그를 확인하세요.");
    }
  };

  /* =========================================================
     3) 음성 답변 제출 (Audio → AI 음성 응답)
  ========================================================= */
  const handleAudioSubmit = async (audioBlob) => {
    if (!sessionId) {
      alert("세션이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.");
      return;
    }

    setIsProcessing(true);
    setChatLog((prev) => [...prev, { sender: "user", text: "🎤 (음성 전송 중...)" }]);

    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "user_voice.webm");
      formData.append("current_emotion", visionResult);

      const response = await axios.post(`${API_BASE_URL}/chat/voice/audio`, formData, {
        params: { thread_id: sessionId },
        responseType: "blob",
      });

      const aiAudioBlob = response.data;
      const audioUrl = URL.createObjectURL(aiAudioBlob);

      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = audioUrl;
        await audioPlayerRef.current.play();
      }

      setChatLog((prev) => [...prev, { sender: "ai", text: "🔊 (AI가 답변 중입니다...)" }]);
    } catch (error) {
      console.error("음성 대화 에러:", error);
      alert("AI 서버 연결 실패! 백엔드 로그를 확인하세요.");
    } finally {
      setIsProcessing(false);
    }
  };

  /* =========================================================
     4) 리포트 생성 + 조회 (면접 종료)
     - POST /report/{thread_id} : 생성(1회)
     - GET  /report/{thread_id}/result : 조회(표준)
  ========================================================= */
  const handleEndInterview = async () => {
    if (!sessionId) {
      alert("세션이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.");
      return;
    }

    if (!window.confirm("면접을 종료하고 결과를 확인하시겠습니까?")) return;

    setLoadingReport(true);
    setShowReport(true);
    setReportData(null);

    try {
      await axios.post(`${API_BASE_URL}/report/${sessionId}`);
      const res = await axios.get(`${API_BASE_URL}/report/${sessionId}/result`);

      setReportData(res.data);
      setInterviewPhase("report");
      console.log("reportData(GET result):", res.data);
    } catch (error) {
      console.error("리포트 생성/조회 실패:", error);
      alert("리포트를 불러오는 중 오류가 발생했습니다.");
      setShowReport(false);
    } finally {
      setLoadingReport(false);
    }
  };

  /* =========================================================
     ✅ 면접 시작: (ready → live) + /interview 이동
     - 로비(/user/home)에서 '면접 시작' 버튼 눌렀을 때 호출됨
  ========================================================= */
  const handleStartInterview = () => {
    if (!isResumeUploaded) {
      alert("이력서 업로드를 먼저 완료해주세요.");
      return;
    }
    setInterviewPhase("live");
    nav("/interview");
  };

  /* =========================================================
     ✅ 세션 리셋: "다른 이력서로 다시 시작"을 위한 MVP
     - 새 sessionId 발급 + 모든 상태 초기화 + /user/home 유지
  ========================================================= */
  const handleResetSession = () => {
    const newId = createSessionId();
    resetSessionState(newId);
    nav("/user/home");
  };

  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("role");
    window.location.href = "/login";
  };

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage_yyr />} />
      <Route path="/admin" element={<AdminPage_yyr />} />

      {/* ✅ B: 단독 결과 페이지 */}
      <Route path="/result/:threadId" element={<ResultRoutePage_yyr />} />
      <Route path="/admin/result/:threadId" element={<ResultRoutePage_yyr />} />

      {/* ✅ 로비: 면접 시작 전(공고 선택/이력서/환경 테스트) */}
      <Route
        path="/user/home"
        element={
          <RequireAuth_yyr>
            <UserHomePage_yyr
              sessionId={sessionId}
              interviewPhase={interviewPhase}
              isResumeUploaded={isResumeUploaded}
              onFileUpload={handleFileUpload}
              onStartInterview={handleStartInterview}
              onResetSession={handleResetSession}
              onLogout={handleLogout}
            />
          </RequireAuth_yyr>
        }
      />

      {/* ✅ 면접 화면 */}
      <Route
        path="/interview"
        element={
          <RequireAuth_yyr>
            <InterviewPage_yyr
              sessionId={sessionId}
              visionResult={visionResult}
              chatLog={chatLog}
              isProcessing={isProcessing}
              isResumeUploaded={isResumeUploaded}
              interviewPhase={interviewPhase}
              onStartInterview={handleStartInterview}
              onLogout={handleLogout}
              onFileUpload={handleFileUpload}
              onEndInterview={handleEndInterview}
              onAudioSubmit={handleAudioSubmit}
              onVideoFrame={handleVideoFrame}
              showReport={showReport}
              setShowReport={setShowReport}
              reportData={reportData}
              loadingReport={loadingReport}
              audioPlayerRef={audioPlayerRef}
            />
          </RequireAuth_yyr>
        }
      />

      {/* ✅ 없는 경로는 로비로 */}
      <Route path="*" element={<Navigate to="/user/home" replace />} />
    </Routes>
  );
}

export default App;