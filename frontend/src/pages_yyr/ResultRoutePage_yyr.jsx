// frontend/src/pages_yyr/ResultRoutePage_yyr.jsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import ResultPage_yyr from "./ResultPage_yyr";
import { mockInterviewResults } from "./mockInterviewResults"; // ✅ 추가

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

                const res = await axios.get(`${API_BASE_URL}/report/${threadId}/result`);
                if (!cancelled) setReportData(res.data || null);
            } catch (e) {
                // ✅ API 실패(422 포함) → mock 먼저 사용
                const mock = mockInterviewResults?.[threadId];

                if (!cancelled && mock) {
                    setReportData(mock);
                    setErrorMsg(""); // mock이면 에러 메시지 안 띄움
                } else if (!cancelled) {
                    setErrorMsg("리포트를 불러오지 못했습니다. (API/DB 확인 필요, mock도 없음)");
                }
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
                    <Link to="/interview" className="text-blue-600 font-bold hover:underline">
                        ← 면접 화면으로 돌아가기
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

                    <Link
                        to="/user/home"
                        className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-bold hover:bg-black"
                    >
                        로비로
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

// 두번째
// import React, { useState, useRef } from "react";
// import html2canvas from "html2canvas";
// import { jsPDF } from "jspdf";

// // 면접자 화면에서 '근거(rationale)'를 보여줄지 여부
// const SHOW_RATIONALE_TO_USER = false;

// export default function ResultPage_yyr({ reportData }) {
//     const pdfRef = useRef(null);
//     const [open, setOpen] = useState({
//         hard_skill: false,
//         problem_solving: false,
//         communication: false,
//         attitude: false,
//     });

//     if (!reportData) return null;

//     // ✅ [핵심] 생성 API 형식(report) / 조회 API 형식(result)을 동시에 지원하는 어댑터
//     const isResultShape = reportData.feedback && reportData.radar; // GET /report/{thread_id}/result 쪽 특징

//     const normalized = (() => {
//         if (!isResultShape) {
//             // 생성 API(POST /report/{thread_id})의 report 형식 그대로
//             return {
//                 totalScore: reportData.total_weighted_score,
//                 finalResult: reportData.final_result,
//                 summary: reportData.overall_summary,
//                 detail: {
//                     hard_skill: reportData.hard_skill,
//                     problem_solving: reportData.problem_solving,
//                     communication: reportData.communication,
//                     attitude: reportData.attitude,
//                 },
//             };
//         }

//         // 조회 API(GET /report/{thread_id}/result) 형식 → ResultPage에서 쓰는 형식으로 변환
//         const fb = reportData.feedback || {};
//         return {
//             totalScore: reportData.total_score,
//             finalResult: reportData.final_result,
//             summary: reportData.summary, // overall_summary가 아니라 summary로 내려옴
//             detail: {
//                 hard_skill: fb.hard_skill,
//                 problem_solving: fb.problem_solving,
//                 communication: fb.communication,
//                 attitude: fb.attitude,
//             },
//         };
//     })();

//     const handleSavePDF = async () => {
//         const element = pdfRef.current;
//         if (!element) return;

//         const canvas = await html2canvas(element, { scale: 2 });
//         const imgData = canvas.toDataURL("image/png");

//         const pdf = new jsPDF("p", "mm", "a4");
//         const imgWidth = 210;
//         const imgHeight = (canvas.height * imgWidth) / canvas.width;

//         pdf.addImage(imgData, "PNG", 0, 0, imgWidth, imgHeight);
//         pdf.save("interview_result.pdf");
//     };

//     const items = [
//         ["hard_skill", "기술 역량"],
//         ["problem_solving", "문제 해결"],
//         ["communication", "커뮤니케이션"],
//         ["attitude", "태도"],
//     ];

//     return (
//         <div className="p-6 space-y-6">
//             <div ref={pdfRef}>
//                 <div>
//                     <h1 className="text-2xl font-bold">면접 결과</h1>
//                     <p className="text-gray-500 text-sm">
//                         총점: {Number.isFinite(Number(normalized.totalScore)) ? Number(normalized.totalScore).toFixed(0) : "N/A"} / 100
//                     </p>
//                     <p className="text-gray-500 text-sm">결과: {normalized.finalResult ?? "N/A"}</p>
//                 </div>

//                 <div className="rounded-xl border p-4 bg-gray-50 whitespace-pre-wrap">
//                     {normalized.summary ?? "요약이 없습니다."}
//                 </div>

//                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
//                     {items.map(([key, label]) => {
//                         const d = normalized.detail?.[key];
//                         if (!d) return null;

//                         return (
//                             <div key={key} className="bg-white border rounded-2xl p-4">
//                                 <div className="flex items-center justify-between">
//                                     <h3 className="font-bold text-gray-900">
//                                         {label} <span className="text-gray-400">· {d.score ?? "N/A"}점</span>
//                                     </h3>

//                                     {SHOW_RATIONALE_TO_USER && (
//                                         <button
//                                             className="text-sm font-bold text-gray-700 hover:underline"
//                                             onClick={() =>
//                                                 setOpen((prev) => ({ ...prev, [key]: !prev[key] }))
//                                             }
//                                         >
//                                             {open[key] ? "근거 접기" : "근거 보기"}
//                                         </button>
//                                     )}
//                                 </div>

//                                 <p className="text-gray-700 mt-2 whitespace-pre-wrap">
//                                     {d.feedback ?? "피드백이 없습니다."}
//                                 </p>

//                                 {SHOW_RATIONALE_TO_USER && open[key] && (
//                                     <div className="mt-3 p-3 rounded-xl bg-gray-50 text-sm text-gray-700 whitespace-pre-wrap">
//                                         {d.rationale ?? "근거가 없습니다."}
//                                     </div>
//                                 )}
//                             </div>
//                         );
//                     })}
//                 </div>
//             </div>

//             <div className="flex gap-2">
//                 <button
//                     onClick={handleSavePDF}
//                     className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold"
//                 >
//                     PDF 저장
//                 </button>
//             </div>
//         </div>
//     );
// }

// 첫번째 // ResultRoutePage = URL 기반으로 데이터 가져와서 화면에 꽂아주는 라우팅용 컨테이너라고 보면 됨

// import React, { useEffect, useState } from "react";
// import { useParams, Link } from "react-router-dom";
// import axios from "axios";
// import ResultPage_yyr from "./ResultPage_yyr";

// // 여기 API 주소만 App.jsx랑 동일하게 맞춰줘야 함
// const API_BASE_URL = "http://127.0.0.1:8001";

// export default function ResultRoutePage_yyr() {
//     const { threadId } = useParams();

//     const [reportData, setReportData] = useState(null);
//     const [loading, setLoading] = useState(true);
//     const [errorMsg, setErrorMsg] = useState("");

//     useEffect(() => {
//         let cancelled = false;

//         async function run() {
//             try {
//                 setLoading(true);
//                 setErrorMsg("");

//                 // ✅ 백엔드 응답이 { status, report: {...} } 형태
//                 const res = await axios.post(`${API_BASE_URL}/report/${threadId}`);
//                 const report = res.data?.report;

//                 if (!cancelled) setReportData(report || null);
//             } catch (e) {
//                 if (!cancelled) setErrorMsg("리포트를 불러오지 못했습니다. 백엔드/DB 상태를 확인하세요.");
//             } finally {
//                 if (!cancelled) setLoading(false);
//             }
//         }

//         if (threadId) run();

//         return () => {
//             cancelled = true;
//         };
//     }, [threadId]);

//     if (loading) {
//         return (
//             <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
//                 <div className="text-center">
//                     <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
//                     <p className="text-gray-500">리포트를 불러오는 중...</p>
//                 </div>
//             </div>
//         );
//     }

//     if (errorMsg) {
//         return (
//             <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
//                 <div className="text-center space-y-3">
//                     <p className="text-red-600 font-semibold">{errorMsg}</p>
//                     <Link to="/interview" className="text-blue-600 font-bold hover:underline">
//                         ← 면접 화면으로 돌아가기
//                     </Link>
//                 </div>
//             </div>
//         );
//     }

//     return (
//         <div className="min-h-screen bg-gray-100 py-10 px-4">
//             <div className="max-w-4xl mx-auto space-y-4">
//                 <div className="flex items-center justify-between">
//                     <div>
//                         <h2 className="text-2xl font-bold text-gray-900">📄 면접 결과 (단독 페이지)</h2>
//                         <p className="text-sm text-gray-500 mt-1">thread_id: {threadId}</p>
//                     </div>

//                     <Link to="/interview" className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-bold hover:bg-black">
//                         면접으로
//                     </Link>
//                 </div>

//                 <div className="bg-white rounded-2xl shadow-lg border border-gray-200">
//                     <div className="p-6">
//                         {reportData ? (
//                             <ResultPage_yyr reportData={reportData} />
//                         ) : (
//                             <p className="text-center text-red-500">reportData가 비어있습니다.</p>
//                         )}
//                     </div>
//                 </div>
//             </div>
//         </div>
//     );
// }
