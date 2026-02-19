// ResultRoutePage = URL 기반으로 데이터 가져와서 화면에 꽂아주는 라우팅용 컨테이너라고 보면 됨

import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import ResultPage_yyr from "./ResultPage_yyr";

// 여기 API 주소만 App.jsx랑 동일하게 맞춰줘야 함
const API_BASE_URL = "http://127.0.0.1:8001";

export default function ResultRoutePage_yyr() {
    const { threadId } = useParams();

    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [errorMsg, setErrorMsg] = useState("");

    useEffect(() => {
        let cancelled = false;

        async function run() {
            try {
                setLoading(true);
                setErrorMsg("");

                // ✅ 백엔드 응답이 { status, report: {...} } 형태
                const res = await axios.post(`${API_BASE_URL}/report/${threadId}`);
                const report = res.data?.report;

                if (!cancelled) setReportData(report || null);
            } catch (e) {
                if (!cancelled) setErrorMsg("리포트를 불러오지 못했습니다. 백엔드/DB 상태를 확인하세요.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        if (threadId) run();

        return () => {
            cancelled = true;
        };
    }, [threadId]);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p className="text-gray-500">리포트를 불러오는 중...</p>
                </div>
            </div>
        );
    }

    if (errorMsg) {
        return (
            <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
                <div className="text-center space-y-3">
                    <p className="text-red-600 font-semibold">{errorMsg}</p>
                    <Link to="/" className="text-blue-600 font-bold hover:underline">
                        ← 메인으로 돌아가기
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-100 py-10 px-4">
            <div className="max-w-4xl mx-auto space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold text-gray-900">📄 면접 결과 (단독 페이지)</h2>
                        <p className="text-sm text-gray-500 mt-1">thread_id: {threadId}</p>
                    </div>

                    <Link to="/" className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-bold hover:bg-black">
                        메인으로
                    </Link>
                </div>

                <div className="bg-white rounded-2xl shadow-lg border border-gray-200">
                    <div className="p-6">
                        {reportData ? (
                            <ResultPage_yyr reportData={reportData} />
                        ) : (
                            <p className="text-center text-red-500">reportData가 비어있습니다.</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
