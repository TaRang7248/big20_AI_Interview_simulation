/**
 * VideoInterviewSession — Phase 3 (Sections 3-1 through 3-6)
 *
 * Full VIDEO interview page with:
 * - Capability gate: DOM removed entirely when video_enabled=false
 * - WebRTC connection via multimodal API (single Offer/Answer, no Trickle ICE)
 * - SSE primary projection (event_seq inversion guard via useSSEProjection)
 * - STT partial caption display (ephemeral — never written to DB)
 * - Blind Mode: question text DOM removed (Phase 3-6)
 * - GPU Queue 429 UX: GPUQueueBanner with 30s retry
 * - Deadline cut-off: session status enum from server
 * - Reconnect: authority pull on re-entry
 *
 * Contracts:
 * - Section 9.4: No local business state
 * - Section 17: Status enum from server
 * - Section 27: Authority Pull on re-entry
 * - Section 37: SSE primary, event_seq monotonic
 * - Section 69: interview_mode immutable after session start
 * - Section 71: Blind Mode = DOM removal, not hidden
 * - Section 79: E_GPU_QUEUE_LIMIT handled with GPUQueueBanner
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../services/api'
import { useSessionStore } from '../../stores/sessionStore'
import { useCapabilityStore } from '../../stores/capabilityStore'
import ErrorBanner from '../../components/ErrorBanner'
import TracedButton from '../../components/TracedButton'
import GPUQueueBanner from '../../components/GPUQueueBanner'
import { useSSEProjection } from '../../hooks/useSSEProjection'
import { createTraceId, ActionTrace } from '../../lib/traceId'
import { ERROR_CODES, getErrorMessage } from '../../lib/errorCodes'

const MULTIMODAL_BASE = '/api/v1/sessions'

export default function VideoInterviewSession() {
    const { interviewId } = useParams()
    const navigate = useNavigate()

    // ─── Session & Capability State ──────────────────────────────────────────
    const [sessionData, setSessionData] = useState(null)
    const [isDone, setIsDone] = useState(false)
    const [sttPartial, setSttPartial] = useState('')  // Phase 3-4: ephemeral only
    const [webrtcState, setWebrtcState] = useState('idle')  // idle | connecting | connected | failed
    const [gpuQueue, setGpuQueue] = useState(null)         // Phase 3-5: 429 error data
    const chatBottomRef = useRef(null)

    const { setLoading, setError, error, isLoading, isPendingMutation, setFromProjection, reset } = useSessionStore()
    const { video_enabled, webrtc_enabled, blind_mode, ai_question_text_visible, hydrateFromSession, resetSession } = useCapabilityStore()

    // WebRTC refs
    const pcRef = useRef(null)
    const localStreamRef = useRef(null)
    const localVideoRef = useRef(null)
    const remoteVideoRef = useRef(null)

    // ─── Authority Pull on mount / reconnect (Section 27) ───────────────────
    useEffect(() => {
        let cancelled = false

        async function authorityPull() {
            const traceId = createTraceId()
            ActionTrace.trigger(traceId, 'video-session:authority-pull')
            setLoading(true)

            try {
                const sessionRes = await interviewsApi.get(interviewId)
                if (cancelled) return

                const session = sessionRes.data

                // Phase 3: Hydrate capability store from server policy_snapshot
                hydrateFromSession(session)

                if (session.status === 'EVALUATED' || session.status === 'COMPLETED') {
                    setIsDone(true)
                }
                setSessionData(session)
                setFromProjection({
                    sessionId: interviewId,
                    status: session.status,
                    currentPhase: session.current_phase,
                })
                ActionTrace.stateApplied(traceId, 'VideoSession')
            } catch (err) {
                if (!cancelled) {
                    setError(err.error_code ? err : { error_code: ERROR_CODES.E_UNKNOWN, trace_id: traceId, message: '세션 정보를 불러오지 못했습니다.' })
                }
            }
        }

        authorityPull()
        return () => {
            cancelled = true
            reset()
            resetSession()
            // Cleanup WebRTC
            pcRef.current?.close()
            localStreamRef.current?.getTracks().forEach(t => t.stop())
        }
    }, [interviewId])

    // ─── SSE Projection (Phase 3-3: SSE primary for VIDEO) ──────────────────
    const handleSSEEvent = useCallback((data) => {
        // Handle VIDEO-specific SSE events
        if (data.type === 'stt_partial') {
            // Phase 3-4: STT partial is ephemeral — only in UI, never persisted
            setSttPartial(data.text || '')
        } else if (data.type === 'stt_final_ack') {
            setSttPartial('')  // Clear on final (server handled persistence separately)
        } else if (data.type === 'webrtc_state') {
            setWebrtcState(data.state || 'idle')
        } else if (data.type === 'deadline_cut') {
            // Section 14: Server authority on deadline
            setSessionData(prev => prev ? { ...prev, status: data.next_status } : prev)
        }
    }, [])

    const handleAuthorityPull = useCallback(async (sid) => {
        try {
            const res = await interviewsApi.get(sid)
            setSessionData(res.data)
            if (res.data.status === 'EVALUATED' || res.data.status === 'COMPLETED') setIsDone(true)
        } catch (err) {
            setError({ error_code: ERROR_CODES.E_UNKNOWN, message: 'SSE 갭 복구 실패' })
        }
    }, [])

    const { connected: sseConnected, lastSeq, sseError } = useSSEProjection(
        interviewId,
        handleAuthorityPull,
        handleSSEEvent
    )

    // ─── Phase 3-2: WebRTC Offer/Answer ─────────────────────────────────────
    const startWebRTC = useCallback(async () => {
        if (!webrtc_enabled) return
        if (webrtcState === 'connecting' || webrtcState === 'connected') return

        setWebrtcState('connecting')
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, 'webrtc:start')

        try {
            // Get local media stream
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
            localStreamRef.current = stream
            if (localVideoRef.current) {
                localVideoRef.current.srcObject = stream
            }

            // Create PeerConnection (no TURN — Phase 3 MVP)
            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
            })
            pcRef.current = pc

            stream.getTracks().forEach(t => pc.addTrack(t, stream))

            // Remote stream (AI responses)
            pc.ontrack = (event) => {
                if (remoteVideoRef.current && event.streams[0]) {
                    remoteVideoRef.current.srcObject = event.streams[0]
                }
            }

            // Phase 3: No Trickle ICE — wait for full ICE gathering
            const offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            // Wait for ICE gathering to complete
            await new Promise((resolve) => {
                if (pc.iceGatheringState === 'complete') { resolve(); return }
                pc.addEventListener('icegatheringstatechange', () => {
                    if (pc.iceGatheringState === 'complete') resolve()
                })
                setTimeout(resolve, 5000) // 5s max wait
            })

            // Send full SDP offer (Trickle ICE disabled)
            const res = await fetch(`${MULTIMODAL_BASE}/${interviewId}/multimodal/webrtc/offer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('imh_token')}`,
                    'X-Trace-Id': traceId,
                },
                body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type }),
            })

            if (res.status === 429) {
                // Phase 3-5: GPU Queue — show banner
                const errData = await res.json()
                setGpuQueue({ trace_id: traceId, detail: errData.detail })
                setWebrtcState('idle')
                pcRef.current?.close()
                localStreamRef.current?.getTracks().forEach(t => t.stop())
                return
            }

            if (!res.ok) {
                throw new Error(`WebRTC signaling failed: ${res.status}`)
            }

            const answer = await res.json()
            await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type })
            setWebrtcState('connected')
            ActionTrace.stateApplied(traceId, 'WebRTC:connected')

            // Track connection state
            pc.onconnectionstatechange = () => {
                if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
                    setWebrtcState('failed')
                } else if (pc.connectionState === 'connected') {
                    setWebrtcState('connected')
                }
            }
        } catch (err) {
            setWebrtcState('failed')
            setError({ error_code: ERROR_CODES.E_UNKNOWN, trace_id: traceId, message: `WebRTC 연결 실패: ${err.message}` })
        }
    }, [interviewId, webrtc_enabled, webrtcState])

    // Auto-start WebRTC if VIDEO mode enabled
    useEffect(() => {
        if (video_enabled && webrtcState === 'idle' && !isDone) {
            startWebRTC()
        }
    }, [video_enabled, webrtcState, isDone])

    // Auto-scroll
    useEffect(() => {
        chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [sttPartial])

    // ─── Capability Gate: DOM removal for non-VIDEO (Section 71) ────────────
    // If video_enabled=false AND this was navigated to as Video route, redirect
    useEffect(() => {
        if (sessionData && !video_enabled) {
            // Session loaded but not VIDEO mode — redirect to text session
            navigate(`/candidate/interview/${interviewId}`, { replace: true })
        }
    }, [sessionData, video_enabled])

    if (isLoading && !sessionData) {
        return (
            <div style={styles.fullPage}>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ textAlign: 'center', color: '#94a3b8' }}>
                        <div style={styles.spinner} />
                        <p style={{ marginTop: 16 }}>VIDEO 면접 세션 로딩 중...</p>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div style={styles.fullPage}>
            {/* Phase 3-5: GPU Queue Banner overlay */}
            {gpuQueue && (
                <GPUQueueBanner
                    errorData={gpuQueue}
                    onRetry={async (traceId) => {
                        setGpuQueue(null)
                        await startWebRTC()
                    }}
                    onCancel={() => {
                        setGpuQueue(null)
                        navigate(-1)
                    }}
                />
            )}

            {/* Header */}
            <div style={styles.header}>
                <div>
                    <h1 style={styles.headerTitle}>
                        🎬 {sessionData?.job_title || 'VIDEO 면접 진행 중'}
                    </h1>
                    <div style={styles.badges}>
                        <span style={{ ...styles.badge, background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' }}>
                            VIDEO 모드
                        </span>
                        {/* Phase 3-6: Blind Mode indicator */}
                        {blind_mode && (
                            <span style={{ ...styles.badge, background: 'rgba(168,85,247,0.15)', color: '#c084fc', border: '1px solid rgba(168,85,247,0.3)' }}>
                                🙈 블라인드 모드
                            </span>
                        )}
                        {/* SSE status */}
                        <span style={{ ...styles.badge, background: sseConnected ? 'rgba(34,197,94,0.15)' : 'rgba(107,114,128,0.15)', color: sseConnected ? '#22c55e' : '#6b7280', border: `1px solid ${sseConnected ? 'rgba(34,197,94,0.3)' : 'rgba(107,114,128,0.3)'}` }}>
                            {sseConnected ? `● LIVE #${lastSeq}` : '○ 연결 중'}
                        </span>
                        {/* WebRTC state */}
                        <span style={{ ...styles.badge, background: webrtcState === 'connected' ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.15)', color: webrtcState === 'connected' ? '#22c55e' : '#f59e0b', border: '1px solid transparent' }}>
                            WebRTC: {webrtcState}
                        </span>
                    </div>
                </div>
                <span style={styles.phaseBadge}>{sessionData?.current_phase || '준비 중'}</span>
            </div>

            <ErrorBanner error={error || sseError} onDismiss={() => setError(null)} />

            {/* Main content: video panels + question area */}
            <div style={styles.mainContent}>
                {/* Video panels (only when webrtc_enabled is true) */}
                {webrtc_enabled && (
                    <div style={styles.videoPanels}>
                        <div style={styles.videoPanel}>
                            <div style={styles.videoLabel}>나</div>
                            <video
                                ref={localVideoRef}
                                autoPlay
                                muted
                                playsInline
                                style={styles.video}
                            />
                        </div>
                        <div style={styles.videoPanel}>
                            <div style={styles.videoLabel}>면접관 (AI)</div>
                            <video
                                ref={remoteVideoRef}
                                autoPlay
                                playsInline
                                style={styles.video}
                            />
                            {webrtcState !== 'connected' && (
                                <div style={styles.videoPlaceholder}>
                                    {webrtcState === 'connecting' ? '연결 중...' : 'AI 면접관 대기 중'}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Question area */}
                <div style={styles.questionArea}>
                    {/* Phase 3-6: Blind Mode — question text DOM removed (not hidden) */}
                    {!blind_mode && sessionData?.current_phase && (
                        <div style={styles.questionCard}>
                            <div style={styles.questionLabel}>현재 질문 단계</div>
                            <div style={styles.questionText}>{sessionData.current_phase}</div>
                        </div>
                    )}

                    {/* Phase 3-4: STT Partial caption (ephemeral — not persisted) */}
                    {sttPartial && (
                        <div style={styles.sttCaption}>
                            <span style={styles.sttIndicator}>🎤</span>
                            <span style={styles.sttText}>{sttPartial}</span>
                            <span style={styles.sttEphemeral}>(실시간 자막 — 저장되지 않음)</span>
                        </div>
                    )}

                    {isDone ? (
                        <div style={styles.completedArea}>
                            <div style={styles.completedBadge}>✅ VIDEO 면접 완료</div>
                            <p style={{ color: '#94a3b8', marginBottom: 16 }}>수고하셨습니다. 평가가 백그라운드에서 진행됩니다.</p>
                            <TracedButton
                                id="view-result-btn-video"
                                onClick={async (traceId) => {
                                    ActionTrace.trigger(traceId, 'video:view-result')
                                    navigate(`/candidate/result/${interviewId}`)
                                }}
                                actionName="video:navigate-result"
                                style={{ padding: '12px 32px' }}
                            >
                                결과 확인하기
                            </TracedButton>
                        </div>
                    ) : (
                        <div style={styles.statusArea}>
                            <p style={{ color: '#64748b', fontSize: 14 }}>
                                {webrtcState === 'connected'
                                    ? '🔴 녹화 중 — 음성으로 답변하세요.'
                                    : webrtcState === 'connecting'
                                        ? '카메라 및 마이크 연결 중...'
                                        : 'WebRTC 연결 대기 중...'}
                            </p>
                            {webrtcState === 'failed' && (
                                <TracedButton
                                    id="retry-webrtc-btn"
                                    onClick={async (traceId) => {
                                        ActionTrace.trigger(traceId, 'webrtc:manual-retry')
                                        setWebrtcState('idle')
                                    }}
                                    actionName="webrtc:retry"
                                    style={{ marginTop: 8 }}
                                >
                                    WebRTC 재연결
                                </TracedButton>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

const styles = {
    fullPage: {
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0f1e 0%, #0f172a 100%)',
        display: 'flex',
        flexDirection: 'column',
    },
    spinner: {
        width: 48, height: 48,
        border: '4px solid rgba(239,68,68,0.2)',
        borderTopColor: '#ef4444',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
        margin: '0 auto',
    },
    header: {
        padding: '16px 24px',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(10,15,30,0.9)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
    },
    headerTitle: {
        color: '#f1f5f9',
        fontSize: 18,
        fontWeight: 700,
        margin: '0 0 6px',
    },
    badges: { display: 'flex', gap: 8, flexWrap: 'wrap' },
    badge: {
        padding: '2px 10px',
        borderRadius: 99,
        fontSize: 12,
        fontWeight: 600,
    },
    phaseBadge: {
        background: 'rgba(239,68,68,0.15)',
        color: '#f87171',
        padding: '4px 14px',
        borderRadius: 99,
        fontSize: 13,
        border: '1px solid rgba(239,68,68,0.3)',
        whiteSpace: 'nowrap',
    },
    mainContent: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        overflow: 'hidden',
    },
    videoPanels: {
        display: 'flex',
        gap: 12,
        padding: '16px 24px',
        background: '#000',
    },
    videoPanel: {
        flex: 1,
        position: 'relative',
        borderRadius: 12,
        overflow: 'hidden',
        background: '#0a0a0a',
        border: '1px solid #1e293b',
        minHeight: 200,
    },
    videoLabel: {
        position: 'absolute',
        top: 8,
        left: 8,
        zIndex: 2,
        background: 'rgba(0,0,0,0.6)',
        color: '#fff',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 12,
    },
    video: {
        width: '100%',
        height: '100%',
        objectFit: 'cover',
        display: 'block',
    },
    videoPlaceholder: {
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#64748b',
        fontSize: 14,
    },
    questionArea: {
        flex: 1,
        padding: '20px 24px',
        overflowY: 'auto',
    },
    questionCard: {
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 12,
        padding: 20,
        marginBottom: 16,
    },
    questionLabel: {
        fontSize: 11,
        color: '#64748b',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: 8,
    },
    questionText: {
        color: '#f1f5f9',
        fontSize: 16,
        fontWeight: 600,
        lineHeight: 1.6,
    },
    sttCaption: {
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.2)',
        borderRadius: 8,
        padding: '10px 16px',
        marginBottom: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexWrap: 'wrap',
    },
    sttIndicator: { fontSize: 16 },
    sttText: { color: '#f1f5f9', fontSize: 14, flex: 1 },
    sttEphemeral: { fontSize: 11, color: '#64748b', fontStyle: 'italic' },
    statusArea: {
        textAlign: 'center',
        padding: '32px 0',
    },
    completedArea: {
        textAlign: 'center',
        padding: '32px',
    },
    completedBadge: {
        fontSize: 22,
        fontWeight: 700,
        color: '#22c55e',
        marginBottom: 8,
    },
}
