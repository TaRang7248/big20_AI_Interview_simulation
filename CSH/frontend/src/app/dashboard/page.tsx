"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Header from "@/components/common/Header";
import { resumeApi, interviewApi, type InterviewRecord } from "@/lib/api";
import InterviewReportCharts, { ReportData } from "@/components/report/InterviewReportCharts";
import { Upload, Trash2, Video, Mic, CheckCircle2, AlertCircle, FileText, Clock, AlertTriangle, Briefcase, X, Loader2, Download, MicOff, VideoOff, Volume2, RefreshCw, Info } from "lucide-react";
import { useToast } from "@/contexts/ToastContext";

// ========== 환경 테스트 상태 타입 ==========
// idle: 미시작, testing: 테스트 중, ok: 정상, warning: 주의, error: 오류
type DeviceStatus = "idle" | "testing" | "ok" | "warning" | "error";

// 에러 타입별 사용자 친화적 메시지 + 해결 가이드
function getDeviceErrorInfo(err: unknown): { title: string; guide: string } {
  const error = err as DOMException;
  switch (error?.name) {
    case "NotAllowedError":
      return {
        title: "카메라/마이크 접근 권한이 거부되었습니다",
        guide: "브라우저 주소창 왼쪽의 🔒 아이콘을 클릭하여 카메라·마이크 권한을 '허용'으로 변경한 후 새로고침해주세요.",
      };
    case "NotFoundError":
      return {
        title: "카메라 또는 마이크 장치를 찾을 수 없습니다",
        guide: "장치가 올바르게 연결되어 있는지 확인하거나, 다른 USB 포트를 시도해보세요.",
      };
    case "NotReadableError":
    case "AbortError":
      return {
        title: "카메라/마이크가 다른 프로그램에서 사용 중입니다",
        guide: "Zoom, Teams 등 다른 화상 회의 프로그램을 종료한 후 다시 시도해주세요.",
      };
    case "OverconstrainedError":
      return {
        title: "요청한 카메라/마이크 설정을 지원하지 않습니다",
        guide: "브라우저를 최신 버전으로 업데이트하거나, 다른 브라우저(Chrome 권장)를 사용해보세요.",
      };
    default:
      return {
        title: "카메라/마이크에 접근할 수 없습니다",
        guide: "브라우저에서 카메라·마이크 권한을 허용하고, 장치가 정상적으로 연결되어 있는지 확인해주세요.",
      };
  }
}

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  const [resumeFile, setResumeFile] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [history, setHistory] = useState<InterviewRecord[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportData | null>(null);
  const [reportSessionId, setReportSessionId] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const micBarRef = useRef<HTMLDivElement>(null);

  // ========== 환경 테스트 상태 (개선) ==========
  const [testing, setTesting] = useState(false);
  // 카메라/마이크 각각의 세부 상태
  const [camStatus, setCamStatus] = useState<DeviceStatus>("idle");
  const [micStatus, setMicStatus] = useState<DeviceStatus>("idle");
  // 에러 메시지 (에러 발생 시 구체적 안내)
  const [deviceError, setDeviceError] = useState<{ title: string; guide: string } | null>(null);
  // 마이크 음량 레벨 (0~100, UI 바 표시용)
  const [micLevel, setMicLevel] = useState(0);
  // 마이크 실제 소리 감지 여부 (음량 임계값 초과 시 true)
  const micDetectedRef = useRef(false);
  // 애니메이션 프레임 ID (cleanup용)
  const animFrameRef = useRef<number | null>(null);
  // AudioContext 참조 (cleanup용)
  const audioCtxRef = useRef<AudioContext | null>(null);
  // 마이크 감지 타이머 (일정 시간 내 미감지 시 경고)
  const micTimerRef = useRef<NodeJS.Timeout | null>(null);
  // 하위 호환: camOk, micOk (면접 시작 판단용 유지)
  const camOk = camStatus === "ok";
  const micOk = micStatus === "ok";

  // 인증 확인 — loading 완료 후에만 리다이렉트 (sessionStorage 복원 대기)
  useEffect(() => {
    if (!loading && !token) {
      router.push("/");
      return;
    }
    // 인사담당자는 전용 대시보드로 리다이렉트
    if (!loading && user?.role === "recruiter") {
      router.push("/recruiter");
    }
  }, [loading, token, user, router]);

  // 면접 기록 로드 + 기존 이력서 확인
  useEffect(() => {
    if (user?.email) {
      // 면접 기록 로드
      interviewApi.getHistory(user.email).then(setHistory).catch(() => { });

      // DB에 저장된 기존 이력서 자동 확인 (서버 재시작 후에도 유지됨)
      resumeApi.getUserResume(user.email).then((data) => {
        if (data.resume_exists && data.filename) {
          setResumeFile(data.filename);
          // 업로드 시각을 한국어 날짜로 표시
          if (data.uploaded_at) {
            try {
              const d = new Date(data.uploaded_at);
              const dateStr = `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
              setUploadMsg(`📄 이전에 업로드한 이력서입니다. (${dateStr})`);
            } catch {
              setUploadMsg("📄 이전에 업로드한 이력서입니다.");
            }
          }
        }
      }).catch(() => { });
    }
  }, [user]);

  // 이력서 업로드
  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) { setUploadMsg("PDF 파일만 업로드 가능합니다."); return; }
    if (file.size > 10 * 1024 * 1024) { setUploadMsg("파일 크기는 10MB 이하여야 합니다."); return; }
    setUploading(true); setUploadMsg("");
    try {
      const sessionId = crypto.randomUUID();
      await resumeApi.upload(file, sessionId, user!.email);
      setResumeFile(file.name);
      setUploadMsg("✅ 이력서가 성공적으로 업로드되었습니다.");
    } catch { setUploadMsg("❌ 업로드 실패. 다시 시도해주세요."); }
    finally { setUploading(false); }
  };

  const removeResume = () => { setResumeFile(null); setUploadMsg(""); };

  // 디바이스 테스트 (개선: 단계별 피드백 + 실제 감지 확인)
  const startTest = async () => {
    // 이전 테스트 리소스 정리
    stopTest();
    setDeviceError(null);
    setCamStatus("testing");
    setMicStatus("testing");
    setMicLevel(0);
    micDetectedRef.current = false;

    try {
      // 1단계: getUserMedia로 카메라/마이크 접근 요청
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      setTesting(true);

      // 2단계: 카메라 영상 프레임 감지 (실제 영상이 나오는지 확인)
      // video 요소의 loadeddata 이벤트로 실제 영상 출력을 검증
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack && videoTrack.readyState === "live") {
        // 잠시 후 video 요소에서 영상이 로드되었는지 확인
        setTimeout(() => {
          if (videoRef.current && videoRef.current.videoWidth > 0) {
            setCamStatus("ok");
          } else if (videoTrack.readyState === "live") {
            // 영상이 아직 로드 안 됐지만 트랙은 살아있음 → 조금 더 대기
            setCamStatus("ok");
          } else {
            setCamStatus("warning");
          }
        }, 1500);
      } else {
        setCamStatus("error");
      }

      // 3단계: 마이크 음량 실시간 분석 (실제 소리가 감지되는지 확인)
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      // 마이크 음량 임계값: 이 이상이면 "소리 감지됨"으로 판단
      const MIC_THRESHOLD = 8;
      // 마이크 감지 확인 시간: 5초 내에 음량이 임계값을 넘지 않으면 경고
      const MIC_DETECT_TIMEOUT_MS = 5000;

      const drawMicLevel = () => {
        if (!streamRef.current) return;
        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        const level = Math.min(avg * 2, 100);
        setMicLevel(level);
        if (micBarRef.current) micBarRef.current.style.width = `${level}%`;

        // 음량이 임계값을 넘으면 마이크 OK로 전환
        if (avg > MIC_THRESHOLD && !micDetectedRef.current) {
          micDetectedRef.current = true;
          setMicStatus("ok");
          // 타이머가 아직 남아있으면 취소
          if (micTimerRef.current) {
            clearTimeout(micTimerRef.current);
            micTimerRef.current = null;
          }
        }
        animFrameRef.current = requestAnimationFrame(drawMicLevel);
      };
      drawMicLevel();

      // 5초 후에도 마이크 음량이 감지되지 않으면 warning 상태로 전환
      micTimerRef.current = setTimeout(() => {
        if (!micDetectedRef.current) {
          setMicStatus("warning");
        }
      }, MIC_DETECT_TIMEOUT_MS);

    } catch (err) {
      // getUserMedia 실패 시 구체적 에러 정보 표시
      const errorInfo = getDeviceErrorInfo(err);
      setDeviceError(errorInfo);
      setCamStatus("error");
      setMicStatus("error");
      setTesting(false);
    }
  };

  // testing이 true가 되어 <video>가 렌더링된 후 스트림을 연결
  useEffect(() => {
    if (testing && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [testing]);

  // 컴포넌트 unmount 시 미디어 리소스 정리 (메모리 누수 방지)
  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (micTimerRef.current) clearTimeout(micTimerRef.current);
      if (audioCtxRef.current) audioCtxRef.current.close().catch(() => { });
      streamRef.current?.getTracks().forEach(t => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopTest = () => {
    // 애니메이션 프레임 정리
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    // 마이크 감지 타이머 정리
    if (micTimerRef.current) {
      clearTimeout(micTimerRef.current);
      micTimerRef.current = null;
    }
    // AudioContext 정리
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => { });
      audioCtxRef.current = null;
    }
    // MediaStream 트랙 정리
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    setTesting(false);
    setCamStatus("idle");
    setMicStatus("idle");
    setMicLevel(0);
    setDeviceError(null);
    micDetectedRef.current = false;
  };

  // 드래그앤드롭
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }, [user]);

  // 인증 상태 로딩 중이면 로딩 화면 표시
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-[var(--text-secondary)]">로딩 중...</p>
      </div>
    </div>
  );

  if (!user) return null;

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-[1100px] mx-auto px-6 py-8">
        {/* 환영 배너 */}
        <div className="glass-card mb-8 bg-gradient-to-r from-[rgba(0,217,255,0.08)] to-[rgba(0,255,136,0.06)]">
          <h1 className="text-3xl font-bold mb-2">안녕하세요, {user.name || user.email}님! 👋</h1>
          <p className="text-[var(--text-secondary)]">오늘도 면접 준비를 위해 함께해요.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* 이력서 카드 */}
          <div className="glass-card">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <FileText size={20} className="text-[var(--cyan)]" /> 이력서 관리
            </h2>
            {resumeFile ? (
              <div className="flex items-center justify-between p-4 rounded-xl bg-[rgba(0,255,136,0.08)] border border-[rgba(0,255,136,0.2)]">
                <div className="flex items-center gap-3">
                  <CheckCircle2 size={20} className="text-[var(--green)]" />
                  <span className="text-sm font-medium">{resumeFile}</span>
                </div>
                <button onClick={removeResume} className="p-2 rounded-lg hover:bg-[rgba(255,82,82,0.1)] transition">
                  <Trash2 size={16} className="text-[var(--danger)]" />
                </button>
              </div>
            ) : (
              <div
                className="border-2 border-dashed border-[rgba(0,217,255,0.3)] rounded-xl p-8 text-center cursor-pointer hover:border-[var(--cyan)] hover:bg-[rgba(0,217,255,0.03)] transition-all"
                onClick={() => fileRef.current?.click()}
                onDragOver={e => e.preventDefault()} onDrop={onDrop}
              >
                <Upload size={32} className="mx-auto mb-3 text-[var(--cyan)]" />
                <p className="text-sm text-[var(--text-secondary)]">PDF 파일을 드래그하거나 클릭하여 업로드</p>
                <p className="text-xs text-[var(--text-secondary)] mt-1">최대 10MB</p>
              </div>
            )}
            <input ref={fileRef} type="file" accept=".pdf" hidden onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
            {uploadMsg && (
              <p className={`text-sm mt-3 ${uploadMsg.startsWith("✅") ? "text-[var(--green)]" : "text-[var(--danger)]"}`}>
                {uploadMsg}
              </p>
            )}

            {/* 지원 공고 확인 버튼 */}
            <button
              onClick={() => router.push("/jobs")}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.08)] transition"
            >
              <Briefcase size={16} /> 지원 공고 확인
            </button>
          </div>

          {/* 환경 테스트 카드 (개선: 단계별 피드백 + 상세 가이드) */}
          <div className="glass-card">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Video size={20} className="text-[var(--cyan)]" /> 환경 테스트
            </h2>

            {/* 카메라 미리보기 */}
            <div className="rounded-xl overflow-hidden bg-[rgba(0,0,0,0.3)] aspect-video mb-4 flex items-center justify-center relative">
              {testing ? (
                <>
                  <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
                  {/* 카메라 상태 오버레이 배지 */}
                  <div className="absolute top-2 right-2">
                    {camStatus === "testing" && (
                      <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[rgba(255,193,7,0.2)] text-[var(--warning)] text-xs font-medium backdrop-blur-sm">
                        <Loader2 size={12} className="animate-spin" /> 확인 중...
                      </span>
                    )}
                    {camStatus === "ok" && (
                      <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[rgba(0,255,136,0.2)] text-[var(--green)] text-xs font-medium backdrop-blur-sm">
                        <CheckCircle2 size={12} /> 정상
                      </span>
                    )}
                    {camStatus === "warning" && (
                      <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[rgba(255,193,7,0.2)] text-[var(--warning)] text-xs font-medium backdrop-blur-sm">
                        <AlertTriangle size={12} /> 영상 불안정
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <div className="text-center">
                  {camStatus === "error" ? (
                    <VideoOff size={32} className="mx-auto mb-2 text-[var(--danger)]" />
                  ) : (
                    <Video size={32} className="mx-auto mb-2 text-[var(--text-secondary)] opacity-40" />
                  )}
                  <span className="text-sm text-[var(--text-secondary)]">
                    {camStatus === "error" ? "카메라를 사용할 수 없습니다" : "카메라 미리보기"}
                  </span>
                </div>
              )}
            </div>

            {/* 마이크 레벨 바 (개선: 상태별 색상 + 소리 감지 피드백) */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {micStatus === "error" ? (
                    <MicOff size={16} className="text-[var(--danger)]" />
                  ) : micStatus === "ok" ? (
                    <Volume2 size={16} className="text-[var(--green)]" />
                  ) : (
                    <Mic size={16} className="text-[var(--text-secondary)]" />
                  )}
                  <span className="text-sm">마이크 레벨</span>
                </div>
                {/* 마이크 상태 라벨 */}
                {micStatus === "testing" && (
                  <span className="text-xs text-[var(--warning)] flex items-center gap-1">
                    <Loader2 size={10} className="animate-spin" /> 소리를 내주세요...
                  </span>
                )}
                {micStatus === "ok" && (
                  <span className="text-xs text-[var(--green)] flex items-center gap-1">
                    <CheckCircle2 size={10} /> 소리 감지됨
                  </span>
                )}
                {micStatus === "warning" && (
                  <span className="text-xs text-[var(--warning)] flex items-center gap-1">
                    <AlertTriangle size={10} /> 소리가 감지되지 않습니다
                  </span>
                )}
              </div>
              <div className="h-3 rounded-full bg-[rgba(255,255,255,0.1)] overflow-hidden">
                <div
                  ref={micBarRef}
                  className={`h-full rounded-full transition-all duration-100 ${micStatus === "ok"
                    ? "bg-gradient-to-r from-[var(--green)] to-[var(--cyan)]"
                    : micStatus === "warning"
                      ? "bg-gradient-to-r from-[var(--warning)] to-[rgba(255,193,7,0.5)]"
                      : "bg-gradient-to-r from-[var(--text-secondary)] to-[rgba(255,255,255,0.2)]"
                    }`}
                  style={{ width: `${micLevel}%` }}
                />
              </div>
              {/* 마이크 warning 시 가이드 */}
              {micStatus === "warning" && testing && (
                <div className="mt-2 p-2.5 rounded-lg bg-[rgba(255,193,7,0.06)] border border-[rgba(255,193,7,0.15)]">
                  <p className="text-xs text-[var(--warning)] leading-relaxed">
                    💡 마이크에서 소리가 감지되지 않습니다. 다음을 확인해주세요:
                  </p>
                  <ul className="text-xs text-[var(--text-secondary)] mt-1 ml-4 list-disc space-y-0.5">
                    <li>마이크가 음소거(Mute)되어 있지 않은지 확인</li>
                    <li>시스템 설정에서 올바른 입력 장치가 선택되어 있는지 확인</li>
                    <li>&quot;안녕하세요&quot;라고 말해보세요</li>
                  </ul>
                </div>
              )}
            </div>

            {/* 디바이스 상태 요약 (개선: 4단계 상태 표시) */}
            <div className="flex gap-3 text-xs mb-3">
              <StatusBadge label="카메라" status={camStatus} />
              <StatusBadge label="마이크" status={micStatus} />
            </div>

            {/* 에러 발생 시 상세 안내 패널 */}
            {deviceError && (
              <div className="mb-3 p-3 rounded-xl bg-[rgba(255,82,82,0.06)] border border-[rgba(255,82,82,0.2)]">
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="text-[var(--danger)] mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-[var(--danger)]">{deviceError.title}</p>
                    <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{deviceError.guide}</p>
                  </div>
                </div>
              </div>
            )}

            {/* 테스트 결과 요약 (모두 OK일 때) */}
            {camStatus === "ok" && micStatus === "ok" && (
              <div className="mb-3 p-3 rounded-xl bg-[rgba(0,255,136,0.06)] border border-[rgba(0,255,136,0.15)]">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-[var(--green)]" />
                  <p className="text-sm font-medium text-[var(--green)]">모든 장치가 정상적으로 작동합니다</p>
                </div>
                <p className="text-xs text-[var(--text-secondary)] mt-1 ml-6">면접을 시작할 준비가 완료되었습니다!</p>
              </div>
            )}

            {/* 테스트 버튼 */}
            <div className="flex gap-2">
              <button onClick={testing ? stopTest : startTest}
                className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition flex items-center justify-center gap-2 ${testing
                  ? "bg-[rgba(255,82,82,0.2)] text-[var(--danger)] border border-[rgba(255,82,82,0.3)] hover:bg-[rgba(255,82,82,0.3)]"
                  : "btn-gradient"
                  }`}>
                {testing ? (
                  <><X size={14} /> 테스트 중지</>
                ) : deviceError ? (
                  <><RefreshCw size={14} /> 다시 테스트</>
                ) : (
                  "환경 테스트 시작"
                )}
              </button>
            </div>
          </div>
        </div>

        {/* 면접 시작 CTA */}
        <button
          onClick={async () => {
            // 이력서 미업로드 시 경고를 표시하고, 사용자가 선택할 수 있도록 함
            if (!resumeFile) {
              const proceed = await toast.confirm(
                "⚠️ 이력서가 업로드되지 않았습니다.\n\n" +
                "이력서를 업로드하면 맞춤형 면접 질문을 받을 수 있습니다.\n\n" +
                "이력서 없이 면접을 시작하시겠습니까?",
                "면접 시작", "돌아가기"
              );
              if (!proceed) return;
            }
            router.push("/interview");
          }}
          className="w-full btn-gradient text-xl py-6 rounded-2xl mb-8 flex items-center justify-center gap-3 group"
        >
          🎥 AI 모의면접 시작하기
          <span className="text-sm opacity-70 group-hover:opacity-100">화상 면접 → 코딩 테스트 → 아키텍처 설계</span>
        </button>

        {/* 이력서 미업로드 안내 배너 */}
        {!resumeFile && (
          <div className="flex items-center gap-3 p-4 mb-8 rounded-xl bg-[rgba(255,193,7,0.08)] border border-[rgba(255,193,7,0.2)]">
            <AlertTriangle size={20} className="text-[var(--warning)] flex-shrink-0" />
            <p className="text-sm text-[var(--warning)]">
              이력서를 업로드하면 지원 직무·경력에 맞는 <strong>맞춤형 면접 질문</strong>을 받을 수 있습니다. 위 이력서 관리에서 PDF를 업로드해보세요.
            </p>
          </div>
        )}

        {/* 면접 기록 */}
        <div className="glass-card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock size={20} className="text-[var(--cyan)]" /> 면접 기록
          </h2>
          {history.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">아직 면접 기록이 없습니다.</p>
          ) : (
            <div className="space-y-3">
              {history.map(h => (
                <div key={h.session_id} className="flex items-center justify-between p-4 rounded-xl bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.06)] transition">
                  <div>
                    <p className="text-sm font-medium">{h.date}</p>
                    {h.summary && <p className="text-xs text-[var(--text-secondary)] mt-1">{h.summary}</p>}
                  </div>
                  <div className="flex items-center gap-3">
                    {h.score != null && (
                      <span className="text-sm font-bold text-[var(--cyan)]">{h.score}점</span>
                    )}
                    <button
                      onClick={async () => {
                        setReportSessionId(h.session_id);
                        setReportLoading(true);
                        setSelectedReport(null);
                        try {
                          const data = await interviewApi.getReport(h.session_id);
                          setSelectedReport(data as ReportData);
                        } catch {
                          toast.error("리포트를 불러올 수 없습니다.");
                          setReportSessionId(null);
                        } finally {
                          setReportLoading(false);
                        }
                      }}
                      className="text-xs px-3 py-1.5 rounded-lg border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition"
                    >
                      리포트
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* ========== 리포트 상세 모달 ========== */}
      {(reportLoading || selectedReport) && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => { setSelectedReport(null); setReportSessionId(null); }}
        >
          <div
            className="relative w-full max-w-5xl max-h-[90vh] mx-4 rounded-2xl overflow-hidden border border-[rgba(0,217,255,0.2)] bg-[var(--bg-secondary)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.05)] bg-[rgba(0,0,0,0.3)]">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <FileText size={18} className="text-[var(--cyan)]" />
                면접 리포트
                {reportSessionId && <span className="text-xs text-[var(--text-secondary)] font-normal">#{reportSessionId.slice(0, 8)}</span>}
              </h3>
              <div className="flex items-center gap-2">
                {selectedReport && reportSessionId && (
                  <button
                    onClick={() => {
                      const tk = sessionStorage.getItem("access_token");
                      fetch(`/api/report/${reportSessionId}/pdf`, {
                        headers: { Authorization: `Bearer ${tk}` },
                      })
                        .then((res) => { if (!res.ok) throw new Error(); return res.blob(); })
                        .then((blob) => {
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a"); a.href = url;
                          a.download = `interview_report_${reportSessionId.slice(0, 8)}.pdf`;
                          a.click(); URL.revokeObjectURL(url);
                        })
                        .catch(() => toast.error("PDF 다운로드 실패"));
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[rgba(0,217,255,0.1)] border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.2)] transition"
                  >
                    <Download size={14} /> PDF
                  </button>
                )}
                <button
                  onClick={() => { setSelectedReport(null); setReportSessionId(null); }}
                  className="p-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.1)] transition" aria-label="닫기"
                >
                  <X size={18} className="text-[var(--text-secondary)]" />
                </button>
              </div>
            </div>
            <div className="overflow-y-auto max-h-[calc(90vh-65px)] p-6">
              {reportLoading && (
                <div className="flex flex-col items-center justify-center py-20">
                  <Loader2 className="w-10 h-10 text-[var(--cyan)] animate-spin mb-4" />
                  <p className="text-[var(--text-secondary)]">리포트를 불러오는 중...</p>
                </div>
              )}
              {!reportLoading && selectedReport && <InterviewReportCharts report={selectedReport} />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ========== StatusBadge: 장치 상태 표시 컴포넌트 ==========
// idle: 회색, testing: 노란(점멸), ok: 초록, warning: 주황, error: 빨강
function StatusBadge({ label, status }: { label: string; status: DeviceStatus }) {
  const config = {
    idle: { color: "text-[var(--text-secondary)]", icon: <AlertCircle size={12} />, text: "미확인" },
    testing: { color: "text-[var(--warning)]", icon: <Loader2 size={12} className="animate-spin" />, text: "확인 중" },
    ok: { color: "text-[var(--green)]", icon: <CheckCircle2 size={12} />, text: "정상" },
    warning: { color: "text-[var(--warning)]", icon: <AlertTriangle size={12} />, text: "주의" },
    error: { color: "text-[var(--danger)]", icon: <AlertCircle size={12} />, text: "오류" },
  };
  const c = config[status];
  return (
    <span className={`flex items-center gap-1 ${c.color}`}>
      {c.icon} {label} ({c.text})
    </span>
  );
}
