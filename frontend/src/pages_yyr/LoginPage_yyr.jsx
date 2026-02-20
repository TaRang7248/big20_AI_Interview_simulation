import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

export default function LoginPage_yyr() {
    const nav = useNavigate();
    const [mode, setMode] = useState("login"); // 'login' | 'signup'

    return (
        <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
            <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
                <h1 className="text-2xl font-extrabold text-gray-900 mb-2">AI Interview</h1>
                <p className="text-sm text-gray-500 mb-6">
                    {mode === "login" ? "로그인" : "회원가입"} (UI 골격)
                </p>

                <div className="flex gap-2 mb-6">
                    <button
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-bold border ${mode === "login"
                            ? "bg-gray-900 text-white border-gray-900"
                            : "bg-white text-gray-700 border-gray-200"
                            }`}
                        onClick={() => setMode("login")}
                    >
                        로그인
                    </button>

                    <button
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-bold border ${mode === "signup"
                            ? "bg-gray-900 text-white border-gray-900"
                            : "bg-white text-gray-700 border-gray-200"
                            }`}
                        onClick={() => setMode("signup")}
                    >
                        회원가입
                    </button>
                </div>

                <div className="space-y-3">
                    <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                        placeholder="이메일"
                    />
                    <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                        placeholder="비밀번호"
                        type="password"
                    />

                    {mode === "signup" && (
                        <input
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
                            placeholder="비밀번호 확인"
                            type="password"
                        />
                    )}

                    {/* ✅ 유저로 시작 */}
                    <button
                        onClick={() => {
                            localStorage.setItem("auth_token", "demo-token");
                            localStorage.setItem("role", "user");
                            nav("/interview");
                        }}
                        className="w-full mt-2 px-4 py-3 rounded-xl bg-blue-600 text-white font-extrabold hover:bg-blue-700 transition"
                    >
                        {mode === "login" ? "로그인하고 시작" : "회원가입하고 시작"}
                    </button>

                    {/* ✅ (개발용) 관리자로 시작 */}
                    <button
                        onClick={() => {
                            localStorage.setItem("auth_token", "demo-token");
                            localStorage.setItem("role", "admin");
                            nav("/admin");
                        }}
                        className="w-full mt-2 px-4 py-3 rounded-xl bg-gray-900 text-white font-extrabold hover:bg-black transition"
                    >
                        (개발용) 관리자로 시작
                    </button>

                    <div className="text-xs text-gray-500 mt-4">
                        지금은 큰 틀(라우팅)만 잡는 단계라 인증은 붙이지 않았어요.
                    </div>

                    <div className="text-xs mt-2">
                        <Link
                            to="/result/my_new_interview_01"
                            className="text-blue-600 font-bold hover:underline"
                        >
                            (개발용) 결과 페이지 바로가기
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}


// import React, { useState } from "react";
// import { useNavigate, Link } from "react-router-dom";

// export default function LoginPage_yyr() {
//     const nav = useNavigate();
//     const [mode, setMode] = useState("login"); // 'login' | 'signup'

//     return (
//         <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
//             <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
//                 <h1 className="text-2xl font-extrabold text-gray-900 mb-2">AI Interview</h1>
//                 <p className="text-sm text-gray-500 mb-6">
//                     {mode === "login" ? "로그인" : "회원가입"} (UI 골격)
//                 </p>

//                 <div className="flex gap-2 mb-6">
//                     <button
//                         className={`flex-1 px-3 py-2 rounded-lg text-sm font-bold border ${mode === "login" ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200"
//                             }`}
//                         onClick={() => setMode("login")}
//                     >
//                         로그인
//                     </button>
//                     <button
//                         className={`flex-1 px-3 py-2 rounded-lg text-sm font-bold border ${mode === "signup" ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200"
//                             }`}
//                         onClick={() => setMode("signup")}
//                     >
//                         회원가입
//                     </button>
//                 </div>

//                 <div className="space-y-3">
//                     <input
//                         className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
//                         placeholder="이메일"
//                     />
//                     <input
//                         className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
//                         placeholder="비밀번호"
//                         type="password"
//                     />

//                     {mode === "signup" && (
//                         <input
//                             className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none"
//                             placeholder="비밀번호 확인"
//                             type="password"
//                         />
//                     )}

//                     {/* ✅ 가짜 로그인: 버튼 누르면 면접 화면으로 이동 */}
//                     <button
//                         onClick={() => {
//                             localStorage.setItem("auth_token", "demo-token");
//                             localStorage.setItem("role", "admin");
//                             nav("/admin");
//                         }}
//                         className="w-full mt-2 px-4 py-3 rounded-xl bg-gray-900 text-white font-extrabold hover:bg-black transition"
//                     >
//                         (개발용) 관리자로 시작
//                     </button>


//                     <div className="text-xs text-gray-500 mt-4">
//                         지금은 큰 틀(라우팅)만 잡는 단계라 인증은 붙이지 않았어요.
//                     </div>

//                     <div className="text-xs mt-2">
//                         <Link to="/result/my_new_interview_01" className="text-blue-600 font-bold hover:underline">
//                             (개발용) 결과 페이지 바로가기
//                         </Link>
//                     </div>
//                 </div>
//             </div>
//         </div >
//     );
// }
