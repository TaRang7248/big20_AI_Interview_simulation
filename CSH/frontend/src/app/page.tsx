"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import LoginModal from "@/components/auth/LoginModal";
import RegisterModal from "@/components/auth/RegisterModal";
import ForgotPasswordModal from "@/components/auth/ForgotPasswordModal";
import { FileText, Mic, BarChart3, Brain, Code2, ArrowRight } from "lucide-react";

type ModalState = "none" | "login" | "register" | "forgot";

const features = [
  { icon: FileText, title: "이력서 RAG", desc: "PDF 이력서를 분석하여 맞춤형 질문을 생성합니다", color: "#00d9ff" },
  { icon: Mic, title: "자연스러운 음성 대화", desc: "Hume AI TTS로 감정이 담긴 면접관 음성을 제공합니다", color: "#00ff88" },
  { icon: BarChart3, title: "실시간 평가", desc: "답변을 즉시 분석하고 상세한 피드백을 제공합니다", color: "#ffc107" },
  { icon: Brain, title: "감정 분석", desc: "실시간 표정 분석으로 면접 태도를 평가합니다", color: "#ce93d8" },
  { icon: Code2, title: "코딩 테스트", desc: "실제 코딩 면접과 동일한 환경의 Web IDE를 제공합니다", color: "#ff9800" },
];

export default function LandingPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [modal, setModal] = useState<ModalState>("none");

  const handleStart = () => {
    if (user) {
      // 역할별 대시보드 리다이렉트
      router.push(user.role === "recruiter" ? "/recruiter" : "/dashboard");
    } else {
      setModal("login");
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* 헤더 */}
      <header className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 bg-[rgba(20,20,40,0.95)] border-b border-[rgba(0,217,255,0.15)] backdrop-blur-xl">
        <span className="text-xl font-bold gradient-text">🎯 AI 모의면접</span>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="text-sm text-[var(--text-secondary)]">
                <strong className="text-[var(--cyan)]">{user.name}</strong>님
              </span>
              <button onClick={() => router.push(user.role === "recruiter" ? "/recruiter" : "/dashboard")} className="btn-gradient text-sm !py-2 !px-5">
                대시보드
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setModal("login")} className="px-5 py-2 text-sm rounded-lg border border-[rgba(0,217,255,0.4)] text-[var(--cyan)] hover:bg-[rgba(0,217,255,0.1)] transition">
                로그인
              </button>
              <button onClick={() => setModal("register")} className="btn-gradient text-sm !py-2 !px-5">
                회원가입
              </button>
            </>
          )}
        </div>
      </header>

      {/* 히어로 */}
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="text-center max-w-3xl mx-auto mt-16 mb-12">
          <h1 className="text-5xl font-extrabold leading-tight mb-6">
            <span className="gradient-text">AI 기반</span>
            <br />모의면접 시뮬레이션
          </h1>
          <p className="text-lg text-[var(--text-secondary)] mb-10 leading-relaxed">
            이력서 기반 맞춤 질문, 실시간 감정 분석, 코딩 테스트까지<br />
            실제 면접과 동일한 환경에서 완벽하게 준비하세요.
          </p>
          <button onClick={handleStart} className="btn-gradient text-lg px-10 py-4 rounded-2xl inline-flex items-center gap-2 group">
            {user ? "대시보드로 이동" : "무료로 시작하기"}
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        {/* 기능 카드 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5 max-w-6xl mx-auto w-full px-4 mb-20">
          {features.map(f => (
            <div key={f.title} className="glass-card flex flex-col items-center text-center py-8 px-4 hover:border-[rgba(0,217,255,0.4)] hover:-translate-y-1 transition-all duration-300">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ background: `${f.color}22` }}>
                <f.icon size={28} style={{ color: f.color }} />
              </div>
              <h3 className="font-semibold text-base mb-2">{f.title}</h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </main>

      {/* 모달 */}
      <LoginModal open={modal === "login"} onClose={() => setModal("none")} onSwitch={() => setModal("register")} onForgot={() => setModal("forgot")} />
      <RegisterModal open={modal === "register"} onClose={() => setModal("none")} onSwitch={() => setModal("login")} />
      <ForgotPasswordModal open={modal === "forgot"} onClose={() => setModal("none")} onBack={() => setModal("login")} />
    </div>
  );
}
