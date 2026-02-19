
import React, { useState, useEffect, useRef } from 'react';
import { Routes, Route, Navigate } from "react-router-dom";

import ResultRoutePage_yyr from "./pages_yyr/ResultRoutePage_yyr";
import LoginPage_yyr from "./pages_yyr/LoginPage_yyr";

import axios from 'axios';
import WebcamView from './components/WebcamView';
import AudioRecorder from './components/AudioRecorder';
import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from 'react-icons/fa';
import ResultPage from "./pages_yyr/ResultPage_yyr";
import RequireAuth_yyr from "./pages_yyr/RequireAuth_yyr";

// 2.19 16:29PM까지의 import
// import ResultRoutePage_yyr from "./pages_yyr/ResultRoutePage_yyr";
// import React, { useState, useEffect, useRef } from 'react';
// import { Routes, Route } from "react-router-dom";
// // import { Routes, Route, useParams } from "react-router-dom"; // ✅ 추가 (2.19추가) -> ResultRoute파일생성으로다시삭제
// import axios from 'axios';
// import WebcamView from './components/WebcamView';
// import AudioRecorder from './components/AudioRecorder';
// import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from 'react-icons/fa'; // 아이콘 추가
// import ResultPage from "./pages_yyr/ResultPage_yyr"; // yyr추가
// import LoginPage_yyr from "./pages_yyr/LoginPage_yyr"; // ✅ 추가 (2.19추가)
// import { Routes, Route, Navigate } from "react-router-dom"; // ✅ 추가 (2.19추가)

// 백엔드 주소
// NOTE:
// SESSION_ID는 실제로 thread_id 역할을 하며,
// A(모달) 결과 조회의 기준 식별자임
const API_BASE_URL = "http://127.0.0.1:8001";
const SESSION_ID = "my_new_interview_01";

function App() {
  const [visionResult, setVisionResult] = useState("분석 대기 중...");
  const [chatLog, setChatLog] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const audioPlayerRef = useRef(null);
  const [isResumeUploaded, setIsResumeUploaded] = useState(false);

  // [신규] 리포트 모달 상태
  const [showReport, setShowReport] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  // 1. 비전 분석 (3초마다 웹캠 이미지 전송)
  const handleVideoFrame = async (imageBlob) => {
    if (isProcessing) return; // AI가 말할 땐 분석 잠시 중단

    try {
      const formData = new FormData();
      formData.append("file", imageBlob, "snapshot.jpg");

      const response = await axios.post(`${API_BASE_URL}/analyze/face`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      if (response.data.status === "success") {
        const emotion = response.data.analysis.dominant_emotion;
        setVisionResult(emotion.toUpperCase());
      }
    } catch (error) {
      // console.error("비전 분석 에러:", error); 
    }
  };

  // 2. 이력서 파일 업로드 핸들러
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      alert("PDF 파일만 업로드 가능합니다.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API_BASE_URL}/upload/resume`, formData, {
        params: { thread_id: SESSION_ID },
        headers: { "Content-Type": "multipart/form-data" },
      });

      if (response.data.status === "success") {
        setIsResumeUploaded(true);
        setChatLog(prev => [...prev, { sender: 'system', text: '✅ 이력서 분석이 완료되었습니다. 이제 맞춤형 질문이 시작됩니다.' }]);
        alert("이력서가 등록되었습니다!");
      }
    } catch (error) {
      console.error("업로드 실패:", error);
      alert("이력서 업로드에 실패했습니다. 백엔드 로그를 확인하세요.");
    }
  };

  // 3. 음성 답변 제출 (수정됨: 감정 데이터 포함 전송)
  const handleAudioSubmit = async (audioBlob) => {
    setIsProcessing(true);
    setChatLog(prev => [...prev, { sender: 'user', text: '🎤 (음성 전송 중...)' }]);

    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "user_voice.webm");

      // [★핵심 변경점] 현재 화면에 보이는 감정 상태(Happy, Fear 등)를 백엔드로 같이 보냅니다!
      // visionResult 상태값은 App 컴포넌트 상단에 이미 선언되어 있으므로 바로 사용 가능합니다.
      formData.append("current_emotion", visionResult);

      // 백엔드로 전송
      const response = await axios.post(`${API_BASE_URL}/chat/voice/audio`, formData, {
        params: { thread_id: SESSION_ID },
        responseType: 'blob', // 오디오 파일(Blob)로 받기
      });

      // AI 음성 재생
      const aiAudioBlob = response.data;
      const audioUrl = URL.createObjectURL(aiAudioBlob);

      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = audioUrl;
        audioPlayerRef.current.play();
      }

      setChatLog(prev => [...prev, { sender: 'ai', text: '🔊 (AI가 답변 중입니다...)' }]);

    } catch (error) {
      console.error("음성 대화 에러:", error);
      alert("AI 서버 연결 실패! 백엔드 로그를 확인하세요.");
    } finally {
      setIsProcessing(false);
    }
  };

  // // [신규] 리포트 생성 및 조회 함수
  // const handleEndInterview = async () => {
  //   if (!window.confirm("면접을 종료하고 결과를 확인하시겠습니까?")) return;

  //   setLoadingReport(true);
  //   setShowReport(true); // 모달 열기

  //   try {
  //     // 리포트 생성 API 호출
  //     const response = await axios.post(`${API_BASE_URL}/report/${SESSION_ID}`);
  //     setReportData(response.data);
  //   } catch (error) {
  //     console.error("리포트 생성 실패:", error);
  //     alert("리포트를 불러오는 중 오류가 발생했습니다.");
  //     setShowReport(false);
  //   } finally {
  //     setLoadingReport(false);
  //   }
  // };

  // [신규] 리포트 생성 및 조회 함수
  const handleEndInterview = async () => {
    if (!window.confirm("면접을 종료하고 결과를 확인하시겠습니까?")) return;

    setLoadingReport(true);
    setShowReport(true); // 모달 열기

    try {
      // 리포트 생성 API 호출
      const response = await axios.post(`${API_BASE_URL}/report/${SESSION_ID}`);
      setReportData(response.data.report); // ✅ 핵심: report만 저장

      // ✅ [추가 1] 리포트 데이터가 뭐가 오는지 콘솔 확인
      // console.log("reportData:", response.data);
      console.log("reportData(report):", response.data.report);

      // ✅ [추가 2] 결과 페이지 새 창 열기 (지금은 session_id=1로 테스트)
      // 주석 처리 (yyr) window.open(
      //   "http://127.0.0.1:5500/result.html?session_id=1",
      //   "_blank",
      //   "noopener,noreferrer"
      // ); 주석 처리 

    } catch (error) {
      console.error("리포트 생성 실패:", error);
      alert("리포트를 불러오는 중 오류가 발생했습니다.");
      setShowReport(false);
    } finally {
      setLoadingReport(false);
    }
  };


  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage_yyr />} />
      {/* ✅ B: 단독 결과 페이지 (주소로 접근) */}
      <Route
        path="/result/:threadId"
        element={<ResultRoutePage_yyr />}
      />
      {/* ✅ A: 기존 메인 화면 (모달 포함) */}
      <Route
        path="/interview"
        element={
          <RequireAuth_yyr>
            <div className="min-h-screen bg-gray-100 flex flex-col items-center py-10 font-sans relative">
              <header className="mb-8 text-center">
                <h1 className="text-4xl font-extrabold text-gray-900 mb-2">AI Interview Simulation</h1>
                <p className="text-gray-500">카메라를 보고 질문에 답해보세요.</p>
                <button
                  onClick={() => {
                    localStorage.removeItem("auth_token");
                    window.location.href = "/login";
                  }}
                  className="mt-4 px-4 py-2 rounded-lg bg-gray-200 text-gray-700 text-sm font-bold hover:bg-gray-300"
                >
                  로그아웃
                </button>
              </header>

              <main className="w-full max-w-6xl px-4 grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* 왼쪽 섹션 */}
                <section className="flex flex-col gap-4">
                  <div className="bg-white p-2 rounded-2xl shadow-lg border border-gray-200">
                    <WebcamView onVideoFrame={handleVideoFrame} isProcessing={isProcessing} />
                  </div>
                  <div className="bg-white p-6 rounded-2xl shadow-md border border-gray-200 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Vision Analysis</h3>
                      <p className="text-2xl font-bold text-blue-600 mt-1">{visionResult}</p>
                    </div>
                    <div className={`w-3 h-3 rounded-full ${visionResult !== "분석 대기 중..." ? "bg-green-500 animate-pulse" : "bg-gray-300"}`}></div>
                  </div>
                  <div className="bg-white p-6 rounded-2xl shadow-md border border-gray-200">
                    <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Resume Setup</h3>
                    {!isResumeUploaded ? (
                      <label className="flex items-center justify-center w-full p-6 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition group">
                        <div className="flex flex-col items-center">
                          <FaFileUpload className="text-3xl text-gray-400 mb-2 group-hover:text-blue-500 transition" />
                          <span className="text-sm text-gray-600 font-medium group-hover:text-blue-600">PDF 이력서 업로드하기</span>
                        </div>
                        <input type="file" className="hidden" accept=".pdf" onChange={handleFileUpload} />
                      </label>
                    ) : (
                      <div className="flex items-center gap-3 p-4 bg-green-50 text-green-700 rounded-xl border border-green-200">
                        <FaCheckCircle className="text-2xl" />
                        <div>
                          <p className="font-bold text-sm">이력서 분석 완료</p>
                          <p className="text-xs text-green-600">AI가 내용을 숙지했습니다.</p>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                {/* 오른쪽 섹션 (종료 버튼 추가됨) */}
                <section className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 flex flex-col h-[750px] relative">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
                    <h2 className="text-xl font-bold text-gray-800">💬 Interview Chat</h2>

                    {/* [신규] 종료 및 리포트 버튼 */}
                    <button
                      onClick={handleEndInterview}
                      className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 text-white text-xs font-bold rounded-lg hover:bg-black transition"
                    >
                      <FaChartBar /> 결과 보기
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-4 mb-6 pr-2">
                    {chatLog.length === 0 && (
                      <div className="text-center text-gray-400 mt-20">
                        준비가 되시면<br />이력서를 업로드하고<br />[답변 시작] 버튼을 눌러주세요.
                      </div>
                    )}
                    {chatLog.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : (msg.sender === 'system' ? 'justify-center' : 'justify-start')}`}>
                        <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm ${msg.sender === 'user'
                          ? 'bg-blue-600 text-white rounded-tr-none'
                          : (msg.sender === 'system'
                            ? 'bg-green-100 text-green-800 text-xs py-2'
                            : 'bg-gray-100 text-gray-800 rounded-tl-none')
                          }`}>
                          {msg.text}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="pt-4 border-t border-gray-100">
                    <AudioRecorder onAudioSubmit={handleAudioSubmit} isProcessing={isProcessing} />
                    <audio ref={audioPlayerRef} hidden />
                  </div>
                </section>
              </main>

              {/* [신규] 결과 리포트 모달 (Popup) */}
              {showReport && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                  <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                    <div className="p-6 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
                      <h2 className="text-2xl font-bold text-gray-900">📊 면접 분석 리포트</h2>
                      <button onClick={() => setShowReport(false)} className="text-gray-400 hover:text-gray-600">
                        <FaTimes size={24} />
                      </button>
                    </div>
                    <div className="p-6">
                      {loadingReport ? (
                        <div className="text-center py-20">
                          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                          <p className="text-gray-500">AI가 면접관들의 평가를 취합 중입니다...</p>
                        </div>
                      ) : reportData ? (
                        <ResultPage reportData={reportData} />
                      ) : (
                        <p className="text-center text-red-500">데이터를 불러오지 못했습니다.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

            </div>
          </RequireAuth_yyr>
        }
      />
    </Routes>
  );
}

export default App;