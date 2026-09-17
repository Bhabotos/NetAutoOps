import { createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { authApi } from "../api/auth";
import { configureApiClient } from "../api/client";
import type { User } from "../types/auth";

const TOKEN_STORAGE_KEY = "netautoops_token";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const tokenRef = useRef<string | null>(localStorage.getItem(TOKEN_STORAGE_KEY));

  const clearSession = useCallback(() => {
    tokenRef.current = null;
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    configureApiClient({
      getToken: () => tokenRef.current,
      onUnauthorized: clearSession,
    });
  }, [clearSession]);

  useEffect(() => {
    if (!tokenRef.current) {
      setStatus("unauthenticated");
      return;
    }
    authApi
      .me()
      .then((me) => {
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        // configureApiClient's onUnauthorized already clears the session on
        // a 401; this catch just prevents an unhandled rejection for any
        // other failure (e.g. the API being unreachable on first load).
        clearSession();
      });
    // Runs once on mount only -- tokenRef is a ref, not reactive state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { access_token } = await authApi.login({ username, password });
    tokenRef.current = access_token;
    localStorage.setItem(TOKEN_STORAGE_KEY, access_token);
    const me = await authApi.me();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const value = useMemo(
    () => ({ user, status, login, logout: clearSession }),
    [user, status, login, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
