"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Modal from "@/components/common/Modal";

interface Props { open: boolean; onClose: () => void; onSwitch: () => void; onForgot: () => void; }

export default function LoginModal({ open, onClose, onSwitch, onForgot }: Props) {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  const handleLogin = async () => {
    setError("");
    if (!email || !password) { setError("이메일과 비밀번호를 입력해주세요."); return; }
    setLoading(true);
    try {
      const result = await login(email, password);
      onClose();
      // 역할별 리다이렉트: 인사담당자 → /recruiter, 지원자 → /dashboard
      if (result?.role === "recruiter") {
        router.push("/recruiter");
      } else {
        router.push("/dashboard");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "로그인 실패");
    } finally { setLoading(false); }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter") handleLogin(); };

  return (
    <Modal open={open} onClose={onClose} title="로그인">
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">이메일</label>
          <input className="input-field" type="email" placeholder="example@email.com"
            value={email} onChange={e => setEmail(e.target.value)} onKeyDown={handleKeyDown} />
        </div>
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">비밀번호</label>
          <input className="input-field" type="password" placeholder="비밀번호 입력"
            value={password} onChange={e => setPassword(e.target.value)} onKeyDown={handleKeyDown} />
        </div>

        {error && <p className="text-sm text-[var(--danger)] bg-[rgba(255,82,82,0.1)] p-3 rounded-lg">{error}</p>}

        <button onClick={handleLogin} disabled={loading} className="btn-gradient w-full text-base py-3">
          {loading ? "로그인 중..." : "로그인"}
        </button>

        {/* 소셜 로그인 */}
        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[rgba(255,255,255,0.1)]" /></div>
          <div className="relative flex justify-center text-xs"><span className="bg-[var(--bg-card)] px-3 text-[var(--text-secondary)]">또는</span></div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <a href={`${apiUrl}/api/auth/social/kakao`} className="flex items-center justify-center gap-2 py-3 rounded-lg bg-[#FEE500] text-[#000000] text-sm font-semibold hover:brightness-95 transition">
            카카오
          </a>
          <a href={`${apiUrl}/api/auth/social/google`} className="flex items-center justify-center gap-2 py-3 rounded-lg bg-white text-gray-700 text-sm font-semibold hover:brightness-95 transition">
            Google
          </a>
          <a href={`${apiUrl}/api/auth/social/naver`} className="flex items-center justify-center gap-2 py-3 rounded-lg bg-[#03C75A] text-white text-sm font-semibold hover:brightness-95 transition">
            네이버
          </a>
        </div>

        <div className="flex justify-between text-sm text-[var(--text-secondary)]">
          <button onClick={onForgot} className="text-[var(--cyan)] hover:underline">비밀번호 찾기</button>
          <button onClick={onSwitch} className="text-[var(--cyan)] hover:underline">회원가입</button>
        </div>
      </div>
    </Modal>
  );
}
