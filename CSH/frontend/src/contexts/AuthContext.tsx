"use client";
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { authApi, type UserInfo } from "@/lib/api";

interface AuthCtx {
  user: UserInfo | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx | null>(null);
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
};

const SESSION_TIMEOUT = 60 * 60 * 1000;   // 60분
const IDLE_TIMEOUT = 30 * 60 * 1000;      // 30분

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 초기 로드 – sessionStorage 복원
  useEffect(() => {
    const stored = sessionStorage.getItem("interview_user");
    const t = sessionStorage.getItem("access_token");
    if (stored && t) {
      try { setUser(JSON.parse(stored)); setToken(t); } catch { /* empty */ }
    }
    setLoading(false);
  }, []);

  // 자동 로그아웃 (세션 60분 / 유휴 30분)
  useEffect(() => {
    if (!token) return;
    const loginTime = Number(sessionStorage.getItem("login_time") || Date.now());
    let idleTimer: ReturnType<typeof setTimeout>;
    let sessionTimer: ReturnType<typeof setTimeout>;

    const doLogout = () => { logout(); alert("세션이 만료되었습니다. 다시 로그인 해주세요."); };

    const resetIdle = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(doLogout, IDLE_TIMEOUT);
    };

    sessionTimer = setTimeout(doLogout, SESSION_TIMEOUT - (Date.now() - loginTime));
    resetIdle();

    const events = ["mousemove", "keydown", "click", "scroll", "touchstart"] as const;
    events.forEach(e => window.addEventListener(e, resetIdle));

    return () => {
      clearTimeout(idleTimer); clearTimeout(sessionTimer);
      events.forEach(e => window.removeEventListener(e, resetIdle));
    };
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    setUser(res.user);
    setToken(res.access_token);
    sessionStorage.setItem("interview_user", JSON.stringify(res.user));
    sessionStorage.setItem("access_token", res.access_token);
    sessionStorage.setItem("login_time", String(Date.now()));
  }, []);

  const logout = useCallback(() => {
    setUser(null); setToken(null);
    sessionStorage.clear();
  }, []);

  const refresh = useCallback(() => {
    const stored = sessionStorage.getItem("interview_user");
    if (stored) try { setUser(JSON.parse(stored)); } catch { /* empty */ }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const u = await authApi.getUser();
      setUser(u);
      sessionStorage.setItem("interview_user", JSON.stringify(u));
    } catch { /* empty */ }
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refresh, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
