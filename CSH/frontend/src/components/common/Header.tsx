"use client";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, Home, User, Briefcase } from "lucide-react";

export default function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 bg-[rgba(20,20,40,0.95)] border-b border-[rgba(0,217,255,0.15)] backdrop-blur-xl">
      <Link href="/" className="text-xl font-bold gradient-text">
        🎯 AI 모의면접
      </Link>

      <div className="flex items-center gap-4">
        {user ? (
          <>
            <span className="text-sm text-[var(--text-secondary)]">
              안녕하세요, <strong className="text-[var(--cyan)]">{user.name || user.email}</strong>님
            </span>
            <Link href="/dashboard" className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition">
              <Home size={14} /> 대시보드
            </Link>
            <Link href="/profile" className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition">
              <User size={14} /> 내 정보
            </Link>
            <Link href="/jobs" className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition">
              <Briefcase size={14} /> 공고
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
