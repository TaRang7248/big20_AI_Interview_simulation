"use client";
import { useState, useCallback } from "react";
import { authApi } from "@/lib/api";
import Modal from "@/components/common/Modal";

interface Props { open: boolean; onClose: () => void; onSwitch: () => void; }

export default function RegisterModal({ open, onClose, onSwitch }: Props) {
  const [form, setForm] = useState({ email: "", password: "", passwordConfirm: "", name: "", birth_date: "", gender: "", address: "", phone: "", role: "candidate" });
  const [emailStatus, setEmailStatus] = useState<"idle" | "checking" | "available" | "taken">("idle");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key: string, val: string) => setForm(p => ({ ...p, [key]: val }));

  const checkEmail = useCallback(async (email: string) => {
    if (!email || !email.includes("@")) return;
    setEmailStatus("checking");
    try {
      const res = await authApi.checkEmail(email);
      setEmailStatus(res.available ? "available" : "taken");
    } catch { setEmailStatus("idle"); }
  }, []);

  const handleSubmit = async () => {
    setError("");
    if (!form.email || !form.password || !form.name) { setError("이메일, 비밀번호, 이름은 필수입니다."); return; }
    if (form.password.length < 8) { setError("비밀번호는 8자 이상이어야 합니다."); return; }
    if (form.password !== form.passwordConfirm) { setError("비밀번호가 일치하지 않습니다."); return; }
    if (emailStatus === "taken") { setError("이미 사용 중인 이메일입니다."); return; }
    setLoading(true);
    try {
      await authApi.register({ email: form.email, password: form.password, name: form.name, birth_date: form.birth_date, gender: form.gender, address: form.address, phone: form.phone, role: form.role });
      alert("회원가입이 완료되었습니다! 로그인 해주세요.");
      onSwitch();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "회원가입 실패");
    } finally { setLoading(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="회원가입" maxWidth="520px">
      <div className="space-y-4">
        {/* 이메일 */}
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">이메일 *</label>
          <input className="input-field" type="email" placeholder="example@email.com" value={form.email}
            onChange={e => { set("email", e.target.value); setEmailStatus("idle"); }}
            onBlur={e => checkEmail(e.target.value)} />
          {emailStatus === "checking" && <p className="text-xs text-[var(--warning)] mt-1">확인 중...</p>}
          {emailStatus === "available" && <p className="text-xs text-[var(--green)] mt-1">✅ 사용 가능한 이메일입니다.</p>}
          {emailStatus === "taken" && <p className="text-xs text-[var(--danger)] mt-1">❌ 이미 사용 중인 이메일입니다.</p>}
        </div>

        {/* 비밀번호 */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">비밀번호 *</label>
            <input className="input-field" type="password" placeholder="8자 이상" value={form.password} onChange={e => set("password", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">비밀번호 확인 *</label>
            <input className="input-field" type="password" placeholder="다시 입력" value={form.passwordConfirm} onChange={e => set("passwordConfirm", e.target.value)} />
          </div>
        </div>

        {/* 이름 */}
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">이름 *</label>
          <input className="input-field" placeholder="홍길동" value={form.name} onChange={e => set("name", e.target.value)} />
        </div>

        {/* 회원 유형 - 지원자(candidate) 또는 인사담당자(recruiter) */}
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">회원 유형 *</label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => set("role", "candidate")}
              className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${
                form.role === "candidate"
                  ? "border-[var(--cyan)] bg-[rgba(0,212,255,0.1)] text-[var(--cyan)]"
                  : "border-[var(--glass-border)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]"
              }`}
            >
              🎯 지원자
            </button>
            <button
              type="button"
              onClick={() => set("role", "recruiter")}
              className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${
                form.role === "recruiter"
                  ? "border-[var(--cyan)] bg-[rgba(0,212,255,0.1)] text-[var(--cyan)]"
                  : "border-[var(--glass-border)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]"
              }`}
            >
              👔 인사담당자
            </button>
          </div>
        </div>

        {/* 추가 정보 */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">생년월일</label>
            <input className="input-field" type="date" value={form.birth_date} onChange={e => set("birth_date", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">성별</label>
            <select className="input-field" value={form.gender} onChange={e => set("gender", e.target.value)}>
              <option value="">선택 안 함</option>
              <option value="male">남성</option>
              <option value="female">여성</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">주소</label>
          <input className="input-field" placeholder="서울시 강남구..." value={form.address} onChange={e => set("address", e.target.value)} />
        </div>

        {/* 전화번호 */}
        <div>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">전화번호</label>
          <input className="input-field" type="tel" placeholder="010-1234-5678" value={form.phone} onChange={e => set("phone", e.target.value)} />
        </div>

        {error && <p className="text-sm text-[var(--danger)] bg-[rgba(255,82,82,0.1)] p-3 rounded-lg">{error}</p>}

        <button onClick={handleSubmit} disabled={loading} className="btn-gradient w-full text-base py-3">
          {loading ? "처리 중..." : "회원가입"}
        </button>

        <p className="text-center text-sm text-[var(--text-secondary)]">
          이미 계정이 있으신가요?{" "}
          <button onClick={onSwitch} className="text-[var(--cyan)] hover:underline">로그인</button>
        </p>
      </div>
    </Modal>
  );
}
