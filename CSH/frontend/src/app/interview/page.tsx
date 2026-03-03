"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Header from "@/components/common/Header";
import EventToastContainer from "@/components/common/EventToast";
import InterviewReportCharts, { ReportData } from "@/components/report/InterviewReportCharts";
import { sessionApi, interviewApi, ttsApi, interventionApi, resumeApi, webrtcApi } from "@/lib/api";
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
    lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
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
  // 백엔드 /api/session/create 응답의 max_questions 값을 동적으로 수신 (기본값 10 = 폴백)
  const [totalQuestions, setTotalQuestions] = useState(10);
  const [sttText, setSttText] = useState("");
  const [interimText, setInterimText] = useState("");  // STT 중간 결과 (확정 전 실시간 표시용)
  const [manualInput, setManualInput] = useState("");  // STT 실패 시 수동 텍스트 입력 (폴백)
  const [sttAvailable, setSttAvailable] = useState(true); // 전체 STT 사용 가능 여부 (서버 STT 또는 브라우저 STT)
  const [serverSttAvailable, setServerSttAvailable] = useState(false); // 서버(WebSocket/Deepgram) STT 가능 여부
  const [browserSttEnabled, setBrowserSttEnabled] = useState(true); // 브라우저 SpeechRecognition 활성화 여부
  const STT_RUNTIME_DEBUG = process.env.NEXT_PUBLIC_STT_DEBUG === "1";
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
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const interventionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pushEventRef = useRef<((raw: Record<string, unknown>) => void) | null>(null);

  // ── VAD (Voice Activity Detection) 실시간 음성 감지 관련 Ref ──
  // Web Audio API의 AnalyserNode로 마이크 음량(RMS)을 실시간 분석하여
  // 음성 여부를 판단하고, 서버에 VAD 신호를 주기적으로 전송합니다.
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const vadSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const sttProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const sttMuteGainRef = useRef<GainNode | null>(null);
  const sttPendingFallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // WebSocket 재연결 시도 횟수 — connectWebSocket 재귀 호출 시에도 누적되어
  // 무한 재연결 루프를 방지 (이전: 매 호출마다 0으로 초기화되는 지역 변수 사용)
  const wsReconnectAttemptsRef = useRef(0);

  // SpeechRecognition 콜백에서 최신 상태를 참조하기 위한 Ref
  // (클로저 캡처 시 stale value 문제 방지 — 콜백은 최초 생성 시점의 state 값만 보유)
  const interviewStartedRef = useRef(false);
  const micEnabledRef = useRef(true);
  const sessionIdRef = useRef("");
  const serverSttAvailableRef = useRef(false);
  const browserSttEnabledRef = useRef(true);
  const sttSourceModeRef = useRef<"browser" | "server_pending" | "server">("browser");
  const lastServerFinalRef = useRef("");
  const lastBrowserFinalRef = useRef("");

  // ── 스트리밍 TTS용 한국어 음성 캐시 ──
  // voiceschanged 이벤트에서 한국어 음성을 미리 캐싱하여,
  // SSE 토큰 도착 시 비동기 검색 없이 즉시 발화할 수 있도록 합니다.
  const koreanVoiceRef = useRef<SpeechSynthesisVoice | null>(null);

  // state 변경 시 ref도 동기화 — 콜백에서 항상 최신 값 참조 가능
  useEffect(() => { interviewStartedRef.current = interviewStarted; }, [interviewStarted]);
  useEffect(() => { micEnabledRef.current = micEnabled; }, [micEnabled]);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { serverSttAvailableRef.current = serverSttAvailable; }, [serverSttAvailable]);
  useEffect(() => { browserSttEnabledRef.current = browserSttEnabled; }, [browserSttEnabled]);

  // ── Web Speech API 음성 목록 사전 로드 ──
  // Chrome 등 일부 브라우저는 getVoices()가 비동기적으로 로딩되므로,
  // voiceschanged 이벤트를 통해 음성 목록이 준비되었음을 보장합니다.
  // 이를 미리 호출하면 speakQuestion() 시점에 한국어 음성이 즉시 사용 가능합니다.
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    // 초기 호출 — 일부 브라우저는 getVoices()를 한 번 호출해야 로딩을 시작함
    speechSynthesis.getVoices();
    const onVoicesChanged = () => {
      const voices = speechSynthesis.getVoices();
      // 한국어 음성 검색 우선순위: Google ko-KR > ko-KR > ko* 접두사
      const googleKo = voices.find((v) => v.lang === "ko-KR" && v.name.toLowerCase().includes("google"));
      const exactKo = voices.find((v) => v.lang === "ko-KR");
      const partialKo = voices.find((v) => v.lang.toLowerCase().startsWith("ko"));
      const koVoice = googleKo || exactKo || partialKo || null;
      // 스트리밍 TTS에서 즉시 사용할 수 있도록 Ref에 캐싱
      koreanVoiceRef.current = koVoice;
      if (koVoice) {
        console.log(`✅ [TTS] 한국어 음성 캐싱 완료: ${koVoice.name} (${koVoice.lang})`);
      } else {
        console.warn("⚠️ [TTS] 한국어 음성이 설치되지 않았습니다. Windows 설정 > 시간 및 언어 > 음성에서 한국어 음성을 추가하세요.");
      }
    };
    speechSynthesis.addEventListener("voiceschanged", onVoicesChanged);
    return () => speechSynthesis.removeEventListener("voiceschanged", onVoicesChanged);
  }, []);

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

  // 클린업 (카메라, WebSocket, 음성인식, VAD)
  useEffect(() => {
    return () => {
      setActiveSession(false); // 페이지 이탈 시 Auth 유휴 타임아웃 복원
      streamRef.current?.getTracks().forEach(t => t.stop());
      wsRef.current?.close();
      try { pcRef.current?.close(); } catch { /* ignore */ }
      pcRef.current = null;
      recognitionRef.current?.stop();
      if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
      stopVAD(); // VAD 리소스 정리
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setActiveSession]);

  // ========== VAD 실시간 음성 감지 (Web Audio API) ==========
  /**
   * 마이크 스트림에서 Web Audio API의 AnalyserNode를 사용하여
   * 실시간 음량(RMS)을 분석하고, 음성 여부를 판단합니다.
   *
   * 동작 방식:
   *  1. MediaStream → AudioContext → AnalyserNode 연결
   *  2. 500ms 간격으로 주파수 데이터를 읽어 RMS(Root Mean Square) 계산
   *  3. RMS가 임계값(0.015) 이상이면 음성(is_speech=true)으로 판단
   *  4. 결과를 interventionApi.vadSignal()로 서버에 전송
   *  5. 서버의 InterventionManager가 침묵/발화 상태를 추적
   *
   * @param stream - getUserMedia()로 얻은 마이크 포함 MediaStream
   */
  const startVAD = (stream: MediaStream) => {
    try {
      const toPcm16k = (input: Float32Array, srcRate: number): Int16Array => {
        if (input.length === 0) return new Int16Array(0);

        if (srcRate === 16000) {
          const direct = new Int16Array(input.length);
          for (let i = 0; i < input.length; i++) {
            const s = Math.max(-1, Math.min(1, input[i]));
            direct[i] = s < 0 ? s * 32768 : s * 32767;
          }
          return direct;
        }

        const targetLen = Math.max(1, Math.round(input.length * 16000 / srcRate));
        const output = new Int16Array(targetLen);
        const ratio = srcRate / 16000;

        for (let i = 0; i < targetLen; i++) {
          const index = i * ratio;
          const left = Math.floor(index);
          const right = Math.min(left + 1, input.length - 1);
          const frac = index - left;
          const sample = input[left] + (input[right] - input[left]) * frac;
          const clamped = Math.max(-1, Math.min(1, sample));
          output[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
        }

        return output;
      };

      // 이전 VAD가 실행 중이면 먼저 정리
      stopVAD();

      // AudioContext 생성 — 브라우저의 오디오 처리 엔진
      const audioCtx = new AudioContext();
      audioContextRef.current = audioCtx;

      // MediaStream을 AudioContext의 입력 소스로 연결
      const source = audioCtx.createMediaStreamSource(stream);
      vadSourceRef.current = source;

      // AnalyserNode — FFT(Fast Fourier Transform)로 주파수 데이터를 분석
      // fftSize: 2048 → 주파수 해상도 1024개 빈(bin)
      // smoothingTimeConstant: 0.3 → 이전 프레임 대비 30% 스무딩 (노이즈 완화)
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.3;
      analyserRef.current = analyser;

      // 소스 → 분석기 연결 (출력은 연결하지 않아 스피커로 소리가 나지 않음)
      source.connect(analyser);

      // 서버 STT(Deepgram)용 오디오 전송 노드
      // - 입력: 마이크 PCM float32
      // - 처리: 16kHz/PCM16 변환
      // - 전송: WebSocket binary frame
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      const muteGain = audioCtx.createGain();
      muteGain.gain.value = 0;
      sttProcessorRef.current = processor;
      sttMuteGainRef.current = muteGain;

      source.connect(processor);
      processor.connect(muteGain);
      muteGain.connect(audioCtx.destination);

      processor.onaudioprocess = (event: AudioProcessingEvent) => {
        if (!interviewStartedRef.current || !micEnabledRef.current) return;
        if (!serverSttAvailableRef.current) return;

        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        const channelData = event.inputBuffer.getChannelData(0);
        const pcm16 = toPcm16k(channelData, audioCtx.sampleRate);
        if (pcm16.length === 0) return;

        try {
          ws.send(pcm16.buffer);
        } catch {
          // 전송 실패는 치명적 오류가 아니므로 무시 (브라우저 STT 폴백 유지)
        }
      };

      // 주파수 데이터를 저장할 버퍼 (0~255 범위의 바이트 값)
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      // RMS 임계값 — 이 값 이상이면 음성으로 판단
      // 0.015는 일반적인 배경 소음과 발화를 구분하는 실용적 기준값
      // (너무 낮으면 키보드/에어컨 소음에 반응, 너무 높으면 조용한 목소리 감지 실패)
      const SPEECH_THRESHOLD = 0.015;

      // 500ms 간격으로 음량 분석 + 서버 전송
      // 500ms는 실시간성과 네트워크 부하의 균형점
      // (100ms → 너무 빈번한 API 호출, 1000ms → 침묵 감지 지연)
      vadIntervalRef.current = setInterval(() => {
        // AudioContext가 suspended 상태일 수 있음 (브라우저 정책)
        if (audioCtx.state === "suspended") {
          audioCtx.resume().catch(() => { });
          return;
        }

        // 현재 프레임의 시간 도메인 데이터(파형) 읽기
        analyser.getByteTimeDomainData(dataArray);

        // RMS (Root Mean Square) 계산 — 파형의 실효값으로 음량 측정
        // 바이트 값(0~255)을 -1.0~1.0 범위로 정규화한 후 제곱 평균의 제곱근 계산
        let sumSquares = 0;
        for (let i = 0; i < dataArray.length; i++) {
          const normalized = (dataArray[i] - 128) / 128; // 128 = 무음 중심값
          sumSquares += normalized * normalized;
        }
        const rms = Math.sqrt(sumSquares / dataArray.length);

        // 음성 여부 판단
        const isSpeech = rms > SPEECH_THRESHOLD;

        // 서버에 VAD 신호 전송 (면접 진행 중일 때만)
        const sid = sessionIdRef.current;
        if (sid && interviewStartedRef.current) {
          interventionApi.vadSignal(sid, isSpeech, rms).catch(() => {
            // 네트워크 오류 시 무시 — VAD 신호 누락은 치명적이지 않음
          });
        }
      }, 500);

      console.log("🎙️ [VAD] 실시간 음성 감지 시작 (Web Audio API)");
    } catch (err) {
      // Web Audio API 미지원 또는 초기화 실패 시
      // VAD 없이도 면접은 정상 진행 가능 (Graceful Degradation)
      console.warn("[VAD] 초기화 실패 (면접은 계속 진행):", err);
    }
  };

  /**
   * VAD 리소스 정리 — 페이지 이탈, 면접 종료, 마이크 비활성화 시 호출
   * AudioContext, AnalyserNode, 주기적 타이머를 모두 해제합니다.
   */
  const stopVAD = () => {
    if (sttPendingFallbackTimerRef.current) {
      clearTimeout(sttPendingFallbackTimerRef.current);
      sttPendingFallbackTimerRef.current = null;
    }

    if (sttProcessorRef.current) {
      try {
        sttProcessorRef.current.onaudioprocess = null;
        sttProcessorRef.current.disconnect();
      } catch {
        // ignore
      }
      sttProcessorRef.current = null;
    }

    if (sttMuteGainRef.current) {
      try { sttMuteGainRef.current.disconnect(); } catch { /* ignore */ }
      sttMuteGainRef.current = null;
    }

    // 주기적 분석 타이머 해제
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    // AudioContext 소스 연결 해제
    if (vadSourceRef.current) {
      try { vadSourceRef.current.disconnect(); } catch { /* ignore */ }
      vadSourceRef.current = null;
    }
    // AnalyserNode 정리
    if (analyserRef.current) {
      try { analyserRef.current.disconnect(); } catch { /* ignore */ }
      analyserRef.current = null;
    }
    // AudioContext 종료 — GPU/CPU 리소스 해제
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => { });
      audioContextRef.current = null;
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

      // 백엔드에서 전달받은 max_questions로 UI 동기화 (진행 바·종료 판단)
      if (res.max_questions && res.max_questions > 0) {
        setTotalQuestions(res.max_questions);
      }

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

      // ── WebRTC /offer 연결 (오디오/비디오 트랙 서버 파이프라인 연결) ──
      // 기존 WS 바이너리 STT 경로와 병행 가능하나, 아키텍처 정합성 확보를 위해
      // 우선 /offer 경로를 연결하여 서버의 WebRTC 오디오 파이프라인을 활성화합니다.
      if (streamRef.current) {
        try {
          if (pcRef.current) {
            try { pcRef.current.close(); } catch { /* ignore */ }
            pcRef.current = null;
          }

          const pc = new RTCPeerConnection();
          pcRef.current = pc;

          for (const track of streamRef.current.getTracks()) {
            pc.addTrack(track, streamRef.current);
          }

          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);

          const answer = await webrtcApi.offer({
            sdp: offer.sdp || "",
            type: offer.type,
            session_id: sid,
          });

          await pc.setRemoteDescription(new RTCSessionDescription({
            sdp: answer.sdp,
            type: answer.type,
          }));

          // 서버가 동일 세션을 재사용하지 못한 경우를 대비해 동기화
          if (answer.session_id && answer.session_id !== sid) {
            setSessionId(answer.session_id);
            sessionIdRef.current = answer.session_id;
            if (STT_RUNTIME_DEBUG) {
              console.warn(
                `[STT-CHECK][webrtc-session-sync] requested=${sid.slice(0, 8)} actual=${answer.session_id.slice(0, 8)}`,
              );
            }
          }
        } catch (webrtcErr) {
          // WebRTC 실패 시에도 WS 바이너리 + 브라우저 STT 폴백 경로로 계속 진행
          console.warn("[WebRTC] /offer 연결 실패 — WS 경로로 계속 진행:", webrtcErr);
          try { pcRef.current?.close(); } catch { /* ignore */ }
          pcRef.current = null;
        }
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
            // ★ STT 정책: Deepgram Nova-3를 메인 STT로 사용, 브라우저 SpeechRecognition은 폴백
            // 서버가 stt_available=true를 보내면 → Deepgram 서버 STT
            // 서버가 stt_available=false를 보내면 → 브라우저 SpeechRecognition 폴백
            if (data.type === "connected") {
              if (data.stt_available) {
                // ── Deepgram 서버 STT 활성화 ──
                // server_pending 상태로 진입: Deepgram 첫 결과를 대기
                // 5초 내에 서버 STT 결과가 오지 않으면 브라우저 폴백으로 전환
                setServerSttAvailable(true);
                sttSourceModeRef.current = "server_pending";
                setBrowserSttEnabled(true);  // 폴백용으로 브라우저 STT도 준비
                if (STT_RUNTIME_DEBUG) {
                  console.log(
                    `[STT-CHECK][source-select] session=${targetSid.slice(0, 8)} mode=server_pending (Deepgram Nova-3, 브라우저 폴백 대기)`,
                  );
                }
                // 폴백 타이머: 5초 내에 서버 STT 결과가 없으면 브라우저로 전환
                if (sttPendingFallbackTimerRef.current) {
                  clearTimeout(sttPendingFallbackTimerRef.current);
                }
                sttPendingFallbackTimerRef.current = setTimeout(() => {
                  if (sttSourceModeRef.current === "server_pending") {
                    console.warn("[STT-CHECK] server_pending 5초 타임아웃 → 브라우저 폴백");
                    sttSourceModeRef.current = "browser";
                    setBrowserSttEnabled(true);
                  }
                  sttPendingFallbackTimerRef.current = null;
                }, 5000);
                // 브라우저 SpeechRecognition도 폴백용으로 초기화
                if (!recognitionRef.current) {
                  initSpeechRecognition();
                } else {
                  try { recognitionRef.current.start(); } catch { /* 이미 시작됨 */ }
                }
              } else {
                // ── Deepgram 불가 → 브라우저 STT 폴백 즉시 활성화 ──
                setServerSttAvailable(false);
                sttSourceModeRef.current = "browser";
                setBrowserSttEnabled(true);
                if (STT_RUNTIME_DEBUG) {
                  console.log(
                    `[STT-CHECK][source-select] session=${targetSid.slice(0, 8)} mode=browser (Deepgram 불가, 브라우저 폴백)`,
                  );
                }
                if (sttPendingFallbackTimerRef.current) {
                  clearTimeout(sttPendingFallbackTimerRef.current);
                  sttPendingFallbackTimerRef.current = null;
                }
                if (!recognitionRef.current) {
                  initSpeechRecognition();
                } else {
                  try { recognitionRef.current.start(); } catch { /* 이미 시작됨 */ }
                }
              }
              return;
            }
            // ★ 서버 STT 상태 변경 알림 처리
            // Deepgram 연결 해제/복구 시 서버에서 stt_status 메시지 전송
            if (data.type === "stt_status") {
              const available = data.available === true;
              setServerSttAvailable(available);
              if (available && sttSourceModeRef.current === "browser") {
                // 서버 STT 복구됨 → server_pending으로 전환
                sttSourceModeRef.current = "server_pending";
              } else if (!available) {
                // 서버 STT 해제됨 → 브라우저 폴백
                sttSourceModeRef.current = "browser";
                setBrowserSttEnabled(true);
              }
              return;
            }
            // ★ 서버(Deepgram) STT 결과 수신
            // server 또는 server_pending 모드일 때만 sttText에 누적
            if (data.type === "stt_result" && data.is_final) {
              const mode = sttSourceModeRef.current;
              if (mode === "server" || mode === "server_pending") {
                const transcript = (data.transcript || "").trim();
                if (transcript) {
                  // server_pending → server 확정 전환 (첫 결과 수신)
                  if (mode === "server_pending") {
                    sttSourceModeRef.current = "server";
                    if (sttPendingFallbackTimerRef.current) {
                      clearTimeout(sttPendingFallbackTimerRef.current);
                      sttPendingFallbackTimerRef.current = null;
                    }
                    if (STT_RUNTIME_DEBUG) {
                      console.log(`[STT-CHECK] server_pending → server 확정 (Deepgram 첫 결과 수신)`);
                    }
                  }
                  // 중복 방지
                  const normalized = transcript.toLowerCase().replace(/\s+/g, " ");
                  if (normalized !== lastServerFinalRef.current) {
                    lastServerFinalRef.current = normalized;
                    setSttText(prev => prev + " " + transcript);
                    setInterimText("");
                    if (STT_RUNTIME_DEBUG) {
                      console.log(`[STT-CHECK][append][server] text="${transcript.slice(0, 60)}"`);
                    }
                  }
                }
              } else {
                // browser 모드 — 서버 결과 무시
                if (STT_RUNTIME_DEBUG) {
                  console.log(`[STT-CHECK][skip][server] mode=${mode}, 서버 STT 결과 무시`);
                }
              }
              return;
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
          // 서버 경로 단절 시 브라우저 STT 폴백 즉시 복구
          sttSourceModeRef.current = "browser";
          setServerSttAvailable(false);
          if (sttPendingFallbackTimerRef.current) {
            clearTimeout(sttPendingFallbackTimerRef.current);
            sttPendingFallbackTimerRef.current = null;
          }
          setBrowserSttEnabled(true);
          try {
            recognitionRef.current?.start();
          } catch {
            // 이미 시작된 상태일 수 있으므로 무시
          }
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

      setPhase("interview");
      setInterviewStarted(true);
      setActiveSession(true); // 면접 시작 → Auth 유휴 타임아웃 비활성화
      setSessionId(sid);

      // ── VAD 실시간 음성 감지 시작 ──
      // 마이크 스트림이 있으면 Web Audio API로 음량을 분석하여
      // 서버에 실시간 VAD 신호(음성/침묵 여부)를 전송합니다.
      if (streamRef.current) {
        startVAD(streamRef.current);
      }

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
    // 서버 STT가 활성화된 세션에서는 브라우저 STT를 시작하지 않음 (소스 단일화)
    if (!browserSttEnabledRef.current) {
      return;
    }

    const SR = window.webkitSpeechRecognition || window.SpeechRecognition;
    if (!SR) {
      // Web Speech API 미지원 브라우저 — 텍스트 입력 모드로 전환
      console.warn("[SpeechRecognition] Web Speech API를 지원하지 않는 브라우저입니다. 텍스트 입력 모드로 전환합니다.");
      setSttAvailable(serverSttAvailableRef.current);
      return;
    }
    const recognition = new SR();
    recognition.lang = "ko-KR";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;  // ★ 대안 수를 1로 제한 → 처리 속도 향상

    // 연속 에러 카운터 — 일정 횟수 이상 에러 시 STT를 비활성화하고 텍스트 입력으로 전환
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 3;

    // 음성 인식 결과 핸들러 — 최종(final) + 중간(interim) 결과 모두 처리
    // ★ 개선: interim 결과를 실시간 표시하여 사용자가 인식 진행 상황을 즉시 확인 가능
    recognition.onresult = (e: SpeechRecognitionEvent) => {
      // browser 모드에서만 누적 (server_pending/server 모드에서는 누적 금지)
      if (sttSourceModeRef.current !== "browser") {
        return;
      }

      consecutiveErrors = 0; // 정상 결과 수신 시 에러 카운터 리셋
      let final = "";
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          final += transcript;
        } else {
          // ★ interim: 아직 확정되지 않은 중간 인식 결과 (실시간 표시용)
          interim += transcript;
        }
      }
      if (final) {
        const finalTrimmed = final.trim();
        if (STT_RUNTIME_DEBUG && finalTrimmed) {
          const normalized = finalTrimmed.toLowerCase().replace(/\s+/g, " ");
          const isDuplicateCandidate = normalized === lastBrowserFinalRef.current;
          console.log(
            `[STT-CHECK][append][browser] session=${sessionIdRef.current.slice(0, 8)} dup=${isDuplicateCandidate ? "Y" : "N"} text="${finalTrimmed.slice(0, 60)}"`,
          );
          lastBrowserFinalRef.current = normalized;
        }
        // 확정된 텍스트를 sttText에 누적하고, interim 텍스트는 초기화
        setSttText(prev => prev + " " + final);
        setInterimText("");
      } else if (interim) {
        // ★ 아직 확정 전 — 중간 결과를 interimText에 표시 (사용자에게 실시간 피드백)
        setInterimText(interim);
      }
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
        setSttAvailable(serverSttAvailableRef.current);
        return;
      }

      // aborted는 의도적 중단 → 재시작 불필요
      if (errorType === "aborted") return;

      // 기타 에러 — 연속 에러 카운터 증가
      consecutiveErrors++;
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        console.warn(`[SpeechRecognition] 연속 ${MAX_CONSECUTIVE_ERRORS}회 에러 발생. 텍스트 입력 모드로 전환합니다.`);
        setSttAvailable(serverSttAvailableRef.current);
      }
    }) as ((ev: Event) => void);

    // 음성 인식 종료 핸들러 — Ref를 통해 최신 state 참조 (stale closure 방지)
    // Chrome에서 continuous 모드라도 네트워크 타임아웃 등으로 인식이 끊길 수 있음
    recognition.onend = () => {
      // Ref에서 최신 interviewStarted/micEnabled 값을 읽어 재시작 여부 결정
      if (
        interviewStartedRef.current
        && micEnabledRef.current
        && browserSttEnabledRef.current
      ) {
        // ★ 디바운스: 50ms로 축소하여 끊김 시간 최소화 (기존 300ms → 50ms)
        // Chrome의 continuous 모드는 네트워크 타임아웃으로 주기적으로 끊기므로
        // 재시작 간격을 최소화하여 발화 유실을 방지
        setTimeout(() => {
          try {
            recognition.start();
          } catch (e) {
            // 이미 시작된 상태에서 start() 호출 시 DOMException 발생 가능 → 무시
            console.warn("[SpeechRecognition] 재시작 실패 (이미 활성):", e);
          }
        }, 50);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setSttAvailable(true);
    } catch (e) {
      console.warn("[SpeechRecognition] 초기 시작 실패:", e);
      setSttAvailable(serverSttAvailableRef.current);
    }
  };

  // ========== 질문 요청 (SSE 스트리밍 우선, 실패 시 기존 API 폴백) ==========
  const getNextQuestion = async (sid: string, message: string) => {
    setStatus("processing");
    try {
      // ── SSE 스트리밍 방식: 토큰이 도착할 때마다 UI에 실시간 표시 + 동시 TTS 발화 ──
      // ChatGPT처럼 AI 응답이 글자 단위로 나타나며,
      // 문장이 완성될 때마다 즉시 TTS로 읽어줘 체감 대기 시간을 대폭 줄입니다.
      let streamedText = "";  // 스트리밍된 토큰 누적 변수 (UI 표시용)
      let ttsBuffer = "";     // TTS 발화를 위한 문장 버퍼 (문장 경계 감지용)
      let streamingTtsUsed = false;  // 스트리밍 중 TTS가 사용되었는지 추적

      // 스트리밍 시작 전, 빈 AI 메시지 슬롯을 미리 추가 (토큰이 들어올 때마다 업데이트)
      setMessages(prev => [...prev, { role: "ai", text: "" }]);

      // 스트리밍 시작 시 이전 발화를 취소하여 겹침 방지
      if (typeof window !== "undefined" && window.speechSynthesis) {
        speechSynthesis.cancel();
      }

      const res = await interviewApi.chatStream(
        { session_id: sid, message, mode: "interview" },
        // onToken 콜백: 각 토큰이 도착할 때마다 호출
        (token: string) => {
          streamedText += token;
          ttsBuffer += token;

          // messages 배열의 마지막 항목(AI 메시지)을 누적된 텍스트로 업데이트
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "ai", text: streamedText };
            return updated;
          });

          // ── 문장 경계 감지 → 즉시 TTS 발화 ──
          // 마침표(.)·물음표(?)·느낌표(!) 뒤에 공백/줄바꿈이 오면 문장 완성으로 판단
          // 최소 5자 이상일 때만 발화하여 너무 짧은 조각 방지
          const boundaryIdx = findLastSentenceBoundary(ttsBuffer);
          if (boundaryIdx >= 0) {
            const speakText = ttsBuffer.slice(0, boundaryIdx + 1).trim();
            ttsBuffer = ttsBuffer.slice(boundaryIdx + 1).trimStart();
            if (speakText.length >= 5) {
              speakSentenceFragment(speakText);
              streamingTtsUsed = true;
              // 첫 문장 발화 시 status를 speaking으로 변경
              setStatus("speaking");
            }
          }
        },
        // onStatus 콜백: 처리 단계 표시 (선택적)
        (phase: string) => {
          if (phase === "rag_search") setStatus("processing");
          else if (phase === "llm_generating") setStatus("processing");
        },
      );

      // 스트리밍 완료 후: 최종 응답으로 상태 업데이트
      const finalQuestion = res.response || streamedText;
      setCurrentQuestion(finalQuestion);
      setQuestionNum(res.question_number || questionNum + 1);
      // 최종 텍스트로 마지막 메시지 확정 (strip_think_tokens 처리된 결과)
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "ai", text: finalQuestion };
        return updated;
      });

      // ── 스트리밍 TTS 마무리 ──
      if (streamingTtsUsed) {
        // 잔여 버퍼에 아직 발화되지 않은 텍스트가 있으면 마지막으로 발화
        if (ttsBuffer.trim()) {
          speakSentenceFragment(ttsBuffer.trim());
        }
        // 모든 문장 발화가 완료될 때까지 대기
        await waitForSpeechEnd();
      } else {
        // 스트리밍 중 문장 경계가 감지되지 않은 경우 (매우 짧은 응답 등)
        // → 전체 텍스트를 한 번에 발화 (기존 방식 폴백)
        await speakQuestion(finalQuestion);
      }
      setStatus("listening");

      // 개입 체크 시작
      startInterventionCheck(sid);
    } catch (streamErr) {
      // ── 폴백: 스트리밍 실패 시 기존 비스트리밍 API 사용 ──
      console.warn("스트리밍 실패, 기존 API로 폴백:", streamErr);
      try {
        // 스트리밍 실패 시 추가된 빈 메시지 제거
        setMessages(prev => {
          if (prev.length > 0 && prev[prev.length - 1].role === "ai" && prev[prev.length - 1].text === "") {
            return prev.slice(0, -1);
          }
          return prev;
        });
        const res = await interviewApi.chat({ session_id: sid, message, mode: "interview" });
        const q = res.response;
        setCurrentQuestion(q);
        setQuestionNum(res.question_number || questionNum + 1);
        setMessages(prev => [...prev, { role: "ai", text: q }]);
        await speakQuestion(q);
        setStatus("listening");
        startInterventionCheck(sid);
      } catch (fallbackErr) {
        console.error("다음 질문 요청 실패:", fallbackErr);
        setMessages(prev => {
          // 빈 메시지가 남아있으면 오류 메시지로 교체
          const updated = [...prev];
          if (updated.length > 0 && updated[updated.length - 1].role === "ai" && !updated[updated.length - 1].text) {
            updated[updated.length - 1] = { role: "ai", text: "⚠️ 일시적 오류가 발생했습니다. 잠시 후 다시 답변해 주세요." };
          } else {
            updated.push({ role: "ai", text: "⚠️ 일시적 오류가 발생했습니다. 잠시 후 다시 답변해 주세요." });
          }
          return updated;
        });
        setStatus("listening");
      }
    }
  };

  // ========== TTS 발화 ==========
  /**
   * 한국어 음성(voice)을 찾아 반환하는 헬퍼 함수.
   *
   * Web Speech API의 speechSynthesis.getVoices()는 브라우저마다
   * 비동기 로딩 타이밍이 다르므로, 최대 3회(300ms 간격)까지 재시도합니다.
   *
   * 우선순위:
   *  1) lang이 "ko-KR"인 음성 중 이름에 "Google"이 포함된 것 (가장 자연스러움)
   *  2) lang이 "ko-KR"인 음성 아무거나
   *  3) lang이 "ko"로 시작하는 음성 아무거나 (ko, ko-KR, ko_KR 등)
   *  4) 없으면 null 반환 → 기본 음성 사용 (영어일 수 있음)
   */
  const findKoreanVoice = async (): Promise<SpeechSynthesisVoice | null> => {
    for (let attempt = 0; attempt < 3; attempt++) {
      const voices = speechSynthesis.getVoices();
      if (voices.length > 0) {
        // 1순위: lang === "ko-KR" && 이름에 "Google" 포함 (고품질 음성)
        const googleKo = voices.find(
          (v) => v.lang === "ko-KR" && v.name.toLowerCase().includes("google")
        );
        if (googleKo) return googleKo;

        // 2순위: lang === "ko-KR"
        const exactKo = voices.find((v) => v.lang === "ko-KR");
        if (exactKo) return exactKo;

        // 3순위: lang이 "ko"로 시작 (ko, ko_KR 등 변형 대응)
        const partialKo = voices.find((v) => v.lang.toLowerCase().startsWith("ko"));
        if (partialKo) return partialKo;

        // 음성 목록이 로드됐지만 한국어가 없는 경우 — 더 기다려도 소용없음
        return null;
      }
      // 음성 목록이 아직 비어 있으면 로딩 대기 후 재시도
      await new Promise((r) => setTimeout(r, 300));
    }
    return null;
  };

  // ========== 스트리밍 TTS 헬퍼 함수 ==========
  /**
   * 문장 버퍼에서 완성된 문장의 경계(마침표/물음표/느낌표 + 공백·줄바꿈)를 찾습니다.
   * 여러 문장이 있으면 마지막 경계 위치를 반환하여 한 번에 더 많이 발화합니다.
   *
   * @param text - 토큰이 누적된 TTS 버퍼 문자열
   * @returns 마지막 문장 경계의 인덱스 (구두점 위치), 없으면 -1
   */
  const findLastSentenceBoundary = (text: string): number => {
    let lastIdx = -1;
    for (let i = 0; i < text.length - 1; i++) {
      // 마침표·물음표·느낌표 뒤에 공백 또는 줄바꿈이 오면 문장 경계로 판단
      if ((text[i] === '.' || text[i] === '?' || text[i] === '!') &&
        (text[i + 1] === ' ' || text[i + 1] === '\n')) {
        lastIdx = i;
      }
    }
    return lastIdx;
  };

  /**
   * 스트리밍 전용 문장 단위 TTS 발화 (Web Speech API)
   *
   * speechSynthesis.speak()는 자체 큐를 가지고 있어,
   * 여러 번 호출하면 이전 발화 완료 후 자동으로 다음 발화가 시작됩니다.
   * 따라서 문장이 감지될 때마다 바로 호출해도 안전합니다.
   *
   * @param text - 발화할 문장 텍스트
   */
  const speakSentenceFragment = (text: string) => {
    if (!text.trim() || typeof window === "undefined" || !window.speechSynthesis) return;
    try {
      const utterance = new SpeechSynthesisUtterance(text.trim());
      utterance.lang = "ko-KR";
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      // 캐싱된 한국어 음성 사용 (voiceschanged에서 미리 설정됨)
      if (koreanVoiceRef.current) {
        utterance.voice = koreanVoiceRef.current;
      }
      speechSynthesis.speak(utterance);
    } catch {
      // Web Speech API 미지원 환경 — 무시
    }
  };

  /**
   * speechSynthesis 큐의 모든 발화(진행 중 + 대기 중)가 완료될 때까지 대기합니다.
   * 100ms 간격으로 폴링하며, 최대 60초 타임아웃으로 무한 대기를 방지합니다.
   *
   * @returns 모든 발화 완료 시 resolve되는 Promise
   */
  const waitForSpeechEnd = (): Promise<void> => {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const MAX_WAIT_MS = 60000; // 최대 60초 대기
      const check = () => {
        // 발화 중이 아니고 대기 큐도 비어있으면 완료
        if (!speechSynthesis.speaking && !speechSynthesis.pending) {
          resolve();
        } else if (Date.now() - startTime > MAX_WAIT_MS) {
          // 타임아웃 — 무한 대기 방지
          speechSynthesis.cancel();
          resolve();
        } else {
          setTimeout(check, 100);
        }
      };
      // 첫 체크 전 약간의 지연 — speak() 직후 호출 시 큐 등록 전일 수 있음
      setTimeout(check, 150);
    });
  };

  const speakQuestion = async (text: string) => {
    setStatus("speaking");

    // ── 1단계: 서버 TTS (Hume AI) 시도 ──
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
        // 서버 TTS 실패 → 이번 세션 동안 비활성화하고 Web Speech API로 폴백
        setServerTtsEnabled(false);
      }
    }

    // ── 2단계: Web Speech API 폴백 (한국어 음성 명시 선택) ──
    // 브라우저 기본 음성이 영어일 수 있으므로 반드시 한국어 voice 객체를 지정
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ko-KR";
      utterance.rate = 1.0;   // 말하기 속도 (1.0 = 정상)
      utterance.pitch = 1.0;  // 음높이 (1.0 = 정상)

      // 한국어 음성 검색 — 없으면 lang 힌트에만 의존 (최선의 폴백)
      const koreanVoice = await findKoreanVoice();
      if (koreanVoice) {
        utterance.voice = koreanVoice;
        console.log(`🗣️ [TTS Fallback] 한국어 음성 선택: ${koreanVoice.name} (${koreanVoice.lang})`);
      } else {
        console.warn("⚠️ [TTS Fallback] 한국어 음성을 찾지 못함 — 브라우저 기본 음성 사용");
      }

      // 발화 완료까지 대기 (발화 중 status="speaking" 유지)
      await new Promise<void>((resolve) => {
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        speechSynthesis.speak(utterance);
      });
    } catch {
      // Web Speech API 자체가 지원되지 않는 환경 — 무음 처리
      console.warn("⚠️ [TTS] Web Speech API 사용 불가");
    }
  };

  // ========== 개입 체크 ==========
  // 백엔드의 중복 방지 플래그 + 쿨다운이 주된 방어선이며,
  // 프론트엔드에서도 개입 발생 시 10초간 폴링을 일시정지하여 이중 방어합니다.
  const startInterventionCheck = (sid: string) => {
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    interventionApi.startTurn(sid, currentQuestion).catch(() => { });
    // 마지막으로 표시한 개입 메시지를 추적하여 동일 메시지 중복 표시 방지
    let lastInterventionMsg = "";
    interventionTimerRef.current = setInterval(async () => {
      try {
        const res = await interventionApi.check(sid, sttText);
        const interventionMessage = res.intervention?.message;
        if (res.needs_intervention && interventionMessage) {
          // 동일 메시지 연속 표시 방지 (백엔드 쿨다운 보완)
          if (interventionMessage === lastInterventionMsg) return;
          lastInterventionMsg = interventionMessage;

          setMessages(prev => [...prev, { role: "ai", text: `💡 ${interventionMessage}` }]);
          await speakQuestion(interventionMessage);

          // 개입 메시지 발화 후 10초간 폴링 일시정지 (사용자 응답 대기)
          if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
          setTimeout(() => {
            // 10초 후 폴링 재개 (타이머가 이미 정리되지 않은 경우에만)
            startInterventionCheck(sid);
          }, 10000);

          // 개입 메시지 발화 후에는 다시 사용자 응답 대기 상태로 복귀
          setStatus("listening");
          return; // setTimeout으로 재개할 것이므로 여기서 종료
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
    setInterimText("");  // interim 텍스트도 초기화
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
    sttSourceModeRef.current = "browser";
    if (sttPendingFallbackTimerRef.current) {
      clearTimeout(sttPendingFallbackTimerRef.current);
      sttPendingFallbackTimerRef.current = null;
    }
    const closingMessage = "답변 감사합니다. 오늘 면접을 마치겠습니다. 수고하셨습니다.";
    setMessages(prev => [...prev, { role: "ai", text: closingMessage }]);
    try {
      await speakQuestion(closingMessage);
    } catch { /* ignore */ }

    setInterviewStarted(false);
    setActiveSession(false); // 면접 종료 → Auth 유휴 타임아웃 재활성화
    try { pcRef.current?.close(); } catch { /* ignore */ }
    pcRef.current = null;
    recognitionRef.current?.stop();
    if (interventionTimerRef.current) clearInterval(interventionTimerRef.current);
    stopVAD(); // VAD 리소스 정리

    setPhase("coding");
  };

  // ========== 마이크/카메라 토글 ==========
  const toggleMic = () => {
    const track = streamRef.current?.getAudioTracks()[0];
    if (track) {
      track.enabled = !track.enabled;
      setMicEnabled(track.enabled);
      // 마이크 비활성화 시 VAD도 일시 중지, 활성화 시 재시작
      // → 마이크가 꺼진 상태에서 무음 신호를 계속 보내면
      //   서버가 "침묵 감지" 개입을 잘못 발동할 수 있으므로 VAD를 중지합니다.
      if (track.enabled && streamRef.current) {
        startVAD(streamRef.current);
      } else {
        stopVAD();
      }
    }
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
                      <p className="text-sm">
                        {/* 확정된 STT 텍스트 */}
                        {sttText || (!interimText && "말씀해주세요...")}
                        {/* ★ 중간 인식 결과를 회색 이탤릭으로 실시간 표시 */}
                        {interimText && (
                          <span className="text-gray-400 italic ml-1">{interimText}</span>
                        )}
                      </p>
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
