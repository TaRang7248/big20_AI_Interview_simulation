// frontend/src/components/ReportModal.jsx


import React from 'react';
import { 
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
  Tooltip
} from 'recharts';
import { X, Award, CheckCircle } from 'lucide-react'; // 아이콘

const ReportModal = ({ isOpen, onClose, reportData }) => {
  if (!isOpen || !reportData) return null;

  // 1. 차트용 데이터 변환 (백엔드 details -> 차트용 data)
  // details 배열이 없는 경우를 대비해 빈 배열 처리
  const details = reportData.details || [];
  
  const chartData = details.map(item => ({
    subject: item.category,
    A: item.score,
    fullMark: 100,
  }));

  // 2. 점수별 색상 함수
  const getScoreColor = (score) => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-yellow-400";
    return "bg-red-500";
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto flex flex-col">
        
        {/* 헤더 */}
        <div className="flex justify-between items-center p-6 border-b bg-gray-50 rounded-t-2xl">
          <div>
            <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
              <Award className="text-blue-600" /> AI 면접 분석 리포트
            </h2>
            <p className="text-sm text-gray-500 mt-1">면접관(AI)이 분석한 지원자의 역량 상세 결과입니다.</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded-full transition">
            <X className="w-6 h-6 text-gray-600" />
          </button>
        </div>

        {/* 본문 (2단 레이아웃) */}
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8 flex-grow">
          
          {/* 왼쪽: 종합 점수 & 레이더 차트 */}
          <div className="flex flex-col items-center justify-center space-y-6 bg-blue-50/50 rounded-xl p-4">
            <div className="text-center">
              <span className="text-sm font-bold text-gray-500 uppercase tracking-wider">Total Score</span>
              <div className="text-7xl font-extrabold text-blue-600 mt-2 tracking-tighter">
                {reportData.total_score}<span className="text-2xl text-gray-400 font-normal">/100</span>
              </div>
            </div>

            {/* 육각형 레이더 차트 */}
            <div className="w-full h-72">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="75%" data={chartData}>
                    <PolarGrid stroke="#e5e7eb" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#4b5563', fontSize: 13, fontWeight: 600 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar
                      name="내 점수"
                      dataKey="A"
                      stroke="#2563eb"
                      strokeWidth={3}
                      fill="#3b82f6"
                      fillOpacity={0.5}
                    />
                    <Tooltip 
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400">데이터 부족</div>
              )}
            </div>
          </div>

          {/* 오른쪽: 상세 피드백 */}
          <div className="space-y-6 overflow-y-auto pr-2 custom-scrollbar">
            {/* 총평 박스 */}
            <div className="bg-white p-5 rounded-xl border border-blue-100 shadow-sm">
              <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center">
                📝 AI 총평
              </h3>
              <p className="text-gray-700 leading-relaxed text-sm whitespace-pre-line">
                {reportData.feedback_summary}
              </p>
            </div>

            {/* 항목별 점수 카드 */}
            <div className="space-y-3">
              <h3 className="font-bold text-gray-800 text-sm uppercase tracking-wide text-opacity-70">상세 분석</h3>
              {details.map((item, idx) => (
                <div key={idx} className="bg-gray-50 p-4 rounded-xl border border-gray-100 hover:border-blue-200 transition-colors">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-gray-800 flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-blue-500" />
                      {item.category}
                    </span>
                    <span className={`px-2 py-1 rounded-md text-xs font-bold text-white ${getScoreColor(item.score)}`}>
                      {item.score}점
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 pl-6 leading-relaxed">{item.comment}</p>
                </div>
              ))}
            </div>
          </div>

        </div>
        
        {/* 푸터 */}
        <div className="p-6 border-t bg-gray-50 rounded-b-2xl flex justify-end">
          <button 
            onClick={onClose}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-blue-500/30 transition transform hover:-translate-y-0.5 active:translate-y-0"
          >
            확인 완료
          </button>
        </div>

      </div>
    </div>
  );
};

export default ReportModal;