"use client";
/**
 * 이벤트 버스 컨텍스트 (EventBusContext)
 * ========================================
 * WebSocket을 통해 서버의 EventBus 이벤트를 실시간으로 수신하고,
 * React 컴포넌트에서 이벤트를 구독할 수 있도록 지원합니다.
 *
 * SAD 설계서의 "실시간 통신" 패턴 구현:
 * - 서버 → (Redis Pub/Sub) → EventBus → WebSocket → 프론트엔드
 * - 평가 완료, 감정 분석, 리포트 생성 등의 이벤트를 실시간 수신
 *
 * 사용법:
 *   const { subscribe, lastEvent, isConnected } = useEventBus();
 *   useEffect(() => {
 *     const unsub = subscribe("evaluation.completed", (event) => {
 *       console.log("평가 완료:", event.data);
 *     });
 *     return unsub;
 *   }, []);
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
} from "react";

// ========== 타입 정의 ==========

export interface ServerEvent {
  type: "event";
  event_type: string;
  event_id: string;
  timestamp: string;
  source: string;
  data: Record<string, unknown>;
}

type EventHandler = (event: ServerEvent) => void;

interface EventBusCtx {
  /** 특정 이벤트 타입 구독 (unsub 함수 반환) */
  subscribe: (eventType: string, handler: EventHandler) => () => void;
  /** 모든 이벤트 구독 */
  subscribeAll: (handler: EventHandler) => () => void;
  /** 가장 최근 수신된 이벤트 */
  lastEvent: ServerEvent | null;
  /** WebSocket 연결 상태 */
  isConnected: boolean;
  /** 수신된 이벤트 수 */
  eventCount: number;
}

// ========== Context ==========

const EventBusContext = createContext<EventBusCtx | null>(null);

export const useEventBus = () => {
  const ctx = useContext(EventBusContext);
  if (!ctx) throw new Error("useEventBus must be inside EventBusProvider");
  return ctx;
};

// ========== Provider ==========

interface Props {
  children: ReactNode;
  sessionId?: string;
}

export function EventBusProvider({ children, sessionId }: Props) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<ServerEvent | null>(null);
  const [eventCount, setEventCount] = useState(0);

  // 핸들러 레지스트리
  const handlers = useRef<Map<string, Set<EventHandler>>>(new Map());
  const globalHandlers = useRef<Set<EventHandler>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  // 이벤트 디스패치
  const dispatchEvent = useCallback((event: ServerEvent) => {
    setLastEvent(event);
    setEventCount((c) => c + 1);

    // 타입별 핸들러 실행
    const typeHandlers = handlers.current.get(event.event_type);
    if (typeHandlers) {
      typeHandlers.forEach((h) => {
        try { h(event); } catch (e) { console.error("[EventBus] handler error:", e); }
      });
    }

    // 글로벌 핸들러 실행
    globalHandlers.current.forEach((h) => {
      try { h(event); } catch (e) { console.error("[EventBus] global handler error:", e); }
    });
  }, []);

  // WebSocket 연결
  useEffect(() => {
    if (!sessionId) return;

    const token = typeof window !== "undefined" ? sessionStorage.getItem("token") : null;
    if (!token) return;

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/interview/${sessionId}?token=${token}`;

    let alive = true;

    const connect = () => {
      if (!alive) return;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log("[EventBus] WebSocket 연결됨");
      };

      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === "event") {
            dispatchEvent(data as ServerEvent);
          }
          // pong 등 다른 메시지는 무시
        } catch {
          // JSON 파싱 실패 무시
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // 재연결 (5초 후)
        if (alive) {
          reconnectTimer.current = setTimeout(connect, 5000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      alive = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
      setIsConnected(false);
    };
  }, [sessionId, dispatchEvent]);

  // 구독 함수
  const subscribe = useCallback((eventType: string, handler: EventHandler) => {
    if (!handlers.current.has(eventType)) {
      handlers.current.set(eventType, new Set());
    }
    handlers.current.get(eventType)!.add(handler);

    return () => {
      handlers.current.get(eventType)?.delete(handler);
    };
  }, []);

  const subscribeAll = useCallback((handler: EventHandler) => {
    globalHandlers.current.add(handler);
    return () => {
      globalHandlers.current.delete(handler);
    };
  }, []);

  return (
    <EventBusContext.Provider
      value={{ subscribe, subscribeAll, lastEvent, isConnected, eventCount }}
    >
      {children}
    </EventBusContext.Provider>
  );
}
