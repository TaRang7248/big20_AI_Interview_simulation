import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LoginPage_yyr() {
    const nav = useNavigate();
    const [mode, setMode] = useState("login");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [passwordConfirm, setPasswordConfirm] = useState("");
    const [name, setName] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async () => {
        setError("");

        // 빈 값 체크
        if (!email || !password) {
            setError("이메일과 비밀번호를 입력해주세요.");
            return;
        }
        if (mode === "signup" && password !== passwordConfirm) {
            setError("비밀번호가 일치하지 않아요.");
            return;
        }

        setLoading(true);
        try {
            const url = mode === "login"
                ? "http://localhost:8001/auth/login"
                : "http://localhost:8001/auth/signup";

            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password, name }),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || "오류가 발생했어요.");
                return;
            }

            // 로그인 성공 → localStorage에 저장
            localStorage.setItem("user_id", data.user_id);
            localStorage.setItem("email", data.email);
            localStorage.setItem("role", data.role || "user");
            localStorage.setItem("auth_token", "loggedin");

            if (data.role === "admin") {
                nav("/admin");
            } else {
                nav("/user/home");
            }

        } catch (e) {
            setError("서버 연결에 실패했어요. 백엔드가 켜져있는지 확인해주세요.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
            <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
                <h1 className="text-2xl font-extrabold text-gray-900 mb-2">AI Interview</h1>
                <p className="text-sm text-gray-500 mb-6">
                    {mode === "login" ? "로그인" : "회원가입"}
                </p>

                <div className="flex gap-2 mb-6">
                    <button
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-bold border ${mode === "login" ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200"}`}
                        onClick={() => { setMode("login"); setError(""); }}
                    >로그인</button>
                    <button
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-bold border ${mode === "signup" ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200"}`}
                        onClick={() => { setMode("signup"); setError(""); }}
                    >회원가입</button>
                </div>

                <div className="space-y-3">
                    {mode === "signup" && (
                        <input
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                            placeholder="이름"
                            value={name}
                            onChange={e => setName(e.target.value)}
                        />
                    )}
                    <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                        placeholder="이메일"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                    />
                    <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                        placeholder="비밀번호"
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                    />
                    {mode === "signup" && (
                        <input
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                            placeholder="비밀번호 확인"
                            type="password"
                            value={passwordConfirm}
                            onChange={e => setPasswordConfirm(e.target.value)}
                        />
                    )}

                    {/* 에러 메시지 */}
                    {error && (
                        <p className="text-sm text-red-500 font-semibold">{error}</p>
                    )}

                    <button
                        onClick={handleSubmit}
                        disabled={loading}
                        className="w-full mt-2 px-4 py-3 rounded-xl bg-blue-600 text-white font-extrabold hover:bg-blue-700 transition disabled:opacity-50"
                    >
                        {loading ? "처리 중..." : mode === "login" ? "로그인하고 시작" : "회원가입하고 시작"}
                    </button>

                    {/* 개발용 관리자 버튼 유지 */}
                    <button
                        onClick={() => {
                            localStorage.setItem("role", "admin");
                            nav("/admin");
                        }}
                        className="w-full mt-2 px-4 py-3 rounded-xl bg-gray-900 text-white font-extrabold hover:bg-black transition"
                    >
                        (개발용) 관리자로 시작
                    </button>
                </div>
            </div>
        </div>
    );
}