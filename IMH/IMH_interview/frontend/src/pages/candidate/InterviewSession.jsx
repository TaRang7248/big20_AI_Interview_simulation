import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../services/api'

const PHASES = ['자기소개', '지원동기', '직무역량', '경험/사례', '문제해결', '마무리']

function Timer({ startTime }) {
    const [elapsed, setElapsed] = useState(0)

    useEffect(() => {
        const interval = setInterval(() => {
            setElapsed(Math.floor((Date.now() - startTime) / 1000))
        }, 1000)
        return () => clearInterval(interval)
    }, [startTime])

    const mins = Math.floor(elapsed / 60).toString().padStart(2, '0')
    const secs = (elapsed % 60).toString().padStart(2, '0')
    return <span>{mins}:{secs}</span>
}

export default function InterviewSession() {
    const { interviewId } = useParams()
    const navigate = useNavigate()
    const chatEndRef = useRef()
    const [session, setSession] = useState(null)
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(true)
    const [sending, setSending] = useState(false)
    const [isDone, setIsDone] = useState(false)
    const [startTime] = useState(Date.now())
    const videoRef = useRef()
    const [camStream, setCamStream] = useState(null)

    useEffect(() => {
        async function init() {
            try {
                const [sessionRes, chatRes] = await Promise.all([
                    interviewsApi.get(interviewId),
                    interviewsApi.getChat(interviewId),
                ])
                setSession(sessionRes.data)
                setMessages(chatRes.data)
                if (['COMPLETED', 'EVALUATED'].includes(sessionRes.data.status)) {
                    setIsDone(true)
                }
            } catch {
                navigate('/candidate/home')
            } finally {
                setLoading(false)
            }
        }
        init()

        // Start camera
        navigator.mediaDevices.getUserMedia({ video: true, audio: true })
            .then(stream => {
                setCamStream(stream)
                if (videoRef.current) videoRef.current.srcObject = stream
            })
            .catch(() => { })

        return () => {
            setCamStream(s => {
                if (s) s.getTracks().forEach(t => t.stop())
                return null
            })
        }
    }, [interviewId])

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    async function handleSend() {
        if (!input.trim() || sending || isDone) return
        const userMsg = input.trim()
        setInput('')
        setSending(true)

        setMessages(m => [...m, {
            role: 'user',
            content: userMsg,
            phase: session?.current_phase,
            created_at: new Date().toISOString(),
        }])

        try {
            const res = await interviewsApi.sendChat(interviewId, userMsg)
            const { ai_message, status, is_done, current_phase } = res.data

            setMessages(m => [...m, {
                role: 'ai',
                content: ai_message,
                phase: current_phase,
                created_at: new Date().toISOString(),
            }])

            setSession(s => ({ ...s, status, current_phase }))

            if (is_done) {
                setIsDone(true)
                if (camStream) camStream.getTracks().forEach(t => t.stop())
            }
        } catch (err) {
            setMessages(m => [...m, {
                role: 'system',
                content: '오류가 발생했습니다. 다시 시도해 주세요.',
                created_at: new Date().toISOString(),
            }])
        } finally {
            setSending(false)
        }
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            handleSend()
        }
    }

    if (loading) {
        return (
            <div className="loading" style={{ height: '100vh' }}>
                <div className="spinner" />면접 준비 중...
            </div>
        )
    }

    const phaseIdx = session?.phase_index ?? 0

    return (
        <div className="interview-layout">
            {/* Header */}
            <header className="interview-header">
                <div className="flex items-center gap-4">
                    <span style={{
                        fontWeight: 800,
                        fontSize: 18,
                        background: 'var(--accent-gradient)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                    }}>
                        IMH 면접
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                        {session?.job_title || '채용 면접'}
                    </span>
                </div>
                <div className="flex items-center gap-4">
                    <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                        경과: <Timer startTime={startTime} />
                    </div>
                    <span className={`badge ${isDone ? 'badge-completed' : 'badge-progress'}`}>
                        {isDone ? '완료' : '진행중'}
                    </span>
                </div>
            </header>

            {/* AI Panel */}
            <aside className="interview-ai-panel">
                <div className="ai-face">🤖</div>

                <div style={{ width: '100%', textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>현재 면접 단계</div>
                    <div style={{
                        fontSize: 16, fontWeight: 700,
                        color: 'var(--accent-1)',
                    }}>
                        {session?.current_phase || PHASES[0]}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {phaseIdx + 1} / {PHASES.length}
                    </div>
                </div>

                {/* Cam */}
                <div className="cam-panel" style={{ width: '100%', height: 160 }}>
                    {camStream ? (
                        <video
                            ref={videoRef}
                            autoPlay
                            muted
                            style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
                        />
                    ) : (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
                            📷 카메라 없음
                        </div>
                    )}
                </div>
            </aside>

            {/* Chat area */}
            <div className="interview-chat">
                <div className="chat-container" style={{ flex: 1, overflow: 'auto' }}>
                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}
                        >
                            {msg.role !== 'system' && (
                                <div className="chat-label" style={{ marginLeft: msg.role === 'user' ? 0 : 4, marginRight: msg.role === 'user' ? 4 : 0 }}>
                                    {msg.role === 'ai' ? '🤖 AI 면접관' : '🙋 나'}
                                    {msg.phase && <span style={{ marginLeft: 6, fontSize: 9, color: 'var(--accent-1)' }}>[{msg.phase}]</span>}
                                </div>
                            )}
                            <div className={`chat-bubble ${msg.role}`}>
                                {msg.content}
                            </div>
                        </div>
                    ))}
                    {sending && (
                        <div style={{ alignSelf: 'flex-start' }}>
                            <div className="chat-bubble ai" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                                답변 분석 중...
                            </div>
                        </div>
                    )}
                    <div ref={chatEndRef} />
                </div>

                {/* Input */}
                {!isDone ? (
                    <div className="chat-input-area">
                        <textarea
                            className="chat-textarea"
                            placeholder="답변을 입력하세요... (Ctrl+Enter로 전송)"
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            disabled={sending}
                        />
                        <div className="flex justify-between items-center">
                            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                Ctrl+Enter로 전송
                            </span>
                            <button
                                id="send-answer"
                                className="btn btn-primary"
                                onClick={handleSend}
                                disabled={!input.trim() || sending}
                            >
                                답변 완료 ➤
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="chat-input-area" style={{ textAlign: 'center' }}>
                        <div className="alert alert-success" style={{ margin: 0 }}>
                            🎉 면접이 종료되었습니다.
                        </div>
                        <button
                            className="btn btn-primary btn-full"
                            style={{ marginTop: 12 }}
                            onClick={() => navigate(`/candidate/result/${interviewId}`)}
                        >
                            결과 확인하기 →
                        </button>
                    </div>
                )}
            </div>

            {/* Side info */}
            <aside className="interview-sidebar">
                <div className="timer-display">
                    <div className="timer-label">경과 시간</div>
                    <div className="timer-value"><Timer startTime={startTime} /></div>
                </div>

                <div className="phase-indicator">
                    <div className="phase-label">면접 단계</div>
                    <div className="phase-steps">
                        {PHASES.map((phase, i) => (
                            <div
                                key={phase}
                                className={`phase-step ${i < phaseIdx ? 'done' : i === phaseIdx ? 'active' : ''}`}
                            >
                                <div className="phase-dot" />
                                {phase}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="card" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    <div style={{ fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>💡 면접 팁</div>
                    <ul style={{ paddingLeft: 16, lineHeight: 1.8 }}>
                        <li>구체적인 사례를 들어 설명하세요</li>
                        <li>STAR 기법을 활용하세요</li>
                        <li>자신감 있게 답변하세요</li>
                    </ul>
                </div>
            </aside>
        </div>
    )
}
