// frontend/src/pages_yyr/AdminResultRoutePage_yyr.jsx
import React, { useEffect } from "react";
import { useParams } from "react-router-dom";

export default function AdminResultRoutePage_yyr() {
    const { threadId } = useParams();

    useEffect(() => {
        const url = `/result.html?thread_id=${encodeURIComponent(threadId)}&from=admin`;
        window.location.replace(url); // ✅ iframe 대신 "페이지 이동"
    }, [threadId]);

    return (
        <div className="min-h-screen flex items-center justify-center">
            관리자 결과 페이지로 이동 중...
        </div>
    );
}

// // frontend/src/pages_yyr/AdminResultRoutePage_yyr.jsx
// import React from "react";
// import { useNavigate, useParams } from "react-router-dom";

// export default function AdminResultRoutePage_yyr() {
//     const nav = useNavigate();
//     const { threadId } = useParams();

//     const src = `/result.html?thread_id=${encodeURIComponent(threadId)}`;

//     return (
//         <div className="min-h-screen bg-slate-50">
//             {/* 상단 네비게이션(관리자용 껍데기) */}
//             <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-2">
//                 <button
//                     onClick={() => nav("/admin")}
//                     className="px-3 py-2 rounded-xl bg-white border font-extrabold"
//                 >
//                     ← 목록으로
//                 </button>

//                 <div className="ml-auto text-xs text-slate-500">
//                     thread_id: <span className="font-bold">{threadId}</span>
//                 </div>
//             </div>

//             {/* 원래 결과 UI를 그대로 임베드 */}
//             <div className="max-w-6xl mx-auto px-4 pb-8">
//                 <div className="max-w-6xl mx-auto px-4 pb-0">
//                     <iframe
//                         title="admin-result"
//                         src={src}
//                         className="w-full"
//                         style={{
//                             height: "calc(100vh - 72px)", // 헤더 높이에 맞춰 조정
//                             border: 0,
//                             display: "block",
//                             background: "transparent",
//                         }}
//                     />
//                 </div>
//             </div>
//         </div>
//     );
// }