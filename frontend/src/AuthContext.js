import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";
import { API } from "./lib/api";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(() => localStorage.getItem("ru_token"));

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setUser(r.data))
      .catch(() => { localStorage.removeItem("ru_token"); setToken(null); })
      .finally(() => setLoading(false));
  }, [token]);

  const login = async (email, password) => {
    const r = await axios.post(`${API}/auth/login`, { email, password });
    localStorage.setItem("ru_token", r.data.token);
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
    localStorage.removeItem("ru_token"); setToken(null); setUser(null);
  };

  return <AuthCtx.Provider value={{ user, token, loading, login, register, logout }}>{children}</AuthCtx.Provider>;
};

export const useAuth = () => useContext(AuthCtx);
