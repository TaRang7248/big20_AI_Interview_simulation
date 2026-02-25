// frontend/src/pages_yyr/AdminResultRoutePage_yyr.jsx
import React, { useEffect } from "react";
import { useParams } from "react-router-dom";

export default function AdminResultRoutePage_yyr() {
    const { threadId } = useParams();

    useEffect(() => {
        // ✅ 관리자 결과는 레이더(result.html)로 연결
        // 기존 result.html이 thread_id든 session_id든 뭐를 받는지에 맞춰 파라미터만 맞추면 됨
        const url = `/result.html?thread_id=${encodeURIComponent(threadId)}`;
        window.location.replace(url);
    }, [threadId]);

    return (
        <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
            <p className="text-gray-600 font-semibold">관리자 결과 페이지로 이동 중...</p>
        </div>
    );
}