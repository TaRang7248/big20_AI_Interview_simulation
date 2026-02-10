"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/common/Header";
import { useAuth } from "@/contexts/AuthContext";
import { authApi } from "@/lib/api";
import { User, Mail, Calendar, MapPin, Phone, Lock, Save, Loader2, CheckCircle2 } from "lucide-react";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const router = useRouter();

  const [form, setForm] = useState({
    name: "", birth_date: "", gender: "", address: "", phone: "",
  });
  const [pwForm, setPwForm] = useState({
    current_password: "", new_password: "", confirm_password: "",
  });
  const [saving, setSaving] = useState(false);
  const [changingPw, setChangingPw] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [pwMessage, setPwMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  /* 유저 데이터 로드 */
  useEffect(() => {
    if (!user) { router.push("/"); return; }
    setForm({
      name: user.name || "",
      birth_date: user.birth_date || "",
      gender: user.gender || "",
      address: user.address || "",
      phone: user.phone || "",
    });
  }, [user, router]);

  /* 프로필 저장 */
  const handleSave = async () => {
    setSaving(true); setMessage(null);
    try {
      await authApi.updateUser(form);
      await refreshUser();
      setMessage({ type: "success", text: "프로필이 저장되었습니다." });
    } catch (e: unknown) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "저장에 실패했습니다." });
    } finally { setSaving(false); }
  };

  /* 비밀번호 변경 */
  const handlePasswordChange = async () => {
    if (pwForm.new_password !== pwForm.confirm_password) {
      setPwMessage({ type: "error", text: "새 비밀번호가 일치하지 않습니다." });
      return;
    }
    if (pwForm.new_password.length < 8) {
      setPwMessage({ type: "error", text: "비밀번호는 8자 이상이어야 합니다." });
      return;
    }
    setChangingPw(true); setPwMessage(null);
    try {
      await authApi.updateUser({
        current_password: pwForm.current_password,
        new_password: pwForm.new_password,
      });
      setPwMessage({ type: "success", text: "비밀번호가 변경되었습니다." });
      setPwForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (e: unknown) {
      setPwMessage({ type: "error", text: e instanceof Error ? e.message : "비밀번호 변경 실패" });
    } finally { setChangingPw(false); }
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460]">
      <Header />
      <main className="max-w-2xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-bold text-white mb-8">👤 프로필 설정</h1>

        {/* 기본 정보 */}
        <section className="glass-card rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
            <User size={18} className="text-cyan-400" /> 기본 정보
          </h2>

          <div className="space-y-4">
            {/* 이메일 (읽기전용) */}
            <div>
              <label className="text-sm text-gray-400 mb-1 flex items-center gap-1"><Mail size={14} /> 이메일</label>
              <input type="email" value={user.email || ""} disabled
                className="input-field opacity-60 cursor-not-allowed" />
            </div>

            {/* 이름 */}
            <div>
              <label className="text-sm text-gray-400 mb-1 flex items-center gap-1"><User size={14} /> 이름</label>
              <input type="text" value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                className="input-field" placeholder="이름" />
            </div>

            {/* 생년월일 */}
            <div>
              <label className="text-sm text-gray-400 mb-1 flex items-center gap-1"><Calendar size={14} /> 생년월일</label>
              <input type="date" value={form.birth_date}
                onChange={e => setForm(p => ({ ...p, birth_date: e.target.value }))}
                className="input-field" />
            </div>

            {/* 성별 */}
            <div>
              <label className="text-sm text-gray-400 mb-1">성별</label>
              <div className="flex gap-3 mt-1">
                {["male", "female", "other"].map(g => (
                  <button key={g} onClick={() => setForm(p => ({ ...p, gender: g }))}
                    className={`px-4 py-2 rounded-lg text-sm border transition ${
                      form.gender === g
                        ? "border-cyan-500 bg-cyan-500/10 text-cyan-400"
                        : "border-gray-600 text-gray-400 hover:border-gray-400"
                    }`}>
                    {g === "male" ? "남성" : g === "female" ? "여성" : "기타"}
                  </button>
                ))}
              </div>
            </div>

            {/* 주소 */}
            <div>
              <label className="text-sm text-gray-400 mb-1 flex items-center gap-1"><MapPin size={14} /> 주소</label>
              <input type="text" value={form.address}
                onChange={e => setForm(p => ({ ...p, address: e.target.value }))}
                className="input-field" placeholder="주소" />
            </div>

            {/* 전화번호 */}
            <div>
              <label className="text-sm text-gray-400 mb-1 flex items-center gap-1"><Phone size={14} /> 전화번호</label>
              <input type="tel" value={form.phone}
                onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
                className="input-field" placeholder="010-1234-5678" />
            </div>
          </div>

          {message && (
            <div className={`mt-4 p-3 rounded-lg text-sm ${
              message.type === "success" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
            }`}>
              {message.text}
            </div>
          )}

          <button onClick={handleSave} disabled={saving}
            className="mt-5 w-full btn-gradient flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold disabled:opacity-50">
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            저장
          </button>
        </section>

        {/* 비밀번호 변경 */}
        <section className="glass-card rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
            <Lock size={18} className="text-cyan-400" /> 비밀번호 변경
          </h2>

          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 mb-1">현재 비밀번호</label>
              <input type="password" value={pwForm.current_password}
                onChange={e => setPwForm(p => ({ ...p, current_password: e.target.value }))}
                className="input-field" placeholder="현재 비밀번호" />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1">새 비밀번호</label>
              <input type="password" value={pwForm.new_password}
                onChange={e => setPwForm(p => ({ ...p, new_password: e.target.value }))}
                className="input-field" placeholder="8자 이상" />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1">비밀번호 확인</label>
              <input type="password" value={pwForm.confirm_password}
                onChange={e => setPwForm(p => ({ ...p, confirm_password: e.target.value }))}
                className="input-field" placeholder="새 비밀번호 확인" />
            </div>
          </div>

          {pwMessage && (
            <div className={`mt-4 p-3 rounded-lg text-sm ${
              pwMessage.type === "success" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
            }`}>
              {pwMessage.text}
            </div>
          )}

          <button onClick={handlePasswordChange} disabled={changingPw || !pwForm.current_password || !pwForm.new_password}
            className="mt-5 w-full py-3 rounded-xl text-sm font-semibold bg-[#2a2a4a] text-white hover:bg-[#3a3a5a] border border-gray-600 transition disabled:opacity-50 flex items-center justify-center gap-2">
            {changingPw ? <Loader2 size={16} className="animate-spin" /> : <Lock size={16} />}
            비밀번호 변경
          </button>
        </section>
      </main>
    </div>
  );
}
