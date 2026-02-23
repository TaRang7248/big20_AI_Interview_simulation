"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Header from "@/components/common/Header";
import EventToastContainer from "@/components/common/EventToast";
import InterviewReportCharts, { ReportData } from "@/components/report/InterviewReportCharts";
import { sessionApi, interviewApi, ttsApi, interventionApi, resumeApi } from "@/lib/api";
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
  interface SpeechRecognitionResultList { readonly length: number; item(index: number): SpeechRecognitionResult;[index: number]: SpeechRecognitionResult; }
  interface SpeechRecognitionResult { readonly length: number; readonly isFinal: boolean; item(index: number): SpeechRecognitionAlternative;[index: number]: SpeechRecognitionAlternative; }
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
  const { user, token, loading, setActiveSession } = useAuth();
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
  const totalQuestions = 5;
  const [sttText, setSttText] = useState("");
  const [manualInput, setManualInput] = useState("");  // STT 실패 시 수동 텍스트 입력 (폴백)
  const [sttAvailable, setSttAvailable] = useState(true); // Web Speech API 사용 가능 여부
  const [micEnabled, setMicEnabled] = useState(true);
  const [camEnabled, setCamEnabled] = useState(true);
  const [interviewStarted, setInterviewStarted] = useState(false);
  const [serverTtsEnabled, setServerTtsEnabled] = useState(true);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  // 이력서 미업로드 경고 모달 상태 (UX 개선)
  const [showResumeWarning, setShowResumeWarning] = useState(false);
  const [resumeWarningMsg, setResumeWarningMsg] = useState("");
  const [pendingSessionId, setPendingSessionId] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resumeUploading, setResumeUploading] = useState(false);

  // Refs
  const interviewVideoRef = useRef<HTMLVideoElement>(null);  // interview 화면 사용자 영상용
  const streamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const interventionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pushEventRef = useRef<((raw: Record<string, unknown>) => void) | null>(null);

  // WebSocket 재연결 시도 횟수 — connectWebSocket 재귀 호출 시에도 누적되어
  // 무한 재연결 루프를 방지 (이전: 매 호출마다 0으로 초기화되는 지역 변수 사용)
  const wsReconnectAttemptsRef = useRef(0);

  // SpeechRecognition 콜백에서 최신 상태를 참조하기 위한 Ref
  // (클로저 캡처 시 stale value 문제 방지 — 콜백은 최초 생성 시점의 state 값만 보유)
  const interviewStartedRef = useRef(false);
  const micEnabledRef = useRef(true);
  const sessionIdRef = useRef("");

  // state 변경 시 ref도 동기화 — 콜백에서 항상 최신 값 참조 가능
  useEffect(() => { interviewStartedRef.current = interviewStarted; }, [interviewStarted]);
  useEffect(() => { micEnabledRef.current = micEnabled; }, [micEnabled]);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);

  // 인증 확인 — loading 완료 후에만 리다이렉트 (sessionStorage 복원 대기)
  // 면접 진행 중(interviewStartedRef)에는 토큰 만료로 인한 리다이렉트 방지
  // → AuthContext의 유휴 타임아웃으로 token이 null이 되어도 면접 화면 유지
  useEffect(() => {
    if (!loading && !token && !interviewStartedRef.current) router.push("/");
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

  // ── 페이지 진입 시 자동으로 면접 시작 (setup 화면 스킵) ──
  // 사용자 인증 완료 후 바로 startInterview()를 호출하여 면접을 시작
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (phase !== "setup" || !user || autoStartedRef.current) return;
    autoStartedRef.current = true;
    startInterview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // 면접 중 우발적 페이지 이탈 방지 (뒤로가기, 새로고침 등)
  // beforeunload 이벤트로 사용자에게 확인 대화상자를 표시
  useEffect(() => {
    if (!interviewStarted) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // 최신 브라우저에서는 returnValue 설정만으로 확인 대화상자 표시
      e.returnValue = "면접이 진행 중입니다. 페이지를 떠나시겠습니까?";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [interviewStarted]);

  // 클린업 (카메라, WebSocket, 음성인식)
  useEffect(() => {
    return () => {
      setActiveSession(false); // 페이지 이탈 시 Auth 유휴 타임아웃 복원
      streamRef.current?.getTracks().forEach(t => t.stop());
      wsRef.current?.close();
      recognitionRef.current?.stop();
      if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setActiveSession]);

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

      // WebSocket 연결 + 자동 재연결 로직
      // 백엔드(uvicorn --reload) 재시작 시 WebSocket 끊김이 발생할 수 있으므로
      // onclose/onerror 핸들러에서 자동 재연결을 시도하여 세션 안정성 보장
      const connectWebSocket = (targetSid: string) => {
        // Next.js rewrites는 WebSocket 프로토콜을 프록시하지 못하므로,
        // WebSocket은 FastAPI 백엔드에 직접 연결해야 합니다.
        // NEXT_PUBLIC_WS_URL 환경변수가 있으면 사용, 없으면 FastAPI 기본 포트(8000)로 연결
        const wsBaseUrl = process.env.NEXT_PUBLIC_WS_URL || null;
        const wsToken = sessionStorage.getItem("access_token");
        let wsUrl: string;
        if (wsBaseUrl) {
          // 환경변수에 지정된 WebSocket URL 사용 (예: ws://localhost:8000)
          wsUrl = `${wsBaseUrl}/ws/interview/${targetSid}?token=${encodeURIComponent(wsToken || "")}`;
        } else {
          // 기본값: 현재 호스트의 포트를 8000으로 교체하여 FastAPI 직접 연결
          const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
          const host = window.location.hostname;
          wsUrl = `${protocol}//${host}:8000/ws/interview/${targetSid}?token=${encodeURIComponent(wsToken || "")}`;
        }
        const ws = new WebSocket(wsUrl);

        // WebSocket 연결 성공 시 재연결 카운터 리셋
        // — 이전 끊김에서 정상 복구된 것이므로 카운터를 초기화
        ws.onopen = () => {
          wsReconnectAttemptsRef.current = 0;
        };

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

        // WebSocket 끊김 시 자동 재연결 (최대 5회, 지수 백오프)
        // wsReconnectAttemptsRef를 사용하여 connectWebSocket 재귀 호출 시에도
        // 카운터가 누적됨 → 무한 재연결 루프 방지
        const MAX_RECONNECT = 5;
        ws.onclose = (ev) => {
          // 정상 종료(코드 1000)이거나 면접 종료 상태면 재연결하지 않음
          if (ev.code === 1000 || !interviewStartedRef.current) return;
          console.warn(`[WebSocket] 연결 끊김 (code: ${ev.code}). 재연결 시도 ${wsReconnectAttemptsRef.current + 1}/${MAX_RECONNECT}`);
          if (wsReconnectAttemptsRef.current < MAX_RECONNECT) {
            wsReconnectAttemptsRef.current++;
            // 지수 백오프: 재시도 간격을 점진적으로 증가 (3초 → 6초 → 12초 → ...)
            const delay = 3000 * Math.pow(2, wsReconnectAttemptsRef.current - 1);
            setTimeout(() => {
              if (interviewStartedRef.current) {
                const newWs = connectWebSocket(targetSid);
                wsRef.current = newWs;
              }
            }, Math.min(delay, 30000)); // 최대 30초 대기
          } else {
            console.error("[WebSocket] 최대 재연결 횟수 초과. 수동 새로고침이 필요합니다.");
          }
        };

        ws.onerror = () => {
          console.warn("[WebSocket] 연결 오류 발생");
          // onclose가 자동으로 호출되므로 여기서는 로그만 출력
        };

        return ws;
      };

      const ws = connectWebSocket(sid);
      wsRef.current = ws;

      initSpeechRecognition();
      setPhase("interview");
      setInterviewStarted(true);
      setActiveSession(true); // 면접 시작 → Auth 유휴 타임아웃 비활성화
      setSessionId(sid);

      // [START] 요청: 첫 인사말 가져오기
      // 만약 API 실패 시에도 기본 인사말을 표시하여 사용자가 빈 화면을 보지 않도록 함
      try {
        await getNextQuestion(sid, "[START]");
      } catch (err) {
        console.error("첫 질문 요청 실패, 기본 인사말 표시:", err);
        const fallbackGreeting = "안녕하세요. 오늘 면접을 진행하게 된 면접관입니다. 먼저 간단한 자기소개를 부탁드립니다.";
        setCurrentQuestion(fallbackGreeting);
        setQuestionNum(1);
        setMessages(prev => [...prev, { role: "ai", text: fallbackGreeting }]);
        setStatus("listening");
      }
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
    if (!SR) {
      // Web Speech API 미지원 브라우저 — 텍스트 입력 모드로 전환
      console.warn("[SpeechRecognition] Web Speech API를 지원하지 않는 브라우저입니다. 텍스트 입력 모드로 전환합니다.");
      setSttAvailable(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = "ko-KR";
    recognition.continuous = true;
    recognition.interimResults = true;

    // 연속 에러 카운터 — 일정 횟수 이상 에러 시 STT를 비활성화하고 텍스트 입력으로 전환
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 3;

    // 음성 인식 결과 핸들러 — 최종(final) 결과만 STT 텍스트에 추가
    recognition.onresult = (e: SpeechRecognitionEvent) => {
      consecutiveErrors = 0; // 정상 결과 수신 시 에러 카운터 리셋
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
      }
      if (final) setSttText(prev => prev + " " + final);
    };

    // 음성 인식 에러 핸들러 — 에러 발생 시에도 시스템이 안정적으로 유지되도록 처리
    // 에러 유형: network(네트워크), not-allowed(권한), aborted(중단), no-speech(무음) 등
    recognition.onerror = ((ev: Event) => {
      const error = ev as Event & { error?: string };
      const errorType = error.error || "unknown";
      // no-speech는 정상 동작 (사용자가 말하지 않은 경우) → 무시
      if (errorType === "no-speech") return;
      console.warn(`[SpeechRecognition] 에러: ${errorType}`);

      // not-allowed(권한 거부) 또는 network(네트워크 불가) → 즉시 텍스트 모드 전환
      if (errorType === "not-allowed" || errorType === "service-not-allowed") {
        console.warn("[SpeechRecognition] 마이크 권한이 거부되었습니다. 텍스트 입력 모드로 전환합니다.");
        setSttAvailable(false);
        return;
      }

      // aborted는 의도적 중단 → 재시작 불필요
      if (errorType === "aborted") return;

      // 기타 에러 — 연속 에러 카운터 증가
      consecutiveErrors++;
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        console.warn(`[SpeechRecognition] 연속 ${MAX_CONSECUTIVE_ERRORS}회 에러 발생. 텍스트 입력 모드로 전환합니다.`);
        setSttAvailable(false);
      }
    }) as ((ev: Event) => void);

    // 음성 인식 종료 핸들러 — Ref를 통해 최신 state 참조 (stale closure 방지)
    // Chrome에서 continuous 모드라도 네트워크 타임아웃 등으로 인식이 끊길 수 있음
    recognition.onend = () => {
      // Ref에서 최신 interviewStarted/micEnabled 값을 읽어 재시작 여부 결정
      if (interviewStartedRef.current && micEnabledRef.current) {
        // 디바운스: 빠른 재시작 루프 방지 (300ms 대기 후 재시작)
        setTimeout(() => {
          try {
            recognition.start();
          } catch (e) {
            // 이미 시작된 상태에서 start() 호출 시 DOMException 발생 가능 → 무시
            console.warn("[SpeechRecognition] 재시작 실패 (이미 활성):", e);
          }
        }, 300);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (e) {
      console.warn("[SpeechRecognition] 초기 시작 실패:", e);
      setSttAvailable(false);
    }
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
    } catch (err) {
      // 에러 발생 시에도 "listening" 상태로 복귀 → 사용자가 재시도 가능
      console.error("다음 질문 요청 실패:", err);
      setMessages(prev => [...prev, { role: "ai", text: "⚠️ 일시적 오류가 발생했습니다. 잠시 후 다시 답변해 주세요." }]);
      setStatus("listening");
    }
  };

  // ========== TTS 발화 ==========
  const speakQuestion = async (text: string) => {
    setStatus("speaking");

    if (serverTtsEnabled) {
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
        return;
      } catch {
        setServerTtsEnabled(false);
      }
    }

    // 서버 TTS 비활성/실패 시 Web Speech API 폴백
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ko-KR";
      speechSynthesis.speak(utterance);
    } catch { /* ignore */ }
  };

  // ========== 개입 체크 ==========
  const startInterventionCheck = (sid: string) => {
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    interventionApi.startTurn(sid, currentQuestion).catch(() => { });
    interventionTimerRef.current = setInterval(async () => {
      try {
        const res = await interventionApi.check(sid, sttText);
        const interventionMessage = res.intervention?.message;
        if (res.needs_intervention && interventionMessage) {
          setMessages(prev => [...prev, { role: "ai", text: `💡 ${interventionMessage}` }]);
          await speakQuestion(interventionMessage);
        }
      } catch { /* ignore */ }
    }, 3000);
  };

  // ========== 답변 제출 ==========
  const submitAnswer = async () => {
    // STT 텍스트 또는 수동 입력 중 하나를 사용 (STT 우선, 없으면 수동 입력)
    const answer = (sttText.trim() || manualInput.trim());
    if (!answer) return;
    setSttText("");
    setManualInput("");  // 수동 입력도 초기화
    setMessages(prev => [...prev, { role: "user", text: answer }]);

    // 개입 타이머 정지
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    interventionApi.endTurn(sessionId, answer).catch(() => { });

    // ⚡ 평가는 /api/chat 내부 워크플로우에서 자동 처리됨 (Celery 오프로드 또는 직접 평가)
    // 별도 /api/evaluate 호출 제거 — 동일 Ollama GPU 리소스 경합으로 질문 생성 지연 방지
    // (이전: interviewApi.evaluate() fire-and-forget → Ollama 큐 점유 → chat 응답 지연)
    setStatus("processing");

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
    setActiveSession(false); // 면접 종료 → Auth 유휴 타임아웃 재활성화
    recognitionRef.current?.stop();
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);

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

      {/* 면접 준비 중 로딩 화면 (자동 시작) */}
      {phase === "setup" && (
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="glass-card max-w-lg w-full text-center">
            <h1 className="text-3xl font-bold gradient-text mb-4">AI 모의면접</h1>
            <div className="flex flex-col items-center gap-4 py-8">
              <Loader2 size={48} className="text-[var(--cyan)] animate-spin" />
              <p className="text-[var(--text-secondary)]">
                면접을 준비하고 있습니다...<br />
                카메라와 마이크 권한을 허용해주세요.
              </p>
            </div>
          </div>
        </main>
      )}

      {/* 면접 진행 화면 */}
      {phase === "interview" && (
        <main className="flex-1 flex flex-col p-4 max-w-[1400px] mx-auto w-full">
          {/* 상태 바 */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className={`px-4 py-1.5 rounded-full text-sm font-semibold ${status === "ready" ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]" :
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
              <div key={i} className={`h-1.5 flex-1 rounded-full transition-all ${i < questionNum ? "bg-gradient-to-r from-[var(--cyan)] to-[var(--green)]" :
                i === questionNum ? "bg-[var(--cyan)] animate-pulse" : "bg-[rgba(255,255,255,0.1)]"
                }`} />
            ))}
          </div>

          {/* 2열 레이아웃: 사용자 영상 + 대화창 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1">
            {/* ══ 왼쪽: 사용자 카메라 영상 (크게) ══ */}
            <div className="glass-card flex flex-col">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Camera size={16} className="text-[var(--cyan)]" /> 내 화면
              </h3>
              <div className="flex-1 rounded-xl overflow-hidden bg-black relative min-h-[300px]">
                {/* 사용자 웹캠 비디오 — 영역 전체를 채움 */}
                <video ref={interviewVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
                {/* 카메라 OFF 오버레이 */}
                {!camEnabled && (
                  <div className="absolute inset-0 bg-black/80 flex items-center justify-center">
                    <CameraOff size={48} className="text-[var(--text-secondary)]" />
                  </div>
                )}
                {/* 좌하단: 카메라 상태 뱃지 */}
                <span className="absolute bottom-3 left-3 text-xs bg-black/60 px-2 py-1 rounded text-white">
                  {camEnabled ? "📷 카메라 ON" : "카메라 OFF"}
                </span>
                {/* 우하단: AI 상태 뱃지 — 면접관이 말하거나 처리 중일 때 표시 */}
                <span className={`absolute bottom-3 right-3 text-xs px-2 py-1 rounded font-medium ${status === "speaking" ? "bg-[rgba(0,255,136,0.25)] text-[var(--green)]"
                  : status === "processing" ? "bg-[rgba(156,39,176,0.25)] text-purple-300"
                    : status === "listening" ? "bg-[rgba(255,193,7,0.25)] text-[var(--warning)]"
                      : "bg-black/60 text-white"
                  }`}>
                  {status === "speaking" ? "🔊 AI 답변 중..."
                    : status === "processing" ? "⏳ AI 생각 중..."
                      : status === "listening" ? "🎤 듣는 중..."
                        : "대기"}
                </span>
              </div>

              {/* 하단 컨트롤 버튼 */}
              <div className="flex items-center justify-center gap-4 mt-4">
                <button onClick={toggleMic} title={micEnabled ? "마이크 끄기" : "마이크 켜기"} className={`w-12 h-12 rounded-full flex items-center justify-center transition ${micEnabled ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]" : "bg-[rgba(255,82,82,0.2)] text-[var(--danger)]"
                  }`}>
                  {micEnabled ? <Mic size={20} /> : <MicOff size={20} />}
                </button>
                <button onClick={toggleCam} title={camEnabled ? "카메라 끄기" : "카메라 켜기"} className={`w-12 h-12 rounded-full flex items-center justify-center transition ${camEnabled ? "bg-[rgba(0,255,136,0.2)] text-[var(--green)]" : "bg-[rgba(255,82,82,0.2)] text-[var(--danger)]"
                  }`}>
                  {camEnabled ? <Camera size={20} /> : <CameraOff size={20} />}
                </button>
                <button onClick={submitAnswer} disabled={(!sttText.trim() && !manualInput.trim()) || status !== "listening"} title="답변 제출"
                  className="btn-gradient !rounded-full w-12 h-12 flex items-center justify-center disabled:opacity-40">
                  <SkipForward size={20} />
                </button>
                <button onClick={endInterview} title="면접 종료" className="w-12 h-12 rounded-full bg-[rgba(244,67,54,0.8)] text-white flex items-center justify-center hover:bg-[rgba(244,67,54,1)] transition">
                  <PhoneOff size={20} />
                </button>
              </div>
            </div>

            {/* ══ 오른쪽: 대화창 ══ */}
            <div className="glass-card flex flex-col">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Volume2 size={16} className="text-[var(--cyan)]" /> AI 면접관 대화
              </h3>

              {/* 채팅 로그 */}
              <div className="flex-1 overflow-y-auto space-y-3 mb-3 min-h-[300px] max-h-[520px] pr-2">
                {messages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${m.role === "user"
                      ? "bg-gradient-to-r from-[rgba(0,217,255,0.15)] to-[rgba(0,255,136,0.1)] rounded-br-md"
                      : "bg-[rgba(255,255,255,0.06)] rounded-bl-md"
                      }`}>
                      {m.text}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              {/* STT 인식 텍스트 + 수동 텍스트 입력 폴백 */}
              {status === "listening" && (
                <div className="space-y-2">
                  {/* STT 활성 시: 실시간 음성 인식 결과 표시 */}
                  {sttAvailable && (
                    <div className="bg-[rgba(255,193,7,0.08)] border border-[rgba(255,193,7,0.2)] rounded-xl p-3">
                      <p className="text-xs text-[var(--warning)] mb-1">🎤 음성 인식 중...</p>
                      <p className="text-sm">{sttText || "말씀해주세요..."}</p>
                    </div>
                  )}
                  {/* STT 비활성 시: 안내 메시지 */}
                  {!sttAvailable && (
                    <div className="bg-[rgba(244,67,54,0.08)] border border-[rgba(244,67,54,0.2)] rounded-xl p-3">
                      <p className="text-xs text-[var(--danger)] mb-1">⚠️ 음성 인식을 사용할 수 없습니다</p>
                      <p className="text-xs text-[var(--text-secondary)]">아래 입력창에 답변을 직접 입력해주세요.</p>
                    </div>
                  )}
                  {/* 수동 텍스트 입력 (항상 표시 — STT 보완/대체) */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={manualInput}
                      onChange={(e) => setManualInput(e.target.value)}
                      onKeyDown={(e) => {
                        // Enter 키로 답변 제출 (Shift+Enter는 무시)
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          submitAnswer();
                        }
                      }}
                      placeholder={sttAvailable ? "텍스트로도 입력할 수 있습니다..." : "답변을 입력하세요..."}
                      className="flex-1 bg-[rgba(255,255,255,0.06)] border border-[rgba(255,255,255,0.15)] rounded-xl px-4 py-2.5 text-sm placeholder:text-[var(--text-secondary)] focus:outline-none focus:border-[var(--cyan)] transition"
                    />
                    <button
                      onClick={submitAnswer}
                      disabled={!sttText.trim() && !manualInput.trim()}
                      className="btn-gradient px-4 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-40 whitespace-nowrap"
                    >
                      제출
                    </button>
                  </div>
                </div>
              )}
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
                  const tk = sessionStorage.getItem("access_token");
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
