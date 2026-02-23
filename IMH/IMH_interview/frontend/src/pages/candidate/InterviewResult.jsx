import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { interviewsApi } from '../../services/api'
import {
    Chart as ChartJS,
    RadialLinearScale, PointElement, LineElement,
    Filler, Tooltip, Legend,
} from 'chart.js'
import { Radar } from 'react-chartjs-2'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

export default function InterviewResult() {
    const { interviewId } = useParams()
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        interviewsApi.getResult(interviewId)
            .then(res => setData(res.data))
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [interviewId])

    if (loading) return <div className="loading"><div className="spinner" />결과 불러오는 중...</div>
    if (!data?.evaluation) {
        return (
            <div className="empty-state">
                <div className="empty-icon">⏳</div>
                <p>아직 평가 결과가 없습니다. 면접을 완료해 주세요.</p>
                <Link to="/candidate/home" className="btn btn-secondary" style={{ marginTop: 16, display: 'inline-flex' }}>
                    내 면접 기록으로
                </Link>
            </div>
        )
    }

    const { evaluation } = data
    const scores = evaluation.scores
    const isPass = evaluation.decision === 'PASS'

    const radarData = {
        labels: ['기술 역량', '문제 해결', '의사소통', '비언어적'],
        datasets: [{
            label: '점수',
            data: [scores.tech, scores.problem, scores.comm, scores.nonverbal],
            backgroundColor: 'rgba(99, 102, 241, 0.2)',
            borderColor: '#6366F1',
            borderWidth: 2,
            pointBackgroundColor: '#6366F1',
        }]
    }

    const radarOptions = {
        plugins: { legend: { display: false } },
        scales: {
            r: {
                min: 0, max: 100,
                ticks: { color: '#6B7280', font: { size: 10 } },
                grid: { color: 'rgba(255,255,255,0.06)' },
                pointLabels: { color: '#9CA3AF', font: { size: 12 } },
                angleLines: { color: 'rgba(255,255,255,0.06)' },
            }
        }
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">면접 결과</h1>
                <p className="page-subtitle">{data.job_title}</p>
            </div>

            <div style={{ maxWidth: 720 }}>
                {/* Decision card */}
                <div className={`result-decision ${isPass ? 'pass' : 'fail'}`}>
                    <div className="decision-emoji">{isPass ? '🎉' : '😔'}</div>
                    <div className={`decision-text ${isPass ? 'pass' : 'fail'}`}>
                        {isPass ? '합격' : '불합격'}
                    </div>
                    <p style={{ color: 'var(--text-secondary)', marginTop: 12, lineHeight: 1.8 }}>
                        {evaluation.summary}
                    </p>
                </div>

                {/* Score breakdown */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
                    <div className="score-grid">
                        <div className="score-item">
                            <div className="score-value">{scores.tech?.toFixed(1)}</div>
                            <div className="score-name">기술 역량</div>
                        </div>
                        <div className="score-item">
                            <div className="score-value">{scores.problem?.toFixed(1)}</div>
                            <div className="score-name">문제 해결</div>
                        </div>
                        <div className="score-item">
                            <div className="score-value">{scores.comm?.toFixed(1)}</div>
                            <div className="score-name">의사소통</div>
                        </div>
                        <div className="score-item">
                            <div className="score-value">{scores.nonverbal?.toFixed(1)}</div>
                            <div className="score-name">비언어적</div>
                        </div>
                    </div>

                    <div className="chart-container">
                        <div className="chart-title">역량 레이더</div>
                        <Radar data={radarData} options={radarOptions} />
                    </div>
                </div>

                {/* Actions */}
                <div className="flex gap-4">
                    <Link to="/candidate/home" className="btn btn-secondary flex-1" style={{ justifyContent: 'center' }}>
                        ← 내 면접 기록
                    </Link>
                    <Link to="/candidate/postings" className="btn btn-primary flex-1" style={{ justifyContent: 'center' }}>
                        다른 공고 보기 →
                    </Link>
                </div>
            </div>
        </div>
    )
}
