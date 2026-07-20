import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";

interface AuthState {
  token: string | null;
  email: string | null;
  name: string | null;
  pictureUrl: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem("qe_token"));
  const [email, setEmail] = useState<string | null>(() => sessionStorage.getItem("qe_email"));
  const [name, setName] = useState<string | null>(() => sessionStorage.getItem("qe_name"));
  const [pictureUrl, setPictureUrl] = useState<string | null>(() => sessionStorage.getItem("qe_picture"));

  useEffect(() => {
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common["Authorization"];
    }
  }, [token]);

  const persist = (t: string, e: string, n?: string | null, p?: string | null) => {
    sessionStorage.setItem("qe_token", t);
    sessionStorage.setItem("qe_email", e);
    if (n) sessionStorage.setItem("qe_name", n); else sessionStorage.removeItem("qe_name");
    if (p) sessionStorage.setItem("qe_picture", p); else sessionStorage.removeItem("qe_picture");
    setToken(t);
    setEmail(e);
    setName(n ?? null);
    setPictureUrl(p ?? null);
  };

  const login = async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    persist(data.access_token, data.email, data.name, data.picture_url);
  };

  const register = async (email: string, password: string) => {
    const { data } = await api.post("/auth/register", { email, password });
    persist(data.access_token, data.email, data.name, data.picture_url);
  };

  const loginWithGoogle = async (idToken: string) => {
    const { data } = await api.post("/auth/google", { id_token: idToken });
    persist(data.access_token, data.email, data.name, data.picture_url);
  };

  const logout = () => {
    sessionStorage.removeItem("qe_token");
    sessionStorage.removeItem("qe_email");
    sessionStorage.removeItem("qe_name");
    sessionStorage.removeItem("qe_picture");
    setToken(null);
    setEmail(null);
    setName(null);
    setPictureUrl(null);
  };

  return (
    <AuthContext.Provider value={{ token, email, name, pictureUrl, login, register, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
