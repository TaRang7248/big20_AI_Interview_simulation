"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Header from "@/components/common/Header";
import EventToastContainer from "@/components/common/EventToast";
import InterviewReportCharts, { ReportData } from "@/components/report/InterviewReportCharts";
import { sessionApi, interviewApi, ttsApi, interventionApi, resumeApi, didApi } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import { Mic, MicOff, Camera, CameraOff, PhoneOff, SkipForward, Volume2, Loader2, FileText, Download, LayoutDashboard, AlertTriangle, Upload } from "lucide-react";

/* Web Speech API 타입 (브라우저 전용) */
type SpeechRecognitionType = typeof window extends { SpeechRecognition: infer T } ? T : unknown;
declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
  interface SpeechRecognition extends EventTarget {
    lang: string; continuous: boolean; interimResults: boolean;
    start(): void; stop(): void; abort(): void;
    onresult: ((ev: SpeechRecognitionEvent) => void) | null;
    onerror: ((ev: Event) => void) | null;
    onend: (() => void) | null;
  }
  interface SpeechRecognitionEvent extends Event {
    readonly resultIndex: number;
    readonly results: SpeechRecognitionResultList;
  }
  interface SpeechRecognitionResultList { readonly length: number; item(index: number): SpeechRecognitionResult; [index: number]: SpeechRecognitionResult; }
  interface SpeechRecognitionResult { readonly length: number; readonly isFinal: boolean; item(index: number): SpeechRecognitionAlternative; [index: number]: SpeechRecognitionAlternative; }
  interface SpeechRecognitionAlternative { readonly transcript: string; readonly confidence: number; }
}

type Phase = "setup" | "interview" | "coding" | "whiteboard" | "report";
type Status = "ready" | "listening" | "speaking" | "processing";

// Next.js App Router에서 useSearchParams 사용 시 Suspense boundary 필요
export default function InterviewPageWrapper() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center"><div className="text-[var(--text-secondary)]">로딩 중...</div></div>}>
      <InterviewPageInner />
    </Suspense>
  );
}

function InterviewPageInner() {
  const { user, token, loading } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  // URL 에서 공고 ID 추출 (ex: /interview?job_posting_id=3)
  const jobPostingId = searchParams.get("job_posting_id");

  // 상태
  const [phase, setPhase] = useState<Phase>("setup");
  const [status, setStatus] = useState<Status>("ready");
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<{ role: "ai" | "user"; text: string }[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [questionNum, setQuestionNum] = useState(0);
  const totalQuestions = 9;
  const [sttText, setSttText] = useState("");
  const [micEnabled, setMicEnabled] = useState(true);
  const [camEnabled, setCamEnabled] = useState(true);
  const [interviewStarted, setInterviewStarted] = useState(false);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  // 이력서 미업로드 경고 모달 상태 (UX 개선)
  const [showResumeWarning, setShowResumeWarning] = useState(false);
  const [resumeWarningMsg, setResumeWarningMsg] = useState("");
  const [pendingSessionId, setPendingSessionId] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resumeUploading, setResumeUploading] = useState(false);

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);           // setup 카메라 프리뷰용
  const interviewVideoRef = useRef<HTMLVideoElement>(null);  // interview 화면 사용자 영상용
  const streamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const interventionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pushEventRef = useRef<((raw: Record<string, unknown>) => void) | null>(null);

  // ── D-ID AI 아바타 상태 ──
  const [didAvailable, setDidAvailable] = useState(false);   // D-ID API 사용 가능 여부
  const [didConnected, setDidConnected] = useState(false);   // WebRTC 연결 완료 여부
  const [didLoading, setDidLoading] = useState(false);       // D-ID 스트림 연결 진행 중
  const avatarVideoRef = useRef<HTMLVideoElement>(null);     // D-ID 아바타 영상 <video>
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null); // WebRTC PC

  // 인증 확인 — loading 완료 후에만 리다이렉트 (sessionStorage 복원 대기)
  useEffect(() => {
    if (!loading && !token) router.push("/");
  }, [loading, token, router]);

  // 리포트 데이터 로드
  useEffect(() => {
    if (phase !== "report" || !sessionId) return;
    setReportLoading(true);
    interviewApi
      .getReport(sessionId)
      .then((data) => setReportData(data as ReportData))
      .catch((err) => console.error("리포트 로드 실패:", err))
      .finally(() => setReportLoading(false));
  }, [phase, sessionId]);

  // 채팅 자동 스크롤
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ── D-ID 사용 가능 여부 확인 (컴포넌트 마운트 시 1회) ──
  useEffect(() => {
    didApi.status()
      .then(res => {
        setDidAvailable(res.available);
        if (res.available) console.log("✅ D-ID AI 아바타 사용 가능");
      })
      .catch(() => setDidAvailable(false));
  }, []);

  // ── setup 화면 카메라 프리뷰 자동 초기화 ──
  // phase가 "setup"일 때 카메라를 바로 켜서 프리뷰 영상을 보여줌
  useEffect(() => {
    if (phase !== "setup" || !user) return;
    let cancelled = false;
    (async () => {
      try {
        // 이미 스트림이 있으면 재사용
        if (streamRef.current) {
          if (videoRef.current) videoRef.current.srcObject = streamRef.current;
          return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch {
        // 권한 거부 등 — setup 화면에서는 조용히 무시 (시작 버튼 클릭 시 재시도)
      }
    })();
    return () => { cancelled = true; };
  }, [phase, user]);

  // ── interview 화면 전환 시 사용자 비디오 스트림 재할당 ──
  // phase가 "interview"로 바뀌면 새로 마운트된 <video>에 srcObject를 연결
  // requestAnimationFrame으로 DOM 마운트 완료를 보장
  useEffect(() => {
    if (phase !== "interview" || !streamRef.current) return;
    const assignStream = () => {
      if (interviewVideoRef.current && streamRef.current) {
        interviewVideoRef.current.srcObject = streamRef.current;
      } else {
        // ref가 아직 연결되지 않았으면 재시도
        requestAnimationFrame(assignStream);
      }
    };
    requestAnimationFrame(assignStream);
  }, [phase]);

  // 클린업 (카메라, WebSocket, 음성인식, D-ID WebRTC)
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop());
      wsRef.current?.close();
      recognitionRef.current?.stop();
      if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
      // D-ID 정리
      peerConnectionRef.current?.close();
      peerConnectionRef.current = null;
    };
  }, []);

  /**
   * D-ID WebRTC 아바타 스트림 연결
   * —————————————————————————————
   * 1. /api/did/stream/create → SDP Offer + ICE 서버 정보 수신
   * 2. RTCPeerConnection 생성 → Remote Description 설정
   * 3. SDP Answer 생성 → /api/did/stream/sdp 전송
   * 4. ICE Candidate → /api/did/stream/ice 전송
   * 5. ontrack 이벤트로 수신한 비디오를 avatarVideoRef에 연결
   */
  const initDIDAvatar = async (sid: string) => {
    if (!didAvailable) return;
    setDidLoading(true);
    try {
      // 1단계: 스트림 생성 요청
      const streamRes = await didApi.createStream(sid);
      if (!streamRes.success || !streamRes.offer) {
        console.warn("D-ID 스트림 생성 실패:", streamRes);
        return;
      }

      // 2단계: RTCPeerConnection 생성
      const pc = new RTCPeerConnection({
        iceServers: streamRes.ice_servers || [{ urls: "stun:stun.l.google.com:19302" }],
      });
      peerConnectionRef.current = pc;

      // 수신 트랙 처리 → 아바타 비디오에 연결
      pc.ontrack = (event) => {
        if (event.streams?.[0] && avatarVideoRef.current) {
          avatarVideoRef.current.srcObject = event.streams[0];
          setDidConnected(true);
          console.log("✅ D-ID 아바타 비디오 스트림 연결됨");
        }
      };

      // ICE Candidate 수집 → 서버로 전송
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          didApi.sendIceCandidate(sid, event.candidate.toJSON()).catch(() => {});
        }
      };

      pc.onconnectionstatechange = () => {
        console.log(`[D-ID WebRTC] 연결 상태: ${pc.connectionState}`);
        if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
          setDidConnected(false);
        }
      };

      // 3단계: Remote SDP Offer 설정 → Local SDP Answer 생성
      await pc.setRemoteDescription(new RTCSessionDescription(streamRes.offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // 4단계: SDP Answer를 D-ID 서버에 전송
      await didApi.sendSdpAnswer(sid, answer);

      // 5단계: 스트림 시작
      await didApi.startStream(sid);
      console.log("✅ D-ID 아바타 스트림 시작");
    } catch (err) {
      console.error("D-ID 아바타 초기화 실패:", err);
      // D-ID 실패해도 면접은 계속 진행 (CSS 폴백 아바타 사용)
    } finally {
      setDidLoading(false);
    }
  };

  // ========== 면접 시작 ==========
  const startInterview = async () => {
    if (!user) return;
    try {
      // 카메라 초기화 — setup useEffect에서 이미 스트림이 있으면 재사용
      if (!streamRef.current) {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        streamRef.current = stream;
      }

      // 세션 생성 (공고 ID가 있으면 함께 전달)
      const createData: { user_email: string; interview_type: string; job_posting_id?: number } = {
        user_email: user.email,
        interview_type: "technical",
      };
      if (jobPostingId) {
        createData.job_posting_id = Number(jobPostingId);
      }
      const res = await sessionApi.create(createData);
      setSessionId(res.session_id);

      // 이력서 미업로드 시 경고 모달 표시 (UX 개선)
      if (!res.resume_uploaded && res.resume_warning) {
        setPendingSessionId(res.session_id);
        setResumeWarningMsg(res.resume_warning);
        setShowResumeWarning(true);
        return; // 경고 모달에서 선택 후 면접 진행
      }

      // 이력서가 이미 업로드된 경우 바로 면접 진행
      await proceedInterview(res.session_id);
    } catch (err) {
      console.error("면접 시작 실패:", err);
      toast.error("면접 시작에 실패했습니다. 카메라/마이크 권한을 확인해주세요.");
    }
  };

  /**
   * 면접 세션 진행 (WebSocket 연결 → 음성인식 → 첫 질문)
   * 이력서 경고 모달에서 '이력서 없이 진행' 또는 '이력서 업로드 후 진행' 모두 이 함수를 호출
   */
  const proceedInterview = async (sid: string) => {
    try {
      // 카메라가 아직 초기화되지 않은 경우 (경고 모달에서 이력서 업로드 후 재진행)
      if (!streamRef.current) {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        streamRef.current = stream;
      }

      // WebSocket 연결
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsToken = sessionStorage.getItem("access_token");
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/interview/${sid}?token=${encodeURIComponent(wsToken || "")}`);
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "stt_result" && data.is_final) {
            setSttText(prev => prev + " " + data.transcript);
          }
          if (data.type === "event" && pushEventRef.current) {
            pushEventRef.current(data);
          }
        } catch { /* ignore */ }
      };
      wsRef.current = ws;

      initSpeechRecognition();
      setPhase("interview");
      setInterviewStarted(true);
      setSessionId(sid);

      // D-ID 아바타 초기화 (비동기 — 면접 진행을 블로킹하지 않음)
      initDIDAvatar(sid);

      await getNextQuestion(sid, "[START]");
    } catch (err) {
      console.error("면접 진행 실패:", err);
      toast.error("면접 시작에 실패했습니다.");
    }
  };

  /**
   * 이력서 경고 모달에서 이력서 업로드 처리
   */
  const handleResumeUploadInWarning = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("PDF 파일만 업로드 가능합니다.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error("파일 크기는 10MB 이하여야 합니다.");
      return;
    }
    setResumeUploading(true);
    try {
      await resumeApi.upload(file, pendingSessionId, user!.email);
      setShowResumeWarning(false);
      // 이력서 업로드 완료 후 면접 진행
      await proceedInterview(pendingSessionId);
    } catch {
      toast.error("이력서 업로드 실패. 다시 시도해주세요.");
    } finally {
      setResumeUploading(false);
    }
  };

  /**
   * 이력서 없이 면접 진행
   */
  const proceedWithoutResume = async () => {
    setShowResumeWarning(false);
    await proceedInterview(pendingSessionId);
  };

  // ========== 음성 인식 (Web Speech API) ==========
  const initSpeechRecognition = () => {
    const SR = window.webkitSpeechRecognition || window.SpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognition.lang = "ko-KR";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
      }
      if (final) setSttText(prev => prev + " " + final);
    };

    recognition.onend = () => { if (interviewStarted && micEnabled) recognition.start(); };
    recognitionRef.current = recognition;
    recognition.start();
  };

  // ========== 질문 요청 ==========
  const getNextQuestion = async (sid: string, message: string) => {
    setStatus("processing");
    try {
      const res = await interviewApi.chat({ session_id: sid, message, mode: "interview" });
      const q = res.response;
      setCurrentQuestion(q);
      setQuestionNum(res.question_number || questionNum + 1);
      setMessages(prev => [...prev, { role: "ai", text: q }]);
      await speakQuestion(q);
      setStatus("listening");

      // 개입 체크 시작
      startInterventionCheck(sid);
    } catch { setStatus("ready"); }
  };

  // ========== TTS 발화 + D-ID 립싱크 ==========
  const speakQuestion = async (text: string) => {
    setStatus("speaking");

    // D-ID 아바타가 연결된 경우: D-ID 립싱크도 병렬로 요청
    // (D-ID는 자체 TTS를 사용하여 립싱크 영상을 생성)
    if (didConnected && sessionId) {
      didApi.speak(sessionId, text, "female").catch(err =>
        console.warn("D-ID speak 실패 (음성은 Hume TTS로 재생):", err)
      );
    }

    try {
      const blob = await ttsApi.speak(text, "professional");
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      await new Promise<void>((resolve) => {
        audio.onended = () => resolve();
        audio.onerror = () => resolve();
        audio.play().catch(() => resolve());
      });
      URL.revokeObjectURL(url);
    } catch {
      // TTS 실패 시 Web Speech API 폴백
      try {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "ko-KR";
        speechSynthesis.speak(utterance);
      } catch { /* ignore */ }
    }
  };

  // ========== 개입 체크 ==========
  const startInterventionCheck = (sid: string) => {
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    interventionApi.startTurn(sid).catch(() => {});
    interventionTimerRef.current = setInterval(async () => {
      try {
        const res = await interventionApi.check(sid, sttText);
        if (res.should_intervene && res.message) {
          setMessages(prev => [...prev, { role: "ai", text: `💡 ${res.message}` }]);
          await speakQuestion(res.message);
        }
      } catch { /* ignore */ }
    }, 3000);
  };

  // ========== 답변 제출 ==========
  const submitAnswer = async () => {
    if (!sttText.trim()) return;
    const answer = sttText.trim();
    setSttText("");
    setMessages(prev => [...prev, { role: "user", text: answer }]);

    // 개입 타이머 정지
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    interventionApi.endTurn(sessionId, answer).catch(() => {});

    // 평가
    setStatus("processing");
    try {
      await interviewApi.evaluate({
        session_id: sessionId,
        question: currentQuestion,
        answer,
        question_number: questionNum,
      });
    } catch { /* ignore */ }

    // 다음 질문 or 종료
    if (questionNum >= totalQuestions) {
      endInterview();
    } else {
      await getNextQuestion(sessionId, answer);
    }
  };

  // ========== 면접 종료 ==========
  const endInterview = async () => {
    setInterviewStarted(false);
    recognitionRef.current?.stop();
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);

    // D-ID 스트림 종료
    if (didConnected && sessionId) {
      didApi.closeStream(sessionId).catch(() => {});
      peerConnectionRef.current?.close();
      peerConnectionRef.current = null;
      setDidConnected(false);
    }

    setPhase("coding");
  };

  // ========== 마이크/카메라 토글 ==========
  const toggleMic = () => {
    const track = streamRef.current?.getAudioTracks()[0];
    if (track) { track.enabled = !track.enabled; setMicEnabled(track.enabled); }
  };
  const toggleCam = () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (track) { track.enabled = !track.enabled; setCamEnabled(track.enabled); }
  };

  if (!user) return null;

  // ========== 렌더링 ==========
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      {/* 실시간 이벤트 알림 (EventBus → WebSocket) */}
      <EventToastContainer onPushEvent={(handler) => { pushEventRef.current = handler; }} />

      {/* ========== 이력서 미업로드 경고 모달 (UX 개선) ========== */}
      {showResumeWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass-card max-w-md w-full mx-4 p-6">
            {/* 경고 아이콘 + 제목 */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-[rgba(255,193,7,0.15)] flex items-center justify-center">
                <AlertTriangle size={24} className="text-[var(--warning)]" />
              </div>
              <h3 className="text-lg font-bold">이력서가 업로드되지 않았습니다</h3>
            </div>

            {/* 경고 메시지 */}
            <p className="text-sm text-[var(--text-secondary)] mb-2">
              {resumeWarningMsg}
            </p>
            <div className="bg-[rgba(255,193,7,0.08)] border border-[rgba(255,193,7,0.2)] rounded-xl p-3 mb-6">
              <p className="text-xs text-[var(--warning)]">
                💡 이력서를 업로드하면 지원 직무·경력에 맞춘 <strong>맞춤형 질문</strong>을 받을 수 있어 더 효과적인 면접 연습이 됩니다.
              </p>
            </div>

            {/* 이력서 업로드 영역 */}
            <div
              className="border-2 border-dashed border-[rgba(0,217,255,0.3)] rounded-xl p-6 text-center cursor-pointer hover:border-[var(--cyan)] hover:bg-[rgba(0,217,255,0.03)] transition-all mb-4"
              onClick={() => fileInputRef.current?.click()}
            >
              {resumeUploading ? (
                <div className="flex flex-col items-center">
                  <Loader2 size={28} className="animate-spin text-[var(--cyan)] mb-2" />
                  <p className="text-sm text-[var(--text-secondary)]">업로드 중...</p>
                </div>
              ) : (
                <>
                  <Upload size={28} className="mx-auto mb-2 text-[var(--cyan)]" />
                  <p className="text-sm text-[var(--text-secondary)]">PDF 이력서를 클릭하여 업로드</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-1">최대 10MB</p>
                </>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              hidden
              onChange={(e) => e.target.files?.[0] && handleResumeUploadInWarning(e.target.files[0])}
            />

            {/* 액션 버튼 */}
            <div className="flex gap-3">
              <button
                onClick={proceedWithoutResume}
                disabled={resumeUploading}
                className="flex-1 px-4 py-3 rounded-xl text-sm font-semibold border border-[rgba(255,255,255,0.15)] text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] transition disabled:opacity-40"
              >
                이력서 없이 진행
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={resumeUploading}
                className="flex-1 btn-gradient px-4 py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-40"
              >
                <Upload size={16} /> 이력서 업로드
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 면접 준비 화면 */}
      {phase === "setup" && (
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="glass-card max-w-lg w-full text-center">
            <h1 className="text-3xl font-bold gradient-text mb-4">AI 모의면접</h1>
            <p className="text-[var(--text-secondary)] mb-8">
              카메라와 마이크가 준비되었는지 확인한 후<br />면접을 시작해주세요.
            </p>
            <div className="rounded-xl overflow-hidden bg-black aspect-video mb-6">
              <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
            </div>
            <button onClick={startInterview} className="btn-gradient text-lg px-12 py-4 rounded-2xl">
              🎤 면접 시작
            </button>
          </div>
        </main>
      )}

      {/* 면접 진행 화면 */}
      {phase === "interview" && (
        <main className="flex-1 flex flex-col p-4 max-w-[1400px] mx-auto w-full">
          {/* 상태 바 */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className={`px-4 py-1.5 rounded-full text-sm font-semibold ${
                status === "ready" ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]" :
                status === "listening" ? "bg-[rgba(255,193,7,0.2)] text-[var(--warning)]" :
                status === "speaking" ? "bg-[rgba(0,217,255,0.2)] text-[var(--cyan)]" :
                "bg-[rgba(156,39,176,0.2)] text-purple-300"
              }`}>
                {status === "ready" && "대기"}
                {status === "listening" && "🎤 듣는 중..."}
                {status === "speaking" && "🔊 발화 중..."}
                {status === "processing" && "⏳ 처리 중..."}
              </span>
              <span className="text-sm text-[var(--text-secondary)]">질문 {questionNum}/{totalQuestions}</span>
            </div>
            <button onClick={endInterview} className="px-4 py-2 text-sm rounded-lg bg-[rgba(244,67,54,0.2)] text-[var(--danger)] border border-[rgba(244,67,54,0.3)] hover:bg-[rgba(244,67,54,0.3)] transition">
              면접 종료
            </button>
          </div>

          {/* 진행 바 */}
          <div className="flex gap-1 mb-6">
            {Array.from({ length: totalQuestions }, (_, i) => (
              <div key={i} className={`h-1.5 flex-1 rounded-full transition-all ${
                i < questionNum ? "bg-gradient-to-r from-[var(--cyan)] to-[var(--green)]" :
                i === questionNum ? "bg-[var(--cyan)] animate-pulse" : "bg-[rgba(255,255,255,0.1)]"
              }`} />
            ))}
          </div>

          {/* 2열 레이아웃 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1">
            {/* AI 면접관 아바타 */}
            <div className="glass-card flex flex-col">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Volume2 size={16} className="text-[var(--cyan)]" /> AI 면접관
                {/* D-ID 연결 상태 배지 */}
                {didLoading && <span className="text-xs text-[var(--warning)] animate-pulse">아바타 연결 중...</span>}
                {didConnected && <span className="text-xs text-[var(--green)]">● LIVE</span>}
              </h3>
              <div className="flex-1 rounded-xl bg-gradient-to-br from-[#1e3a5f] to-[#0d2137] flex items-center justify-center min-h-[200px] relative overflow-hidden">

                {/* ══ D-ID WebRTC 아바타 비디오 (연결 성공 시 표시) ══ */}
                {didConnected && (
                  <video
                    ref={avatarVideoRef}
                    autoPlay
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover rounded-xl"
                  />
                )}

                {/* ══ CSS 폴백 아바타 (D-ID 미연결 시 표시) ══ */}
                {!didConnected && (
                  <>
                    {/* 발화 상태 배경 파동 효과 */}
                    {status === "speaking" && (
                      <>
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                          <div className="w-64 h-64 rounded-full bg-[rgba(0,255,136,0.06)] animate-ping" style={{ animationDuration: "2s" }} />
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                          <div className="w-52 h-52 rounded-full bg-[rgba(0,217,255,0.08)] animate-ping" style={{ animationDuration: "2.5s" }} />
                        </div>
                      </>
                    )}
                    {/* 처리 중 배경 효과 */}
                    {status === "processing" && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="w-56 h-56 rounded-full border-2 border-dashed border-[rgba(156,39,176,0.3)] animate-spin" style={{ animationDuration: "4s" }} />
                      </div>
                    )}
                    {/* D-ID 로딩 중 */}
                    {didLoading && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center z-10">
                        <Loader2 size={40} className="text-[var(--cyan)] animate-spin mb-3" />
                        <span className="text-sm text-[var(--text-secondary)]">AI 아바타 연결 중...</span>
                      </div>
                    )}
                    {/* 아바타 원형 */}
                    {!didLoading && (
                      <div className={`relative w-48 h-48 rounded-full border-4 transition-all duration-500 ${
                        status === "speaking"
                          ? "border-[var(--green)] shadow-[0_0_40px_rgba(0,255,136,0.5)] scale-105"
                          : status === "processing"
                          ? "border-purple-400 shadow-[0_0_20px_rgba(156,39,176,0.3)]"
                          : status === "listening"
                          ? "border-[var(--warning)] shadow-[0_0_20px_rgba(255,193,7,0.3)]"
                          : "border-[var(--cyan)]"
                      } bg-gradient-to-br from-[#2a4a6b] to-[#1a3050] flex items-center justify-center`}>
                        {/* 발화 중 이퀄라이저 바 */}
                        {status === "speaking" ? (
                          <div className="flex items-end gap-1.5 h-16">
                            {[0, 1, 2, 3, 4].map(i => (
                              <div
                                key={i}
                                className="w-2.5 bg-gradient-to-t from-[var(--cyan)] to-[var(--green)] rounded-full"
                                style={{
                                  animation: `equalizer 0.8s ease-in-out ${i * 0.15}s infinite alternate`,
                                  height: `${20 + Math.random() * 30}px`,
                                }}
                              />
                            ))}
                          </div>
                        ) : status === "processing" ? (
                          <Loader2 size={48} className="text-purple-300 animate-spin" />
                        ) : (
                          <span className="text-6xl">🤖</span>
                        )}
                      </div>
                    )}
                  </>
                )}

                {/* 상태 라벨 (D-ID/폴백 공통) */}
                <span className={`absolute bottom-3 left-3 text-xs px-2 py-1 rounded font-medium z-20 ${
                  status === "speaking" ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]"
                    : status === "processing" ? "bg-[rgba(156,39,176,0.2)] text-purple-300"
                    : status === "listening" ? "bg-[rgba(255,193,7,0.2)] text-[var(--warning)]"
                    : "bg-black/60 text-white"
                }`}>
                  {status === "speaking" ? "🔊 답변 중..."
                    : status === "processing" ? "⏳ 생각 중..."
                    : status === "listening" ? "👂 경청 중..."
                    : "AI 면접관"}
                </span>
              </div>
            </div>

            {/* 채팅/비디오 */}
            <div className="glass-card flex flex-col">
              {/* 사용자 비디오 (작게) */}
              <div className="rounded-xl overflow-hidden bg-black h-32 mb-3 relative">
                <video ref={interviewVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
                <span className="absolute bottom-2 right-2 text-xs bg-black/60 px-2 py-0.5 rounded text-white">
                  {camEnabled ? "카메라 ON" : "카메라 OFF"}
                </span>
              </div>

              {/* 채팅 로그 */}
              <div className="flex-1 overflow-y-auto space-y-3 mb-3 min-h-[200px] max-h-[400px] pr-2">
                {messages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                      m.role === "user"
                        ? "bg-gradient-to-r from-[rgba(0,217,255,0.15)] to-[rgba(0,255,136,0.1)] rounded-br-md"
                        : "bg-[rgba(255,255,255,0.06)] rounded-bl-md"
                    }`}>
                      {m.text}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              {/* STT 인식 텍스트 */}
              {status === "listening" && (
                <div className="bg-[rgba(255,193,7,0.08)] border border-[rgba(255,193,7,0.2)] rounded-xl p-3 mb-3">
                  <p className="text-xs text-[var(--warning)] mb-1">🎤 음성 인식 중...</p>
                  <p className="text-sm">{sttText || "말씀해주세요..."}</p>
                </div>
              )}

              {/* 컨트롤 */}
              <div className="flex items-center justify-center gap-4">
                <button onClick={toggleMic} className={`w-12 h-12 rounded-full flex items-center justify-center transition ${
                  micEnabled ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]" : "bg-[rgba(255,82,82,0.2)] text-[var(--danger)]"
                }`}>
                  {micEnabled ? <Mic size={20} /> : <MicOff size={20} />}
                </button>
                <button onClick={toggleCam} className={`w-12 h-12 rounded-full flex items-center justify-center transition ${
                  camEnabled ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]" : "bg-[rgba(255,82,82,0.2)] text-[var(--danger)]"
                }`}>
                  {camEnabled ? <Camera size={20} /> : <CameraOff size={20} />}
                </button>
                <button onClick={submitAnswer} disabled={!sttText.trim() || status !== "listening"}
                  className="btn-gradient !rounded-full w-12 h-12 flex items-center justify-center disabled:opacity-40">
                  <SkipForward size={20} />
                </button>
                <button onClick={endInterview} className="w-12 h-12 rounded-full bg-[rgba(244,67,54,0.8)] text-white flex items-center justify-center hover:bg-[rgba(244,67,54,1)] transition">
                  <PhoneOff size={20} />
                </button>
              </div>
            </div>
          </div>
        </main>
      )}

      {/* 코딩 테스트 Phase */}
      {phase === "coding" && (
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="glass-card max-w-lg text-center">
            <h2 className="text-2xl font-bold gradient-text mb-4">💻 코딩 테스트</h2>
            <p className="text-[var(--text-secondary)] mb-6">
              화상 면접이 완료되었습니다. 코딩 테스트를 시작하시겠습니까?
            </p>
            <div className="flex gap-4 justify-center">
              <button onClick={() => router.push(`/coding?session=${sessionId}`)} className="btn-gradient px-8 py-3">
                코딩 테스트 시작
              </button>
              <button onClick={() => setPhase("whiteboard")} className="px-8 py-3 rounded-xl border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition">
                건너뛰기
              </button>
            </div>
          </div>
        </main>
      )}

      {/* 화이트보드 Phase */}
      {phase === "whiteboard" && (
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="glass-card max-w-lg text-center">
            <h2 className="text-2xl font-bold gradient-text mb-4">🎨 아키텍처 설계</h2>
            <p className="text-[var(--text-secondary)] mb-6">
              화이트보드에 시스템 아키텍처를 설계해보세요.
            </p>
            <div className="flex gap-4 justify-center">
              <button onClick={() => router.push(`/whiteboard?session=${sessionId}`)} className="btn-gradient px-8 py-3">
                설계 시작
              </button>
              <button onClick={() => setPhase("report")} className="px-8 py-3 rounded-xl border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition">
                결과 보기
              </button>
            </div>
          </div>
        </main>
      )}

      {/* 리포트 Phase */}
      {phase === "report" && (
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto space-y-6">
            {/* 로딩 상태 */}
            {reportLoading && (
              <div className="flex flex-col items-center justify-center py-20">
                <Loader2 className="w-10 h-10 text-[var(--cyan)] animate-spin mb-4" />
                <p className="text-[var(--text-secondary)]">리포트를 생성하고 있습니다…</p>
              </div>
            )}

            {/* 차트 리포트 */}
            {!reportLoading && reportData && (
              <InterviewReportCharts report={reportData} />
            )}

            {/* 데이터 없을 때 */}
            {!reportLoading && !reportData && (
              <div className="glass-card text-center py-12">
                <h2 className="text-2xl font-bold gradient-text mb-4">📊 면접 완료!</h2>
                <p className="text-[var(--text-secondary)]">리포트 데이터를 불러올 수 없습니다.</p>
              </div>
            )}

            {/* 하단 액션 버튼 */}
            <div className="flex gap-4 justify-center flex-wrap pb-8">
              <button
                onClick={() => window.open(`/api/report/${sessionId}`, "_blank")}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-[rgba(0,217,255,0.15)] border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.25)] transition"
              >
                <FileText className="w-4 h-4" /> JSON 원본
              </button>
              <button
                onClick={() => {
                  const tk = localStorage.getItem("token");
                  fetch(`/api/report/${sessionId}/pdf`, {
                    headers: { Authorization: `Bearer ${tk}` },
                  })
                    .then((res) => {
                      if (!res.ok) throw new Error("PDF 생성 실패");
                      return res.blob();
                    })
                    .then((blob) => {
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `interview_report_${sessionId?.slice(0, 8)}.pdf`;
                      a.click();
                      URL.revokeObjectURL(url);
                    })
                    .catch((err) => toast.error(err.message));
                }}
                className="flex items-center gap-2 btn-gradient px-6 py-3"
              >
                <Download className="w-4 h-4" /> PDF 다운로드
              </button>
              <button
                onClick={() => router.push("/dashboard")}
                className="flex items-center gap-2 px-6 py-3 rounded-xl border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition"
              >
                <LayoutDashboard className="w-4 h-4" /> 대시보드로
              </button>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
