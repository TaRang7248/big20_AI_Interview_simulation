import React from "react";
import { Link } from "react-router-dom";

export default function AdminPage_yyr() {
    const sampleThreadId = "my_new_interview_01";

    return (
        <div className="min-h-screen bg-gray-100 p-6">
            <div className="max-w-4xl mx-auto space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-extrabold text-gray-900">🛠 Admin Dashboard</h1>
                        <p className="text-sm text-gray-500 mt-1">관리자 전용 페이지 (뼈대)</p>
                    </div>

                    <Link
                        to="/interview"
                        className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-bold hover:bg-black"
                    >
                        면접 화면으로
                    </Link>
                </div>

                <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 space-y-3">
                    <h2 className="text-lg font-bold text-gray-900">빠른 링크</h2>

                    <Link
                        to={`/admin/results/${sampleThreadId}`}
                        className="inline-block px-4 py-2 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-700"
                    >
                        샘플 결과 보기
                    </Link>

                    <div className="text-xs text-gray-500">
                        나중에 여기에 “최근 thread 목록”, “검색”, “통계”, “사용자별 히스토리”를 붙이면 됨.
                    </div>
                </div>
            </div>
        </div>
    );
}
