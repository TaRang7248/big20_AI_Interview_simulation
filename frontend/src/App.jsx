// 26.02.09 로그인 정보 수정

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import WebcamView from './components/WebcamView';
import AudioRecorder from './components/AudioRecorder';
import ReportModal from './components/ReportModal';
import { FaFileUpload, FaCheckCircle, FaChartBar, FaHistory, FaUserCircle, FaSignOutAlt, FaArrowLeft } from 'react-icons/fa';

// 백엔드 주소
const API_BASE_URL = "http://127.0.0.1:8001";

function App() {
  // -------------------------------------------------------------------------
  // [상태 관리] View: 'login' | 'interview' | 'mypage'
  // -------------------------------------------------------------------------
  const [view, setView] = useState("login"); 
  const [user, setUser] = useState(null); // 로그인한 유저 정보 { user_id, username }
  const [historyList, setHistoryList] = useState([]); // 마이페이지 리스트

  // 면접 관련 상태
  const [sessionId, setSessionId] = useState(""); // 매번 바뀌는 세션 ID
  const [visionResult, setVisionResult] = useState("분석 대기 중...");
  const [chatLog, setChatLog] = useState([]); 
  const [isProcessing, setIsProcessing] = useState(false);
  const [isResumeUploaded, setIsResumeUploaded] = useState(false);
  const audioPlayerRef = useRef(null);
  
  // 리포트 모달 상태
  const [showReport, setShowReport] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  // -------------------------------------------------------------------------
  // [기능 1] 로그인 & 로그아웃
  // -------------------------------------------------------------------------
  const handleLogin = async (username) => {
    if (!username.trim()) return alert("닉네임을 입력해주세요!");
    try {
      const res = await axios.post(`${API_BASE_URL}/login`, { username });
      setUser(res.data); // { user_id: 1, username: "..." }
      
      // 로그인 성공 시 새 세션 ID 발급 및 화면 이동
      setSessionId(`session_${Date.now()}`);
      setView("interview");
    } catch (error) {
      console.error(error);
      alert("로그인 서버 연결 실패");
    }
  };

  const handleLogout = () => {
    setUser(null);
    setView("login");
    setChatLog([]);
    setIsResumeUploaded(false);
  };

  // -------------------------------------------------------------------------
  // [기능 2] 마이 페이지 (이력 조회)
  // -------------------------------------------------------------------------
  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/history/${user.user_id}`);
      setHistoryList(res.data.history);
      setView("mypage");
    } catch (error) {
      console.error(error);
      alert("기록을 불러오는데 실패했습니다.");
    }
  };

  const goBackToInterview = () => {
    // 마이페이지에서 다시 면접장으로 돌아올 때
    // 새로운 마음으로 시작하도록 세션 ID 갱신 (선택사항)
    setSessionId(`session_${Date.now()}`);
    setChatLog([]);
    setIsResumeUploaded(false);
    setView("interview");
  };

  // -------------------------------------------------------------------------
  // [기능 3] 면접 로직 (이력서, 비전, 오디오)
  // -------------------------------------------------------------------------
  
  // 3-1. 이력서 업로드 (user_id 포함 전송!)
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.type !== 'application/pdf') {
      alert("PDF 파일만 업로드 가능합니다.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("thread_id", sessionId); // 현재 세션 ID
    formData.append("user_id", user.user_id); // [중요] 내 ID 같이 전송

    try {
      const response = await axios.post(`${API_BASE_URL}/upload/resume`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      
      if (response.data.status === "success") {
        setIsResumeUploaded(true);
        setChatLog(prev => [...prev, { sender: 'system', text: `✅ ${user.username}님의 이력서 분석 완료! 면접 준비가 되었습니다.` }]);
      }
    } catch (error) {
      console.error("업로드 실패:", error);
      alert("이력서 업로드 실패");
    }
  };

  // 3-2. 비전 분석
  const handleVideoFrame = async (imageBlob) => {
    if (isProcessing) return;
    try {
      const formData = new FormData();
      formData.append("file", imageBlob, "snapshot.jpg");
      const response = await axios.post(`${API_BASE_URL}/analyze/face`, formData);
      if (response.data.status === "success") {
        setVisionResult(response.data.analysis.dominant_emotion.toUpperCase()); 
      }
    } catch (error) {}
  };

  // 3-3. 음성 답변 제출
  const handleAudioSubmit = async (audioBlob) => {
    setIsProcessing(true);
    setChatLog(prev => [...prev, { sender: 'user', text: '🎤 (음성 전송 중...)' }]);

    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "user_voice.webm");
      formData.append("current_emotion", visionResult); 
      // thread_id는 쿼리 파라미터로 보냄
      const response = await axios.post(`${API_BASE_URL}/chat/voice/audio`, formData, {
        params: { thread_id: sessionId },
        responseType: 'blob', 
      });

      const aiAudioBlob = response.data;
      const audioUrl = URL.createObjectURL(aiAudioBlob);
      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = audioUrl;
        audioPlayerRef.current.play();
      }
      setChatLog(prev => [...prev, { sender: 'ai', text: '🔊 (AI가 답변 중입니다...)' }]);
    } catch (error) {
      console.error(error);
      alert("AI 서버 연결 실패");
    } finally {
      setIsProcessing(false);
    }
  };

  // 3-4. 결과 리포트 보기
  const handleEndInterview = async () => {
    if (!window.confirm("면접을 종료하고 결과를 저장하시겠습니까?")) return;
    setLoadingReport(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/report/${sessionId}`);
      setReportData(response.data);
      setShowReport(true);
    } catch (error) {
      console.error(error);
      alert("리포트 생성 실패");
    } finally {
      setLoadingReport(false);
    }
  };


  // -------------------------------------------------------------------------
  // [화면 렌더링] View 상태에 따라 다른 화면 보여주기
  // -------------------------------------------------------------------------

  // 1. 로그인 화면
  if (view === "login") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
        <div className="bg-white p-10 rounded-3xl shadow-2xl w-full max-w-md text-center transform transition-all hover:scale-105 duration-300">
          <div className="mb-6 flex justify-center">
            <div className="bg-blue-100 p-4 rounded-full">
               <FaUserCircle className="text-6xl text-blue-600" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-gray-800 mb-2">AI 면접관</h1>
          <p className="text-gray-500 mb-8">당신의 역량을 증명할 준비가 되셨나요?</p>
          
          <input 
            type="text" 
            id="usernameInput"
            placeholder="닉네임을 입력하세요 (예: 김개발)" 
            className="w-full border-2 border-gray-200 p-4 rounded-xl mb-4 text-lg focus:outline-none focus:border-blue-500 transition"
            onKeyDown={(e) => e.key === 'Enter' && handleLogin(e.target.value)}
          />
          <button 
            onClick={() => handleLogin(document.getElementById("usernameInput").value)}
            className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold text-lg hover:bg-blue-700 shadow-lg hover:shadow-xl transition"
          >
            면접 시작하기 🚀
          </button>
        </div>
      </div>
    );
  }

  // 2. 마이 페이지 (이력 리스트)
  if (view === "mypage") {
    return (
      <div className="min-h-screen bg-gray-50 p-6 md:p-12">
        <div className="max-w-5xl mx-auto">
          <div className="flex justify-between items-center mb-10">
            <div>
              <h2 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
                <FaHistory className="text-blue-600" /> 
                {user.username}님의 면접 기록
              </h2>
              <p className="text-gray-500 mt-2">지난 면접 결과를 복기하며 성장하세요.</p>
            </div>
            <button 
              onClick={goBackToInterview}
              className="bg-gray-800 text-white px-6 py-3 rounded-xl font-bold hover:bg-black transition flex items-center gap-2 shadow-lg"
            >
              <FaArrowLeft /> 새로운 면접 보기
            </button>
          </div>
          
          <div className="grid gap-6">
            {historyList.length === 0 ? (
              <div className="text-center py-20 bg-white rounded-2xl shadow-sm border border-gray-200">
                <p className="text-gray-400 text-xl">아직 진행한 면접 기록이 없습니다.</p>
              </div>
            ) : (
              historyList.map((item, idx) => (
                <div key={idx} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition flex flex-col md:flex-row justify-between items-center gap-6">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-sm font-bold text-gray-400">SESSION #{item.session_id}</span>
                      <span className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-md">{item.date}</span>
                    </div>
                    <p className="text-gray-700 font-medium leading-relaxed">
                      {item.summary || "요약 정보가 없습니다."}
                    </p>
                  </div>
                  
                  <div className="flex items-center gap-6">
                    {/* 점수 뱃지 */}
                    <div className="text-center">
                      <div className="text-sm text-gray-400 mb-1">Total Score</div>
                      <div className={`text-3xl font-extrabold ${item.total_score >= 80 ? 'text-green-500' : (item.total_score >= 60 ? 'text-yellow-500' : 'text-red-500')}`}>
                        {item.total_score}
                      </div>
                    </div>
                    
                    {/* 상세 점수 미니 뷰 (Models 수정 후 적용됨) */}
                    {item.scores && (
                       <div className="text-xs text-gray-400 grid grid-cols-1 gap-1 border-l pl-6">
                          <div>직무: {item.scores.tech}</div>
                          <div>소통: {item.scores.comm}</div>
                          <div>문제: {item.scores.prob}</div>
                       </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    );
  }

  // 3. 면접 화면 (기존 App)
  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center py-10 font-sans relative">
      
      {/* 상단 네비게이션 */}
      <div className="w-full max-w-6xl px-4 mb-6 flex justify-between items-center">
        <h1 className="text-2xl font-extrabold text-gray-800">AI Interview Simulation</h1>
        <div className="flex items-center gap-4">
           <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-sm border border-gray-200">
              <FaUserCircle className="text-gray-400" />
              <span className="font-bold text-gray-700">{user.username}</span>
           </div>
           <button onClick={fetchHistory} className="bg-white text-blue-600 border border-blue-200 px-4 py-2 rounded-lg font-bold hover:bg-blue-50 transition flex items-center gap-2">
             <FaHistory /> 내 기록
           </button>
           <button onClick={handleLogout} className="text-gray-500 hover:text-red-500 transition px-2">
             <FaSignOutAlt size={20} />
           </button>
        </div>
      </div>

      <main className="w-full max-w-6xl px-4 grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* 왼쪽: 카메라 & 이력서 */}
        <section className="flex flex-col gap-4">
          <div className="bg-white p-2 rounded-2xl shadow-lg border border-gray-200">
            <WebcamView onVideoFrame={handleVideoFrame} isProcessing={isProcessing} />
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-2xl shadow-md border border-gray-200">
              <h3 className="text-xs font-bold text-gray-400 uppercase mb-1">Emotion</h3>
              <p className="text-xl font-bold text-blue-600">{visionResult}</p>
            </div>
             <div className="bg-white p-4 rounded-2xl shadow-md border border-gray-200">
              <h3 className="text-xs font-bold text-gray-400 uppercase mb-1">Status</h3>
              <p className={`text-xl font-bold ${isResumeUploaded ? 'text-green-600' : 'text-gray-400'}`}>
                {isResumeUploaded ? "준비 완료" : "이력서 대기"}
              </p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-md border border-gray-200">
             {!isResumeUploaded ? (
                <label className="flex items-center justify-center w-full p-6 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition group">
                  <div className="flex flex-col items-center">
                    <FaFileUpload className="text-3xl text-gray-400 mb-2 group-hover:text-blue-500 transition" />
                    <span className="text-sm text-gray-600 font-medium group-hover:text-blue-600">PDF 이력서 업로드</span>
                  </div>
                  <input type="file" className="hidden" accept=".pdf" onChange={handleFileUpload} />
                </label>
              ) : (
                <div className="flex items-center gap-3 p-4 bg-green-50 text-green-700 rounded-xl border border-green-200">
                  <FaCheckCircle className="text-2xl" />
                  <div>
                    <p className="font-bold text-sm">이력서 분석 완료</p>
                    <p className="text-xs text-green-600">AI가 {user.username}님의 이력서를 학습했습니다.</p>
                  </div>
                </div>
              )}
          </div>
        </section>

        {/* 오른쪽: 채팅 & 음성 */}
        <section className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 flex flex-col h-[700px] relative">
           <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
             <h2 className="text-xl font-bold text-gray-800">💬 Live Chat</h2>
             <button 
               onClick={handleEndInterview}
               className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 text-white text-xs font-bold rounded-lg hover:bg-black transition"
             >
               <FaChartBar /> 결과 보기 & 저장
             </button>
           </div>
           
           <div className="flex-1 overflow-y-auto space-y-4 mb-6 pr-2">
             {chatLog.length === 0 && (
               <div className="text-center text-gray-400 mt-20 flex flex-col items-center">
                 <p className="mb-2">안녕하세요, <b>{user.username}</b>님!</p>
                 <p className="text-sm">이력서를 업로드하고<br/>[답변 시작] 버튼을 눌러주세요.</p>
               </div>
             )}
             {chatLog.map((msg, idx) => (
               <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                 <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm ${
                   msg.sender === 'user' 
                     ? 'bg-blue-600 text-white rounded-tr-none' 
                     : 'bg-gray-100 text-gray-800 rounded-tl-none'
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

      {/* 리포트 모달 */}
      <ReportModal 
        isOpen={showReport} 
        onClose={() => setShowReport(false)} 
        reportData={reportData} 
      />

      {/* 로딩 인디케이터 */}
      {loadingReport && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-[60]">
          <div className="bg-white p-6 rounded-xl shadow-xl flex flex-col items-center animate-bounce-short">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-3"></div>
            <p className="text-gray-700 font-bold">결과 분석 및 DB 저장 중...</p>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;