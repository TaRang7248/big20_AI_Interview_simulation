"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Header from "@/components/common/Header";
import { resumeApi, interviewApi, type InterviewRecord } from "@/lib/api";
import { Upload, Trash2, Video, Mic, CheckCircle2, AlertCircle, FileText, Clock, AlertTriangle, Briefcase } from "lucide-react";

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  const [resumeFile, setResumeFile] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [history, setHistory] = useState<InterviewRecord[]>([]);
  const [testing, setTesting] = useState(false);
  const [camOk, setCamOk] = useState(false);
  const [micOk, setMicOk] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const micBarRef = useRef<HTMLDivElement>(null);

  // 인증 확인 — loading 완료 후에만 리다이렉트 (sessionStorage 복원 대기)
  useEffect(() => {
    if (!loading && !token) {
      router.push("/");
    }
  }, [loading, token, router]);

  // 면접 기록 로드
  useEffect(() => {
    if (user?.email) {
      interviewApi.getHistory(user.email).then(setHistory).catch(() => {});
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

  // 디바이스 테스트
  const startTest = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; }
      setCamOk(true);

      // 마이크 레벨
      const ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const draw = () => {
        if (!streamRef.current) return;
        analyser.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        if (micBarRef.current) micBarRef.current.style.width = `${Math.min(avg * 2, 100)}%`;
        requestAnimationFrame(draw);
      };
      draw();
      setMicOk(true);
      setTesting(true);
    } catch { alert("카메라/마이크 접근 권한이 필요합니다."); }
  };

  const stopTest = () => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    setTesting(false); setCamOk(false); setMicOk(false);
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

          {/* 디바이스 테스트 카드 */}
          <div className="glass-card">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Video size={20} className="text-[var(--cyan)]" /> 환경 테스트
            </h2>
            <div className="rounded-xl overflow-hidden bg-[rgba(0,0,0,0.3)] aspect-video mb-4 flex items-center justify-center">
              {testing ? (
                <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
              ) : (
                <span className="text-sm text-[var(--text-secondary)]">카메라 미리보기</span>
              )}
            </div>
            {/* 마이크 레벨 */}
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Mic size={16} className="text-[var(--green)]" />
                <span className="text-sm">마이크 레벨</span>
              </div>
              <div className="h-3 rounded-full bg-[rgba(255,255,255,0.1)] overflow-hidden">
                <div ref={micBarRef} className="h-full rounded-full bg-gradient-to-r from-[var(--green)] to-[var(--cyan)] transition-all duration-100" style={{ width: "0%" }} />
              </div>
            </div>
            <div className="flex gap-2 text-xs mb-3">
              <span className={`flex items-center gap-1 ${camOk ? "text-[var(--green)]" : "text-[var(--text-secondary)]"}`}>
                {camOk ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />} 카메라
              </span>
              <span className={`flex items-center gap-1 ${micOk ? "text-[var(--green)]" : "text-[var(--text-secondary)]"}`}>
                {micOk ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />} 마이크
              </span>
            </div>
            <button onClick={testing ? stopTest : startTest}
              className={`w-full py-2.5 rounded-lg text-sm font-semibold transition ${testing ? "bg-[rgba(255,82,82,0.2)] text-[var(--danger)] border border-[rgba(255,82,82,0.3)]" : "btn-gradient"}`}>
              {testing ? "테스트 중지" : "환경 테스트 시작"}
            </button>
          </div>
        </div>

        {/* 면접 시작 CTA */}
        <button
          onClick={() => {
            // 이력서 미업로드 시 경고를 표시하고, 사용자가 선택할 수 있도록 함
            if (!resumeFile) {
              const proceed = window.confirm(
                "⚠️ 이력서가 업로드되지 않았습니다.\n\n" +
                "이력서를 업로드하면 맞춤형 면접 질문을 받을 수 있습니다.\n\n" +
                "이력서 없이 면접을 시작하시겠습니까?"
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
                      onClick={() => window.open(`/api/report/${h.session_id}`, "_blank")}
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
    </div>
  );
}
