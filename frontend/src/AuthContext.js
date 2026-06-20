import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";
import { API } from "./lib/api";

const AuthCtx = createContext(null);

const storage = {
  get(key) {
    try {
      if (typeof window === "undefined" || !window.localStorage) return null;
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      if (typeof window === "undefined" || !window.localStorage) return;
      window.localStorage.setItem(key, value);
    } catch {}
  },
  remove(key) {
    try {
      if (typeof window === "undefined" || !window.localStorage) return;
      window.localStorage.removeItem(key);
    } catch {}
  },
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(() => storage.get("ru_token"));

  const refreshUser = async (nextToken = token) => {
    if (!nextToken) {
      setUser(null);
      return null;
    }
    const response = await axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${nextToken}` } });
    setUser(response.data);
    return response.data;
  };

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => setUser(response.data))
      .catch(() => { storage.remove("ru_token"); setToken(null); })
      .finally(() => setLoading(false));
  }, [token]);

  const login = async (email, password) => {
    const r = await axios.post(`${API}/auth/login`, { email, password });
    storage.set("ru_token", r.data.token);
    setToken(r.data.token); setUser(r.data.user);
    return r.data.user;
  };
  const register = async (pseudo, email, password, country = "FR") => {
    await axios.post(`${API}/auth/register`, { pseudo, email, password, country });
    return login(email, password);
  };
  const logout = async () => {
    try { await axios.post(`${API}/auth/logout`, {}, { headers: { Authorization: `Bearer ${token}` } }); }
    catch (err) { console.warn("Logout API call failed (non-blocking):", err?.message || err); }
    storage.remove("ru_token"); setToken(null); setUser(null);
  };

  return <AuthCtx.Provider value={{ user, token, loading, login, register, logout, refreshUser, setUser }}>{children}</AuthCtx.Provider>;
};

export const useAuth = () => useContext(AuthCtx);
