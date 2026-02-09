"use client";
import { useState } from "react";
import { authApi } from "@/lib/api";
import Modal from "@/components/common/Modal";

interface Props { open: boolean; onClose: () => void; onBack: () => void; }

export default function ForgotPasswordModal({ open, onClose, onBack }: Props) {
  const [step, setStep] = useState<1 | 2>(1);
  const [form, setForm] = useState({ email: "", name: "", birth_date: "", new_password: "", confirm: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const handleVerify = async () => {
    setError("");
    if (!form.email || !form.name || !form.birth_date) { setError("모든 항목을 입력해주세요."); return; }
    setLoading(true);
    try {
      await authApi.verifyIdentity({ email: form.email, name: form.name, birth_date: form.birth_date });
      setStep(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "본인 확인 실패");
    } finally { setLoading(false); }
  };

  const handleReset = async () => {
    setError("");
    if (form.new_password.length < 8) { setError("비밀번호는 8자 이상이어야 합니다."); return; }
    if (form.new_password !== form.confirm) { setError("비밀번호가 일치하지 않습니다."); return; }
    setLoading(true);
    try {
      await authApi.resetPassword({ email: form.email, new_password: form.new_password });
      alert("비밀번호가 변경되었습니다. 로그인 해주세요.");
      onBack();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "비밀번호 재설정 실패");
    } finally { setLoading(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title={step === 1 ? "비밀번호 찾기" : "비밀번호 재설정"}>
      <div className="space-y-4">
        {step === 1 ? (
          <>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">이메일</label>
              <input className="input-field" type="email" value={form.email} onChange={e => set("email", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">이름</label>
              <input className="input-field" value={form.name} onChange={e => set("name", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">생년월일</label>
              <input className="input-field" type="date" value={form.birth_date} onChange={e => set("birth_date", e.target.value)} />
            </div>
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <button onClick={handleVerify} disabled={loading} className="btn-gradient w-full py-3">
              {loading ? "확인 중..." : "본인 확인"}
            </button>
          </>
        ) : (
          <>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">새 비밀번호</label>
              <input className="input-field" type="password" placeholder="8자 이상" value={form.new_password} onChange={e => set("new_password", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">비밀번호 확인</label>
              <input className="input-field" type="password" value={form.confirm} onChange={e => set("confirm", e.target.value)} />
            </div>
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <button onClick={handleReset} disabled={loading} className="btn-gradient w-full py-3">
              {loading ? "처리 중..." : "비밀번호 재설정"}
            </button>
          </>
        )}
        <button onClick={onBack} className="w-full text-sm text-[var(--text-secondary)] hover:text-[var(--cyan)]">
          ← 로그인으로 돌아가기
        </button>
      </div>
    </Modal>
  );
}
