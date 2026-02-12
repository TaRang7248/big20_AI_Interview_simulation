"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, Home, User, Briefcase, Building2, Settings, Menu, X } from "lucide-react";

/**
 * 공통 헤더 컴포넌트 ─────────────────────
 * - 역할(role)에 따라 네비게이션 메뉴가 달라짐
 * - 인사담당자(recruiter): 인사담당자 대시보드, 공고 관리, 내 정보
 * - 지원자(candidate):      대시보드, 공고, 내 정보
 * - 모바일: 햄버거 메뉴 → 슬라이드 Drawer 지원
 */
export default function Header() {
  const { user, logout } = useAuth();
  const pathname = usePathname();            // 현재 활성 경로 (active link 표시용)
  const isRecruiter = user?.role === "recruiter";
  const [drawerOpen, setDrawerOpen] = useState(false); // 모바일 Drawer 열림 상태

  // 페이지 이동 시 자동으로 Drawer 닫기
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  // Drawer 열림 시 body 스크롤 잠금
  useEffect(() => {
    if (drawerOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [drawerOpen]);

  // Escape 키로 Drawer 닫기
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setDrawerOpen(false);
  }, []);

  useEffect(() => {
    if (drawerOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [drawerOpen, handleKeyDown]);

  /**
   * 링크 스타일 헬퍼
   * - isActive: 현재 경로와 일치하면 활성 스타일 적용
   * - mobile: true이면 Drawer 내부용 전폭 스타일
   */
  const getLinkCls = (href: string, mobile = false) => {
    const isActive = pathname === href;
    const base = "flex items-center gap-2 text-sm rounded-lg border transition";
    const activeStyle = isActive
      ? "bg-[rgba(0,217,255,0.15)] text-white border-[rgba(0,217,255,0.6)]"
      : "border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)]";

    return mobile
      ? `${base} ${activeStyle} px-4 py-3 w-full`         // Drawer 내부: 전폭, 패딩 크게
      : `${base} ${activeStyle} px-4 py-2`;                // 데스크탑: 기본
  };

  // ── 네비게이션 링크 목록 (역할별) ──
  const navLinks = isRecruiter
    ? [
        { href: "/recruiter", icon: Home, label: "대시보드" },
        { href: "/jobs", icon: Briefcase, label: "공고 목록" },
      ]
    : [
        { href: "/dashboard", icon: Home, label: "대시보드" },
        { href: "/jobs", icon: Briefcase, label: "공고" },
      ];

  // 공통 링크 (내 정보)
  const commonLinks = [
    { href: "/profile", icon: User, label: "내 정보" },
  ];

  return (
    <>
      <header className="sticky top-0 z-50 flex items-center justify-between px-4 md:px-8 py-4 bg-[rgba(20,20,40,0.95)] border-b border-[rgba(0,217,255,0.15)] backdrop-blur-xl">
        {/* ── 로고 ── */}
        <Link href="/" className="text-xl font-bold gradient-text">
          🎯 AI 모의면접
        </Link>

        {/* ── 데스크탑 네비게이션 (md 이상에서 표시) ── */}
        <nav className="hidden md:flex items-center gap-3" aria-label="메인 네비게이션">
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

              {/* 역할별 링크 */}
              {navLinks.map(({ href, icon: Icon, label }) => (
                <Link key={href} href={href} className={getLinkCls(href)} aria-current={pathname === href ? "page" : undefined}>
                  <Icon size={14} /> {label}
                </Link>
              ))}

              {/* 공통 링크 */}
              {commonLinks.map(({ href, icon: Icon, label }) => (
                <Link key={href} href={href} className={getLinkCls(href)} aria-current={pathname === href ? "page" : undefined}>
                  <Icon size={14} /> {label}
                </Link>
              ))}

              {/* 로그아웃 */}
              <button
                onClick={logout}
                className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(255,82,82,0.4)] text-[var(--danger)] hover:bg-[rgba(255,82,82,0.1)] transition"
              >
                <LogOut size={14} /> 로그아웃
              </button>
            </>
          ) : (
            <Link href="/" className="btn-gradient text-sm !py-2 !px-5 rounded-lg">
              로그인
            </Link>
          )}
        </nav>

        {/* ── 모바일 햄버거 버튼 (md 미만에서 표시) ── */}
        {user && (
          <button
            onClick={() => setDrawerOpen(true)}
            className="md:hidden flex items-center justify-center w-10 h-10 rounded-lg border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition"
            aria-label="메뉴 열기"
            aria-expanded={drawerOpen}
          >
            <Menu size={20} />
          </button>
        )}

        {/* 비로그인 모바일 */}
        {!user && (
          <Link href="/" className="md:hidden btn-gradient text-sm !py-2 !px-5 rounded-lg">
            로그인
          </Link>
        )}
      </header>

      {/* ── 모바일 Drawer (슬라이드 메뉴) ── */}
      {user && (
        <>
          {/* 오버레이 (배경 어둡게) */}
          <div
            className={`
              fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm
              transition-opacity duration-300
              ${drawerOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}
            `}
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer 패널 (오른쪽에서 슬라이드) */}
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="모바일 메뉴"
            className={`
              fixed top-0 right-0 z-[70] h-full w-72 max-w-[80vw]
              bg-[rgba(20,20,40,0.98)] border-l border-[rgba(0,217,255,0.15)] backdrop-blur-xl
              flex flex-col
              transition-transform duration-300 ease-out
              ${drawerOpen ? "translate-x-0" : "translate-x-full"}
            `}
          >
            {/* Drawer 헤더 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[rgba(0,217,255,0.1)]">
              <span className="text-lg font-bold gradient-text">메뉴</span>
              <button
                onClick={() => setDrawerOpen(false)}
                className="flex items-center justify-center w-9 h-9 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition"
                aria-label="메뉴 닫기"
              >
                <X size={20} />
              </button>
            </div>

            {/* 사용자 정보 */}
            <div className="px-5 py-4 border-b border-[rgba(0,217,255,0.1)]">
              {isRecruiter && (
                <span className="inline-flex items-center gap-1 mb-2 px-2 py-0.5 text-[10px] font-bold rounded-full bg-[rgba(206,147,216,0.15)] text-[#ce93d8] border border-[rgba(206,147,216,0.3)]">
                  <Building2 size={10} /> 인사담당자
                </span>
              )}
              <p className="text-sm text-white/80">
                <strong className="text-[var(--cyan)]">{user.name || user.email}</strong>님
              </p>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">{user.email}</p>
            </div>

            {/* 네비게이션 링크 */}
            <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto" aria-label="모바일 네비게이션">
              {navLinks.map(({ href, icon: Icon, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={getLinkCls(href, true)}
                  aria-current={pathname === href ? "page" : undefined}
                  onClick={() => setDrawerOpen(false)}
                >
                  <Icon size={16} /> {label}
                </Link>
              ))}

              {commonLinks.map(({ href, icon: Icon, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={getLinkCls(href, true)}
                  aria-current={pathname === href ? "page" : undefined}
                  onClick={() => setDrawerOpen(false)}
                >
                  <Icon size={16} /> {label}
                </Link>
              ))}

              {/* 설정 링크 */}
              <Link
                href="/settings"
                className={getLinkCls("/settings", true)}
                aria-current={pathname === "/settings" ? "page" : undefined}
                onClick={() => setDrawerOpen(false)}
              >
                <Settings size={16} /> 설정
              </Link>
            </nav>

            {/* 로그아웃 버튼 (하단 고정) */}
            <div className="px-4 py-4 border-t border-[rgba(0,217,255,0.1)]">
              <button
                onClick={() => { logout(); setDrawerOpen(false); }}
                className="flex items-center justify-center gap-2 w-full px-4 py-3 text-sm rounded-lg border border-[rgba(255,82,82,0.4)] text-[var(--danger)] hover:bg-[rgba(255,82,82,0.1)] transition"
              >
                <LogOut size={16} /> 로그아웃
              </button>
            </div>
          </aside>
        </>
      )}
    </>
  );
}
