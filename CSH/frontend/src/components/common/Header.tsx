"use client";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, Home, User, Briefcase, Building2, Settings } from "lucide-react";

/**
 * 공통 헤더 컴포넌트 ─────────────────────
 * - 역할(role)에 따라 네비게이션 메뉴가 달라짐
 * - 인사담당자(recruiter): 인사담당자 대시보드, 공고 관리, 내 정보
 * - 지원자(candidate):      대시보드, 공고, 내 정보
 */
export default function Header() {
  const { user, logout } = useAuth();
  const isRecruiter = user?.role === "recruiter";

  // 링크 스타일 헬퍼
  const linkCls = "flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition";

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 bg-[rgba(20,20,40,0.95)] border-b border-[rgba(0,217,255,0.15)] backdrop-blur-xl">
      <Link href="/" className="text-xl font-bold gradient-text">
        🎯 AI 모의면접
      </Link>

      <div className="flex items-center gap-3">
        {user ? (
          <>
            {/* 역할 뱃지 */}
            <span className="text-sm text-[var(--text-secondary)]">
              {isRecruiter && (
                <span className="inline-flex items-center gap-1 mr-2 px-2 py-0.5 text-[10px] font-bold rounded-full bg-[rgba(206,147,216,0.15)] text-[#ce93d8] border border-[rgba(206,147,216,0.3)]">
                  <Building2 size={10} /> 인사담당자
                </span>
              )}
              <strong className="text-[var(--cyan)]">{user.name || user.email}</strong>님
            </span>

            {isRecruiter ? (
              /* ── 인사담당자 전용 메뉴 ── */
              <>
                <Link href="/recruiter" className={linkCls}>
                  <Home size={14} /> 대시보드
                </Link>
                <Link href="/jobs" className={linkCls}>
                  <Briefcase size={14} /> 공고 목록
                </Link>
              </>
            ) : (
              /* ── 지원자 메뉴 ── */
              <>
                <Link href="/dashboard" className={linkCls}>
                  <Home size={14} /> 대시보드
                </Link>
                <Link href="/jobs" className={linkCls}>
                  <Briefcase size={14} /> 공고
                </Link>
              </>
            )}

            {/* 공통 메뉴 */}
            <Link href="/profile" className={linkCls}>
              <User size={14} /> 내 정보
            </Link>
            <button onClick={logout} className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(255,82,82,0.4)] text-[var(--danger)] hover:bg-[rgba(255,82,82,0.1)] transition">
              <LogOut size={14} /> 로그아웃
            </button>
          </>
        ) : (
          <Link href="/" className="btn-gradient text-sm !py-2 !px-5 rounded-lg">
            로그인
          </Link>
        )}
      </div>
    </header>
  );
}
