// import React from "react";

// export default function ResultPage({ reportData }) {
//   if (!reportData) return null;

//   return (
//     <div className="p-6">
//       {/* 지금은 “진짜 결과 UI”로 옮기기 전, 자리만 잡기 */}
//       <div className="mb-4">
//         <h1 className="text-2xl font-bold">면접 결과</h1>
//         <p className="text-gray-500 text-sm">총점: {reportData.total_score} / 100</p>
//       </div>

//       <div className="rounded-xl border p-4 bg-gray-50 whitespace-pre-wrap">
//         {reportData.feedback_summary}
//       </div>

//       {/* TODO: 여기부터 네 result.html의 카드/레이더 UI를 JSX로 옮겨 붙이면 됨 */}
//     </div>
//   );
// }

// import React from "react";

// export default function ResultPage_yyr({ reportData }) {
//   if (!reportData) return null;

//   return (
//     <div className="p-6">
//       <div className="mb-4">
//         <h1 className="text-2xl font-bold">면접 결과</h1>

//         <p className="text-gray-500 text-sm">
//           총점: {reportData.total_weighted_score?.toFixed(0)} / 100
//         </p>

//         <p className="text-gray-500 text-sm">
//           결과: {reportData.final_result}
//         </p>
//       </div>

//       <div className="rounded-xl border p-4 bg-gray-50 whitespace-pre-wrap">
//         {reportData.overall_summary}
//       </div>

//       {/* 디버그용(필요하면 잠깐만 켜기) */}
//       {/* <pre className="bg-gray-800 text-gray-100 p-4 rounded-xl text-xs overflow-x-auto mt-4">
//         {JSON.stringify(reportData, null, 2)}
//       </pre> */}
//     </div>
//   );
// }

import React, { useState, useRef } from "react"; // yyr추가
import html2canvas from "html2canvas"; // yyr 추가
import { jsPDF } from "jspdf"; // yyr 추가

// 면접자 화면에서 '근거(rationale)'를 보여줄지 여부
// false: 숨김(추천) / true: 노출
const SHOW_RATIONALE_TO_USER = false;

export default function ResultPage_yyr({ reportData }) {
  const pdfRef = useRef(null);
  const [open, setOpen] = useState({
    hard_skill: false,
    problem_solving: false,
    communication: false,
    attitude: false,
  });

  if (!reportData) return null;

  const handleSavePDF = async () => {
    const element = pdfRef.current;
    if (!element) return;

    const canvas = await html2canvas(element, { scale: 2 });
    const imgData = canvas.toDataURL("image/png");

    const pdf = new jsPDF("p", "mm", "a4");
    const imgWidth = 210; // A4 너비(mm)
    const imgHeight = (canvas.height * imgWidth) / canvas.width;

    pdf.addImage(imgData, "PNG", 0, 0, imgWidth, imgHeight);
    pdf.save("interview_result.pdf");
  };

  const items = [
    ["hard_skill", "기술 역량"],
    ["problem_solving", "문제 해결"],
    ["communication", "커뮤니케이션"],
    ["attitude", "태도"],
  ];

  return (
    <div className="p-6 space-y-6">
      <div ref={pdfRef}>
        <div>
          <h1 className="text-2xl font-bold">면접 결과</h1>
          <p className="text-gray-500 text-sm">
            총점: {reportData.total_weighted_score?.toFixed(0)} / 100
          </p>
          <p className="text-gray-500 text-sm">결과: {reportData.final_result}</p>
        </div>

        <div className="rounded-xl border p-4 bg-gray-50 whitespace-pre-wrap">
          {reportData.overall_summary}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map(([key, label]) => {
            const d = reportData[key];
            if (!d) return null;

            return (
              <div key={key} className="bg-white border rounded-2xl p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-gray-900">
                    {label} <span className="text-gray-400">· {d.score}점</span>
                  </h3>

                  {SHOW_RATIONALE_TO_USER && (
                    <button
                      className="text-sm font-bold text-gray-700 hover:underline"
                      onClick={() =>
                        setOpen((prev) => ({ ...prev, [key]: !prev[key] }))
                      }
                    >
                      {open[key] ? "근거 접기" : "근거 보기"}
                    </button>
                  )}
                </div>

                <p className="text-gray-700 mt-2 whitespace-pre-wrap">
                  {d.feedback}
                </p>

                {SHOW_RATIONALE_TO_USER && open[key] && (
                  <div className="mt-3 p-3 rounded-xl bg-gray-50 text-sm text-gray-700 whitespace-pre-wrap">
                    {d.rationale}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleSavePDF}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold"
        >
          PDF 저장
        </button>
      </div>
    </div>
  );
}
