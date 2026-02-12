"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/common/Header";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/contexts/ToastContext";
import { interviewApi, authApi, type InterviewRecord } from "@/lib/api";
import InterviewReportCharts, { ReportData } from "@/components/report/InterviewReportCharts";
import {
  User, Mail, Calendar, MapPin, Phone, Shield, Clock,
  ChevronRight, FileText, Settings, TrendingUp, Award, Briefcase, Trash2,
  X, Loader2, Download,
} from "lucide-react";

/**
 * 내 정보 페이지 — 개인정보 요약 + 지난 면접 기록
 * 회원정보·비밀번호 수정은 /settings 페이지에서 처리
 */
export default function ProfilePage() {
  const { user, token, loading, logout } = useAuth();
  const { toast } = useToast();
  const router = useRouter();

  // 면접 기록 상태
  const [history, setHistory] = useState<InterviewRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // 리포트 상세 모달 상태
  const [selectedReport, setSelectedReport] = useState<ReportData | null>(null);
  const [reportSessionId, setReportSessionId] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  // 회원탈퇴 모달 상태
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteForm, setDeleteForm] = useState({ email: "", password: "" });
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);

  // 인증 확인 — loading 완료 후에만 리다이렉트 (sessionStorage 복원 대기)
  useEffect(() => {
    if (!loading && !token) {
      router.push("/");
    }
  }, [loading, token, router]);

  // 면접 기록 로드
  useEffect(() => {
    if (user?.email) {
      setHistoryLoading(true);
      interviewApi
        .getHistory(user.email)
        .then(setHistory)
        .catch(() => {})
        .finally(() => setHistoryLoading(false));
    }
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

  // 면접 통계 계산
  const totalInterviews = history.length;
  const scoredHistory = history.filter((h) => h.score != null);
  const avgScore =
    scoredHistory.length > 0
      ? Math.round(scoredHistory.reduce((sum, h) => sum + (h.score ?? 0), 0) / scoredHistory.length)
      : 0;
  const bestScore =
    scoredHistory.length > 0
      ? Math.max(...scoredHistory.map((h) => h.score ?? 0))
      : 0;

  // ── 면접 기록 클릭 → 리포트 상세 조회 ──
  const handleViewReport = async (sessionId: string) => {
    setReportSessionId(sessionId);
    setReportLoading(true);
    setSelectedReport(null);
    try {
      const data = await interviewApi.getReport(sessionId);
      setSelectedReport(data as ReportData);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "리포트를 불러올 수 없습니다.");
      setReportSessionId(null);
    } finally {
      setReportLoading(false);
    }
  };

  // ── 회원탈퇴 처리 ──
  const handleDeleteAccount = async () => {
    setDeleteError("");
    if (!deleteForm.email || !deleteForm.password) {
      setDeleteError("이메일과 비밀번호를 모두 입력해주세요.");
      return;
    }
    if (deleteForm.email !== user.email) {
      setDeleteError("현재 로그인된 계정의 이메일을 입력해주세요.");
      return;
    }
    setDeleting(true);
    try {
      const res = await authApi.deleteAccount(deleteForm.email, deleteForm.password);
      if (res.success) {
        toast.success("회원 탈퇴가 완료되었습니다. 이용해 주셔서 감사합니다.");
        logout();
        router.push("/");
      } else {
        setDeleteError(res.message || "회원 탈퇴에 실패했습니다.");
      }
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : "회원 탈퇴 처리 중 오류가 발생했습니다.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-[900px] mx-auto px-6 py-10">
        {/* ========== 프로필 헤더 ========== */}
        <div className="glass-card mb-8 flex flex-col sm:flex-row items-center gap-6">
          {/* 아바타 */}
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[var(--cyan)] to-[var(--green)] flex items-center justify-center text-3xl font-bold text-white flex-shrink-0">
            {(user.name || user.email)[0].toUpperCase()}
          </div>

          <div className="flex-1 text-center sm:text-left">
            <h1 className="text-2xl font-bold text-white mb-1">
              {user.name || "사용자"}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">{user.email}</p>
            {user.role && (
              <span className="inline-block mt-2 px-3 py-1 rounded-full text-xs bg-[rgba(0,217,255,0.12)] text-[var(--cyan)] border border-[rgba(0,217,255,0.25)]">
                {user.role === "candidate" ? "지원자" : user.role === "recruiter" ? "채용담당자" : user.role}
              </span>
            )}
          </div>

          {/* 설정 버튼 */}
          <div className="flex flex-col sm:flex-row gap-2">
            <button
              onClick={() => router.push("/settings")}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.08)] transition"
            >
              <Settings size={16} /> 회원정보 수정
            </button>
            <button
              onClick={() => setShowDeleteModal(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold border border-[rgba(255,82,82,0.3)] text-red-400 hover:bg-[rgba(255,82,82,0.08)] transition"
            >
              <Trash2 size={16} /> 회원탈퇴
            </button>
          </div>
        </div>

        {/* ========== 개인정보 카드 ========== */}
        <section className="glass-card mb-8">
          <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
            <User size={18} className="text-[var(--cyan)]" /> 개인 정보
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <InfoItem icon={<Mail size={15} />} label="이메일" value={user.email} />
            <InfoItem icon={<User size={15} />} label="이름" value={user.name || "-"} />
            <InfoItem icon={<Calendar size={15} />} label="생년월일" value={user.birth_date || "-"} />
            <InfoItem
              icon={<Shield size={15} />}
              label="성별"
              value={
                user.gender === "male" ? "남성" : user.gender === "female" ? "여성" : "-"
              }
            />
            <InfoItem icon={<MapPin size={15} />} label="주소" value={user.address || "-"} />
            <InfoItem icon={<Phone size={15} />} label="전화번호" value={user.phone || "-"} />
            <InfoItem
              icon={<Briefcase size={15} />}
              label="회원 유형"
              value={
                user.role === "candidate" ? "지원자" : user.role === "recruiter" ? "인사담당자" : "-"
              }
            />
          </div>
        </section>

        {/* ========== 면접 통계 ========== */}
        <section className="grid grid-cols-3 gap-4 mb-8">
          <StatCard icon={<FileText size={20} />} label="총 면접 횟수" value={`${totalInterviews}회`} color="cyan" />
          <StatCard icon={<TrendingUp size={20} />} label="평균 점수" value={totalInterviews > 0 ? `${avgScore}점` : "-"} color="green" />
          <StatCard icon={<Award size={20} />} label="최고 점수" value={totalInterviews > 0 ? `${bestScore}점` : "-"} color="yellow" />
        </section>

        {/* ========== 면접 기록 ========== */}
        <section className="glass-card">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Clock size={18} className="text-[var(--cyan)]" /> 면접 기록
            </h2>
            {totalInterviews > 0 && (
              <span className="text-xs text-[var(--text-secondary)]">총 {totalInterviews}건</span>
            )}
          </div>

          {historyLoading ? (
            <div className="text-center py-10 text-sm text-[var(--text-secondary)]">불러오는 중...</div>
          ) : history.length === 0 ? (
            <div className="text-center py-10">
              <p className="text-sm text-[var(--text-secondary)] mb-4">아직 면접 기록이 없습니다.</p>
              <button
                onClick={() => router.push("/dashboard")}
                className="btn-gradient px-6 py-2.5 rounded-xl text-sm"
              >
                첫 면접 시작하기
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {history.map((h) => (
                <div
                  key={h.session_id}
                  className="flex items-center justify-between p-4 rounded-xl bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.06)] transition cursor-pointer group"
                  onClick={() => handleViewReport(h.session_id)}
                >
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">
                      {(() => {
                        try {
                          const d = new Date(h.date);
                          return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
                        } catch { return h.date; }
                      })()}
                    </p>
                    {h.summary && (
                      <p className="text-xs text-[var(--text-secondary)] mt-1 line-clamp-1">{h.summary}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    {h.score != null && (
                      <span
                        className={`text-sm font-bold ${
                          h.score >= 80
                            ? "text-[var(--green)]"
                            : h.score >= 60
                              ? "text-[var(--cyan)]"
                              : h.score >= 40
                                ? "text-[var(--warning)]"
                                : "text-[var(--danger)]"
                        }`}
                      >
                        {h.score}점
                      </span>
                    )}
                    <span className="text-xs text-[var(--text-secondary)] hidden sm:inline">질문 {h.summary?.match(/질문\s*(\d+)/)?.[1] ?? "-"}개 · 답변 {h.summary?.match(/답변\s*(\d+)/)?.[1] ?? "-"}개</span>
                    <ChevronRight
                      size={16}
                      className="text-[var(--text-secondary)] group-hover:text-[var(--cyan)] transition"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
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
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.05)] bg-[rgba(0,0,0,0.3)]">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <FileText size={18} className="text-[var(--cyan)]" />
                면접 리포트
                {reportSessionId && (
                  <span className="text-xs text-[var(--text-secondary)] font-normal">
                    #{reportSessionId.slice(0, 8)}
                  </span>
                )}
              </h3>
              <div className="flex items-center gap-2">
                {/* PDF 다운로드 버튼 */}
                {selectedReport && reportSessionId && (
                  <button
                    onClick={() => {
                      const tk = sessionStorage.getItem("access_token");
                      fetch(`/api/report/${reportSessionId}/pdf`, {
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
                          a.download = `interview_report_${reportSessionId.slice(0, 8)}.pdf`;
                          a.click();
                          URL.revokeObjectURL(url);
                        })
                        .catch(() => toast.error("PDF 다운로드에 실패했습니다."));
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[rgba(0,217,255,0.1)] border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.2)] transition"
                  >
                    <Download size={14} /> PDF
                  </button>
                )}
                {/* 닫기 버튼 */}
                <button
                  onClick={() => { setSelectedReport(null); setReportSessionId(null); }}
                  className="p-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.1)] transition"
                  aria-label="닫기"
                >
                  <X size={18} className="text-[var(--text-secondary)]" />
                </button>
              </div>
            </div>

            {/* 모달 본문 */}
            <div className="overflow-y-auto max-h-[calc(90vh-65px)] p-6">
              {reportLoading && (
                <div className="flex flex-col items-center justify-center py-20">
                  <Loader2 className="w-10 h-10 text-[var(--cyan)] animate-spin mb-4" />
                  <p className="text-[var(--text-secondary)]">리포트를 불러오는 중...</p>
                </div>
              )}
              {!reportLoading && selectedReport && (
                <InterviewReportCharts report={selectedReport} />
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========== 회원탈퇴 확인 모달 ========== */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass-card max-w-md w-full mx-4 p-6 rounded-2xl border border-[rgba(255,82,82,0.3)]">
            <h3 className="text-xl font-bold text-red-400 mb-2">⚠️ 회원 탈퇴</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-1">
              탈퇴 시 모든 개인 정보와 면접 기록이 <strong className="text-red-400">영구적으로 삭제</strong>됩니다.
            </p>
            <p className="text-sm text-[var(--text-secondary)] mb-5">
              본인 확인을 위해 이메일과 비밀번호를 입력해주세요.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">이메일</label>
                <input
                  type="email"
                  className="input-field"
                  placeholder="가입한 이메일"
                  value={deleteForm.email}
                  onChange={(e) => setDeleteForm((p) => ({ ...p, email: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">비밀번호</label>
                <input
                  type="password"
                  className="input-field"
                  placeholder="현재 비밀번호"
                  value={deleteForm.password}
                  onChange={(e) => setDeleteForm((p) => ({ ...p, password: e.target.value }))}
                />
              </div>
            </div>

            {deleteError && (
              <p className="mt-3 text-sm text-red-400 bg-[rgba(255,82,82,0.1)] p-3 rounded-lg">
                {deleteError}
              </p>
            )}

            <div className="flex gap-3 mt-5">
              <button
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteForm({ email: "", password: "" });
                  setDeleteError("");
                }}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-[rgba(255,255,255,0.05)] text-white hover:bg-[rgba(255,255,255,0.1)] border border-gray-600 transition"
              >
                취소
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleting}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/40 transition disabled:opacity-50"
              >
                {deleting ? "처리 중..." : "탈퇴하기"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ========== 하위 컴포넌트 ========== */

/** 개인정보 항목 — 읽기 전용 표시 */
function InfoItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-xl bg-[rgba(255,255,255,0.03)]">
      <span className="text-[var(--cyan)] mt-0.5">{icon}</span>
      <div>
        <p className="text-xs text-[var(--text-secondary)]">{label}</p>
        <p className="text-sm text-white font-medium">{value}</p>
      </div>
    </div>
  );
}

/** 통계 카드 */
function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: "cyan" | "green" | "yellow";
}) {
  const colorMap = {
    cyan: { bg: "rgba(0,217,255,0.08)", border: "rgba(0,217,255,0.2)", text: "var(--cyan)" },
    green: { bg: "rgba(0,255,136,0.08)", border: "rgba(0,255,136,0.2)", text: "var(--green)" },
    yellow: { bg: "rgba(255,193,7,0.08)", border: "rgba(255,193,7,0.2)", text: "var(--warning)" },
  };
  const c = colorMap[color];

  return (
    <div
      className="glass-card flex flex-col items-center text-center py-5"
      style={{ background: c.bg, borderColor: c.border }}
    >
      <span style={{ color: c.text }}>{icon}</span>
      <p className="text-2xl font-bold text-white mt-2">{value}</p>
      <p className="text-xs text-[var(--text-secondary)] mt-1">{label}</p>
    </div>
  );
}
