"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/common/Header";
import { useAuth } from "@/contexts/AuthContext";
import { interviewApi, type InterviewRecord } from "@/lib/api";
import {
  User, Mail, Calendar, MapPin, Phone, Shield, Clock,
  ChevronRight, FileText, Settings, TrendingUp, Award,
} from "lucide-react";

/**
 * 내 정보 페이지 — 개인정보 요약 + 지난 면접 기록
 * 회원정보·비밀번호 수정은 /settings 페이지에서 처리
 */
export default function ProfilePage() {
  const { user, token } = useAuth();
  const router = useRouter();

  // 면접 기록 상태
  const [history, setHistory] = useState<InterviewRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // 인증 확인
  useEffect(() => {
    if (!token && typeof window !== "undefined") {
      router.push("/");
    }
  }, [token, router]);

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
          <button
            onClick={() => router.push("/settings")}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold border border-[rgba(0,217,255,0.3)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.08)] transition"
          >
            <Settings size={16} /> 회원정보 수정
          </button>
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
                user.gender === "male" ? "남성" : user.gender === "female" ? "여성" : user.gender === "other" ? "기타" : "-"
              }
            />
            <InfoItem icon={<MapPin size={15} />} label="주소" value={user.address || "-"} />
            <InfoItem icon={<Phone size={15} />} label="전화번호" value={user.phone || "-"} />
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
                  onClick={() => window.open(`/api/report/${h.session_id}`, "_blank")}
                >
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">{h.date}</p>
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
