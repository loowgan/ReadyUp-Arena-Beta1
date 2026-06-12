import React, { useEffect, useState, useRef } from "react";
import { BrowserRouter, Routes, Route, Link, useParams, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { Flame, Trophy, Users, Swords, Radio, Shield, Zap, Crown, Target, AlertTriangle, Coins, Heart, ChevronRight, Play, Lock, CheckCircle2, Circle, Clock, Tv, ExternalLink, Star, TrendingUp, Award, Gamepad2, LogOut, User, Server, Terminal, Plus, Trash2, RefreshCw } from "lucide-react";
import { AuthProvider, useAuth } from "./AuthContext";
import { API, WS_BASE_URL } from "./lib/api";

/* ============== SHARED UI ============== */
const Logo = ({ size = 40 }) => (
  <div className="flex items-center gap-3" data-testid="brand-logo">
    <img src="https://customer-assets.emergentagent.com/job_file-reader-108/artifacts/d88wsvtc_readyup-logo.png"
      alt="ReadyUp Arena" style={{ height: size * 1.6, width: "auto", filter: "drop-shadow(0 0 12px rgba(111, 229, 197, 0.4))" }}/>
  </div>
);

const NavBar = () => {
  const loc = useLocation();
  const links = [
    { to: "/", label: "Accueil" }, { to: "/tournaments", label: "Tournois" },
    { to: "/teams", label: "Équipes" }, { to: "/rankings", label: "Classements" },
    { to: "/duels", label: "Duels 1v1" }, { to: "/live", label: "En direct" }, { to: "/admin", label: "Admin" },
  ];
  return (
    <nav className="sticky top-0 z-50 glass border-b border-white/5" data-testid="main-nav">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link to="/" data-testid="nav-home-logo"><Logo /></Link>
        <div className="hidden md:flex items-center gap-1">
          {links.map(l => (
            <Link key={l.to} to={l.to} data-testid={`nav-link-${l.label.toLowerCase().replace(/\s/g,'-')}`}
              className={`px-4 py-2 text-sm font-display tracking-widest uppercase transition-colors ${loc.pathname === l.to ? "text-orange-500" : "text-white/70 hover:text-white"}`}>
              {l.label}
            </Link>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Link to="/donate" className="btn-ghost" data-testid="nav-donate-btn"><Heart size={14}/>Soutenir</Link>
          <AuthZone/>
        </div>
      </div>
    </nav>
  );
};

const Footer = () => (
  <footer className="mt-24 border-t border-white/5 py-10 px-6" data-testid="footer">
    <div className="max-w-7xl mx-auto grid md:grid-cols-4 gap-8 text-sm">
      <div><Logo size={28}/><p className="text-white/50 mt-3">Plateforme indépendante de tournois e-sport CS2. Non affiliée à Valve.</p></div>
      <div><h4 className="font-display uppercase tracking-widest text-white mb-3">Plateforme</h4>
        <ul className="space-y-2 text-white/60"><li><Link to="/tournaments">Tournois</Link></li><li><Link to="/teams">Équipes</Link></li><li><Link to="/rankings">Classements</Link></li></ul></div>
      <div><h4 className="font-display uppercase tracking-widest text-white mb-3">Communauté</h4>
        <ul className="space-y-2 text-white/60"><li><Link to="/faq">FAQ</Link></li><li><a href="#">Discord</a></li><li><Link to="/donate">Faire un don</Link></li></ul></div>
      <div><h4 className="font-display uppercase tracking-widest text-white mb-3">Légal</h4>
        <ul className="space-y-2 text-white/60"><li><Link to="/legal">Mentions légales</Link></li><li><Link to="/legal">Confidentialité</Link></li><li><Link to="/legal">CGU</Link></li></ul></div>
    </div>
    <p className="text-center text-white/30 mt-8 text-xs tracking-widest uppercase">© 2026 ReadyUp Arena — Non affilié à Valve / Counter-Strike 2</p>
  </footer>
);

const Badge = ({ children, variant = "default", testid }) => {
  const cls = { live: "badge badge-live", soon: "badge badge-soon", verified: "badge badge-verified", offline: "badge badge-offline", default: "badge text-white/60" }[variant];
  return <span className={cls} data-testid={testid}>{variant === "live" && <span className="pulse-dot"/>}{children}</span>;
};

const Stat = ({ label, value, accent }) => (
  <div className="text-center">
    <div className={`font-display text-4xl font-bold ${accent || "text-white"}`}>{value}</div>
    <div className="text-xs uppercase tracking-[0.2em] text-white/40 mt-1">{label}</div>
  </div>
);

const SectionTitle = ({ title, sub, cta }) => (
  <div className="flex items-end justify-between mb-6 mt-12">
    <div><div className="text-xs uppercase tracking-[0.3em] text-orange-500 mb-2">{sub}</div>
      <h2 className="font-display text-3xl sm:text-4xl font-bold uppercase tracking-tight">{title}</h2></div>
    {cta}
  </div>
);

const Particles = () => (
  <div className="particles">{[...Array(20)].map((_, i) => (
    <span key={i} style={{ left: `${Math.random()*100}%`, animationDelay: `${Math.random()*8}s`, animationDuration: `${6+Math.random()*6}s` }}/>))}</div>
);

const TeamLogo = ({ team, size = 48 }) => (
  <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
    <div className="absolute inset-0" style={{ background: team.logo_color, clipPath: "polygon(20% 0,80% 0,100% 50%,80% 100%,20% 100%,0 50%)", filter: `drop-shadow(0 0 12px ${team.logo_color}88)` }}/>
    <span className="relative font-display font-bold text-black" style={{ fontSize: size*0.32 }}>{team.tag.slice(0,3)}</span>
  </div>
);

/* ============== HOME ============== */
const Home = () => {
  const [tournaments, setTournaments] = useState([]);
  const [news, setNews] = useState([]);
  const [stats, setStats] = useState({});
  const [live, setLive] = useState(null);
  const [teams, setTeams] = useState([]);
  useEffect(() => {
    Promise.all([axios.get(`${API}/tournaments`), axios.get(`${API}/news`), axios.get(`${API}/stats/global`), axios.get(`${API}/twitch/live`), axios.get(`${API}/teams`)])
      .then(([t, n, s, l, te]) => { setTournaments(t.data); setNews(n.data); setStats(s.data); setLive(l.data); setTeams(te.data); });
  }, []);

  return (
    <div data-testid="home-page">
      {/* HERO */}
      <section className="relative bg-arena bg-grid scanlines overflow-hidden" style={{ minHeight: "78vh" }}>
        <Particles/>
        <div className="max-w-7xl mx-auto px-6 pt-16 pb-20 relative">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="inline-flex items-center gap-2 border border-orange-500/30 bg-orange-500/5 px-3 py-1 mb-6">
              <span className="pulse-dot text-red-500"/><span className="text-xs uppercase tracking-[0.3em] text-orange-400">Bêta ouverte — Saison 1</span>
            </div>
            <h1 className="font-display text-5xl sm:text-7xl lg:text-8xl font-bold uppercase leading-[0.95] tracking-tighter max-w-4xl">
              Formez votre équipe.<br/>
              <span className="text-neon">Entrez dans l'arène.</span><br/>
              Devenez champion.
            </h1>
            <p className="mt-6 text-lg text-white/60 max-w-2xl">
              La plateforme nouvelle génération de tournois CS2 fun. Salle d'attente temps réel, renforts automatiques, tirage animé, automatisation complète.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/teams" className="btn-neon" data-testid="hero-cta-team"><Users size={16}/>Créer une équipe</Link>
              <Link to="/tournaments" className="btn-ghost" data-testid="hero-cta-tournaments"><Trophy size={16}/>Voir les tournois</Link>
              <Link to="/waiting-room/tr1" className="btn-ghost" data-testid="hero-cta-match"><Swords size={16}/>Trouver un match</Link>
            </div>
          </motion.div>
        </div>
        {/* Stats strip */}
        <div className="relative border-t border-white/5 bg-black/30 backdrop-blur-xl">
          <div className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-3 md:grid-cols-6 gap-4">
            <Stat label="Joueurs" value={stats.players?.toLocaleString() || "—"} accent="text-orange-500"/>
            <Stat label="Équipes" value={stats.teams?.toLocaleString() || "—"}/>
            <Stat label="Tournois" value={stats.tournaments_total || "—"} accent="text-cyan-neon"/>
            <Stat label="Matchs" value={stats.matches_played?.toLocaleString() || "—"}/>
            <Stat label="Renforts" value={stats.reinforcements_completed?.toLocaleString() || "—"} accent="text-yellow-neon"/>
            <Stat label="En ligne" value={stats.online_now || "—"} accent="text-red-500"/>
          </div>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-6">
        {/* TWITCH MAJOR */}
        <SectionTitle sub="Live officiel" title="Major CS2 en direct" cta={live?.live && <Badge variant="live" testid="twitch-live-badge">LIVE</Badge>}/>
        <div className="grid lg:grid-cols-3 gap-4" data-testid="twitch-block">
          <div className="lg:col-span-2 aspect-video glass overflow-hidden relative">
            <iframe title="Twitch" src={`https://player.twitch.tv/?channel=${live?.channel || "esl_csgo"}&parent=${window.location.hostname}&muted=true&autoplay=false`}
              allowFullScreen className="w-full h-full" frameBorder="0"/>
          </div>
          <div className="glass p-6 flex flex-col">
            <Badge variant="live" testid="twitch-status-badge">EN DIRECT</Badge>
            <h3 className="font-display text-xl mt-3">{live?.title || "BLAST Major CS2"}</h3>
            <p className="text-sm text-white/50 mt-1">Chaîne <span className="text-cyan-neon">{live?.channel}</span></p>
            <div className="mt-auto pt-6 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-white/50">Spectateurs</span><span className="font-display text-orange-500">{live?.viewers?.toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-white/50">Jeu</span><span>{live?.game}</span></div>
              <a href={`https://twitch.tv/${live?.channel}`} target="_blank" rel="noreferrer" className="btn-ghost w-full mt-3" data-testid="open-twitch-btn"><ExternalLink size={14}/>Ouvrir sur Twitch</a>
            </div>
          </div>
        </div>

        {/* TOURNAMENTS */}
        <SectionTitle sub="Action immédiate" title="Tournois à venir" cta={<Link to="/tournaments" className="btn-ghost" data-testid="all-tournaments-btn">Tout voir <ChevronRight size={14}/></Link>}/>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tournaments.slice(0,6).map(t => <TournamentCard key={t.id} t={t}/>)}
        </div>

        {/* TOP TEAMS */}
        <SectionTitle sub="Élite" title="Meilleures équipes"/>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {teams.slice(0,4).map((te, i) => (
            <Link to="/teams" key={te.id} className="glass glass-hover p-5 transition-all" data-testid={`top-team-${te.id}`}>
              <div className="flex items-center gap-3"><TeamLogo team={te}/>
                <div><div className="font-display text-lg">{te.name}</div><div className="text-xs text-white/40">#{i+1} • {te.country}</div></div></div>
              <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                <div><div className="font-display text-orange-500 text-lg">{te.elo}</div><div className="text-[10px] uppercase tracking-widest text-white/40">ELO</div></div>
                <div><div className="font-display text-white text-lg">{te.wins}</div><div className="text-[10px] uppercase tracking-widest text-white/40">WIN</div></div>
                <div><div className="font-display text-yellow-neon text-lg">{te.trophies}</div><div className="text-[10px] uppercase tracking-widest text-white/40">🏆</div></div>
              </div>
            </Link>))}
        </div>

        {/* NEWS */}
        <SectionTitle sub="Actualité" title="Dernières news"/>
        <div className="grid md:grid-cols-3 gap-4">
          {news.map(n => (
            <div key={n.id} className="glass p-6" data-testid={`news-${n.id}`}>
              <div className="text-xs text-orange-400 uppercase tracking-widest">{new Date(n.date).toLocaleDateString("fr-FR")}</div>
              <h4 className="font-display text-lg mt-2">{n.title}</h4>
              <p className="text-sm text-white/60 mt-2">{n.excerpt}</p>
            </div>))}
        </div>

        <SectionTitle sub="Communauté" title="Soutiens récents" cta={<Link to="/donate" className="btn-ghost" data-testid="donate-cta-home"><Heart size={14}/>Faire un don</Link>}/>
        <RecentDonors/>
      </div>
    </div>
  );
};

const RecentDonors = () => {
  const [donors, setDonors] = useState([]);
  useEffect(() => { axios.get(`${API}/donations/recent?limit=5`).then(r => setDonors(r.data)).catch(()=>{}); }, []);
  if (donors.length === 0) return (
    <div className="glass p-6 text-center text-white/40" data-testid="no-donors">
      Soyez le premier à soutenir la plateforme ❤️ — <Link to="/donate" className="text-orange-500">Faire un don</Link>
    </div>);
  return (
    <div className="grid md:grid-cols-5 gap-3" data-testid="recent-donors">
      {donors.map((d,i) => (
        <div key={i} className="glass p-4 text-center">
          <Heart className="text-red-500 mx-auto" size={24}/>
          <div className="font-display text-2xl text-yellow-neon mt-2">{d.amount_eur}€</div>
          <div className="text-xs text-white/40 uppercase tracking-widest">{d.kind === "monthly" ? "Mensuel" : "Ponctuel"}</div>
          <div className="text-[10px] text-white/30 mt-1">{new Date(d.at).toLocaleDateString("fr-FR")}</div>
        </div>))}
    </div>);
};

const TournamentCard = ({ t }) => {
  const variant = { open: "soon", registering: "soon", starting: "live", live: "live", in_progress: "live", closed: "offline" }[t.status] || "default";
  const label = { open: "Inscriptions", registering: "Inscriptions", starting: "Lancement", live: "LIVE", in_progress: "En cours", closed: "Terminé" }[t.status];
  return (
    <Link to={`/tournament/${t.id}`} className="glass glass-hover p-5 block relative overflow-hidden" data-testid={`tournament-card-${t.id}`}>
      <div className="absolute top-0 right-0 w-32 h-32 opacity-20 blur-3xl" style={{ background: t.image_color }}/>
      <div className="flex items-start justify-between relative">
        <Badge variant={variant}>{label}</Badge>
        <span className="font-display text-xs text-white/40">{t.format}</span>
      </div>
      <h3 className="font-display text-xl mt-3 uppercase">{t.name}</h3>
      <p className="text-sm text-white/50">{t.organizer}</p>
      <div className="mt-4 flex items-center gap-3 text-xs text-white/60">
        <span className="flex items-center gap-1"><Users size={12}/>{t.registered}/{t.capacity}</span>
        <span className="flex items-center gap-1"><Clock size={12}/>{new Date(t.starts_at).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
        <span className="flex items-center gap-1"><Target size={12}/>{t.region}</span>
      </div>
      <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
        <span className="text-yellow-neon font-display text-sm">{t.prize}</span>
        <span className="text-orange-500"><ChevronRight size={16}/></span>
      </div>
    </Link>
  );
};

/* ============== TOURNAMENTS LIST ============== */
const TournamentsList = () => {
  const [tournaments, setTournaments] = useState([]);
  const [filter, setFilter] = useState("all");
  useEffect(() => { axios.get(`${API}/tournaments`).then(r => setTournaments(r.data)); }, []);
  const filtered = filter === "all" ? tournaments : tournaments.filter(t => t.status === filter);
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="tournaments-page">
      <h1 className="font-display text-5xl uppercase tracking-tight">Catalogue des tournois</h1>
      <p className="text-white/50 mt-2">Tous les formats, toutes les régions. Inscrivez votre équipe ou rejoignez la file solo.</p>
      <div className="flex flex-wrap gap-2 mt-6">
        {["all", "open", "registering", "live", "closed"].map(s => (
          <button key={s} onClick={() => setFilter(s)} data-testid={`filter-${s}`}
            className={`px-4 py-2 text-xs uppercase tracking-widest font-display ${filter === s ? "bg-orange-500 text-black" : "border border-white/10 text-white/60 hover:text-white"}`}>
            {{all:"Tous",open:"Ouverts",registering:"Inscriptions",live:"En direct",closed:"Terminés"}[s]}
          </button>))}
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">{filtered.map(t => <TournamentCard key={t.id} t={t}/>)}</div>
    </div>
  );
};

/* ============== TOURNAMENT DETAIL ============== */
const TournamentDetail = () => {
  const { id } = useParams();
  const { token, user } = useAuth();
  const [t, setT] = useState(null);
  const load = async () => {
    const r = await axios.get(`${API}/tournaments/${id}`);
    setT(r.data);
  };
  useEffect(() => {
    axios.get(`${API}/tournaments/${id}`).then(r => setT(r.data));
  }, [id]);
  const register = async (entity_type) => {
    if (!token) { alert("Connectez-vous pour vous inscrire."); return; }
    const entity_name = entity_type === "team"
      ? (prompt("Nom de votre équipe ?") || "").trim()
      : (user?.pseudo || "Joueur");
    if (entity_type === "team" && !entity_name) return;
    try {
      await axios.post(`${API}/tournaments/${id}/register`, { entity_type, entity_name }, { headers: { Authorization: `Bearer ${token}` } });
      await load();
      alert("Inscription confirmée ✅");
    } catch (e) { alert(e.response?.data?.detail || "Erreur d'inscription"); }
  };
  if (!t) return <div className="p-10 text-center text-white/40">Chargement…</div>;
  const canRegister = ["open", "registering"].includes(t.status) && t.registered < t.capacity;
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="tournament-detail">
      <Link to="/tournaments" className="text-orange-500 text-xs uppercase tracking-widest">← Retour catalogue</Link>
      <div className="glass mt-4 p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 opacity-30 blur-3xl" style={{ background: t.image_color }}/>
        <Badge variant={t.status === "open" ? "soon" : "live"}>{t.status.toUpperCase()}</Badge>
        <h1 className="font-display text-5xl uppercase mt-3">{t.name}</h1>
        <p className="text-white/60">{t.organizer} • {t.format} • {t.mode} • {t.region}</p>
        <div className="grid sm:grid-cols-4 gap-4 mt-6">
          <Stat label="Inscrites" value={`${t.registered}/${t.capacity}`}/>
          <Stat label="Format" value={t.format} accent="text-orange-500"/>
          <Stat label="Récompense" value="🏆" accent="text-yellow-neon"/>
          <Stat label="Début" value={new Date(t.starts_at).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}/>
        </div>
        <div className="mt-6 flex gap-2 flex-wrap">
          {canRegister ? (
            <>
              <button onClick={() => register("team")} className="btn-neon" data-testid="register-team-btn"><Users size={14}/>Inscrire mon équipe</button>
              <button onClick={() => register("solo")} className="btn-ghost" data-testid="register-solo-btn"><User size={14}/>Rejoindre la file solo</button>
            </>
          ) : (
            <span className="px-4 py-2 text-xs uppercase tracking-widest border border-white/10 text-white/40" data-testid="register-closed">Inscriptions fermées</span>
          )}
          <Link to={`/waiting-room/${t.id}`} className="btn-ghost" data-testid="enter-waiting-room-btn"><Radio size={14}/>Salle d'attente</Link>
        </div>
      </div>
      <div className="grid lg:grid-cols-2 gap-4 mt-6">
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Équipes inscrites ({t.teams_in.length})</h3>
          <div className="space-y-2">{t.teams_in.map((te,i) => (
            <div key={te.id} className="flex items-center gap-3 p-2 border border-white/5">
              <span className="font-mono-display text-white/30 text-xs">#{String(i+1).padStart(2,"0")}</span>
              <TeamLogo team={te} size={32}/><span className="font-display flex-1">{te.name}</span>
              <span className="text-xs text-cyan-neon">ELO {te.elo}</span>
            </div>))}</div>
        </div>
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">File solo / Renforts ({t.solo_queue.length})</h3>
          <div className="space-y-2">{t.solo_queue.map(p => (
            <div key={p.id} className="flex items-center gap-3 p-2 border border-white/5">
              <span className={`w-2 h-2 rounded-full ${p.online ? "bg-green-400 shadow-[0_0_8px_#4ade80]" : "bg-white/20"}`}/>
              <span className="font-display flex-1">{p.pseudo} <span className="text-xs text-white/40">{p.role}</span></span>
              {p.steam_verified && <Badge variant="verified" testid="steam-verified-mini">✓ STEAM</Badge>}
            </div>))}</div>
        </div>
      </div>
      <BracketSection tid={t.id}/>
    </div>
  );
};

/* ============== BRACKET ============== */
const BracketSection = ({ tid }) => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = { Authorization: `Bearer ${token}` };
  const [bracket, setBracket] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const r = await axios.get(`${API}/tournaments/${tid}/bracket`);
      setBracket(r.data);
    } catch {
      setBracket(null);
    }
  };
  useEffect(() => {
    axios.get(`${API}/tournaments/${tid}/bracket`).then(r => setBracket(r.data)).catch(() => setBracket(null));
  }, [tid]);
  const gen = async (type) => { setBusy(true);
    try { await axios.post(`${API}/tournaments/${tid}/bracket/generate`, { type }, { headers: authH }); await load(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); } finally { setBusy(false); } };
  const report = async (mid, winner_id) => {
    try { const r = await axios.post(`${API}/tournaments/${tid}/bracket/match/${mid}/result`, { winner_id, expected_version: bracket?.version }, { headers: authH }); setBracket(r.data); }
    catch (e) { if (e.response?.status === 409) { await load(); } alert(e.response?.data?.detail || "Erreur"); } };

  const groupLabel = { W: "Bracket principal", L: "Bracket des perdants", GF: "Grande finale" };
  const renderGroup = (g) => {
    const ms = (bracket.matches[g] || []);
    if (!ms.length) return null;
    const rounds = [...new Set(ms.map(m => m.round))].sort((a, b) => a - b);
    return (
      <div key={g} className="mb-6" data-testid={`bracket-group-${g}`}>
        <h4 className="font-display text-sm uppercase tracking-widest text-white/50 mb-3">{groupLabel[g]}</h4>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {rounds.map(rnd => (
            <div key={rnd} className="flex flex-col gap-3 min-w-[210px]">
              <div className="text-xs text-white/30 uppercase tracking-widest">Tour {rnd + 1}</div>
              {ms.filter(m => m.round === rnd).map(m => (
                <div key={m.id} className="glass p-3" data-testid={`bmatch-${m.id}`}>
                  {["a", "b"].map(slot => {
                    const ent = m[slot]; const name = m[slot + "_name"];
                    const isWin = ent && m.winner_id === ent.id;
                    return (
                      <div key={slot} className={`flex items-center justify-between py-1 px-2 ${isWin ? "text-cyan-neon font-bold" : "text-white/70"}`}>
                        <span className="text-sm truncate">{name || (m.phantom ? "—" : "À déterminer")}</span>
                        {isAdmin && ent && m[slot === "a" ? "b" : "a"] && !m.winner_id && (
                          <button onClick={() => report(m.id, ent.id)} className="text-xs btn-ghost py-0.5 px-2" data-testid={`bwin-${m.id}-${slot}`}>✓</button>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="glass p-6 mt-6" data-testid="bracket-section">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="font-display text-xl uppercase">Bracket</h3>
        {isAdmin && (
          <div className="flex gap-2">
            <button disabled={busy} onClick={() => gen("single")} className="btn-ghost text-xs" data-testid="gen-single-btn">Générer (élim. simple)</button>
            <button disabled={busy} onClick={() => gen("double")} className="btn-ghost text-xs" data-testid="gen-double-btn">Générer (élim. double)</button>
          </div>
        )}
      </div>
      {!bracket ? <p className="text-white/40 mt-4" data-testid="no-bracket">Aucun bracket généré pour ce tournoi.</p> : (
        <div className="mt-4">
          {bracket.champion_id && <div className="mb-4 text-yellow-neon font-display flex items-center gap-2" data-testid="bracket-champion"><Crown size={16}/>Champion désigné !</div>}
          {["W", "L", "GF"].map(renderGroup)}
        </div>
      )}
    </div>
  );
};
const WaitingRoom = () => {
  const { id } = useParams();
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [seconds, setSeconds] = useState(null);
  const [phase, setPhase] = useState("open");
  const [presence, setPresence] = useState([]);
  const [liveEvents, setLiveEvents] = useState([]);
  const [chat, setChat] = useState([]);
  const [msg, setMsg] = useState("");
  const wsRef = useRef(null);

  useEffect(() => { axios.get(`${API}/tournaments/${id}/waiting-room`).then(r => setData(r.data)); }, [id]);

  useEffect(() => {
    const wsUrl = `${WS_BASE_URL}/api/ws/waiting-room/${id}` + (token ? `?token=${token}` : "");
    const ws = new WebSocket(wsUrl); wsRef.current = ws;
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.type === "countdown") { setSeconds(m.seconds); setPhase(m.phase); if (m.seconds <= 10) navigate(`/countdown/${id}`); }
      if (m.type === "presence") setPresence(m.users || []);
      if (m.type === "event") setLiveEvents(prev => [{ time: m.time, msg: m.msg }, ...prev].slice(0, 30));
      if (m.type === "go") navigate(`/draw/${id}`);
      if (m.type === "chat") setChat(prev => [...prev, m].slice(-50));
    };
    return () => ws.close();
  }, [id, token, navigate]);

  const startCountdown = () => wsRef.current?.send(JSON.stringify({ action: "start_countdown", from: 30 }));
  const markReady = () => wsRef.current?.send(JSON.stringify({ action: "ready" }));
  const sendChat = () => { if (msg.trim()) { wsRef.current?.send(JSON.stringify({ action: "chat", msg })); setMsg(""); } };

  if (!data) return <div className="p-10 text-center text-white/40">Chargement…</div>;
  const displaySec = seconds !== null ? seconds : data.starts_in_seconds;
  const mm = String(Math.floor(displaySec/60)).padStart(2,"0");
  const ss = String(displaySec%60).padStart(2,"0");
  const phaseColor = { open: "text-white", first_call: "text-yellow-neon", last_call: "text-orange-500", countdown: "text-red-500" }[phase] || "text-white";
  const phaseLabel = { open: "Salle d'attente — ouverte", first_call: "Premier appel — confirmez votre équipe", last_call: "Dernier appel — départ imminent", countdown: "Décompte" }[phase] || "Salle d'attente";

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="waiting-room">
      <div className="glass p-8 text-center relative overflow-hidden">
        <Particles/>
        <div className="flex items-center justify-center gap-3"><Badge variant="live">SALLE D'ATTENTE</Badge>
          <span className="text-xs uppercase tracking-widest text-cyan-neon" data-testid="ws-presence-count">● {presence.length} connecté{presence.length>1?'s':''}</span></div>
        <div className={`font-display font-bold text-7xl sm:text-8xl mt-4 ${phaseColor}`} data-testid="countdown-timer">{mm}:{ss}</div>
        <p className={`mt-2 uppercase tracking-[0.3em] text-sm ${phaseColor}`}>{phaseLabel}</p>
        <div className="mt-6 flex gap-2 justify-center flex-wrap">
          {user && <button onClick={markReady} className="btn-ghost" data-testid="btn-ready"><CheckCircle2 size={14}/>Je suis prêt</button>}
          <button onClick={startCountdown} className="btn-neon" data-testid="start-countdown-btn"><Zap size={14}/>Lancer le décompte serveur</button>
        </div>
      </div>
      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Présence ({presence.length})</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {presence.map(p => (<div key={p.id} className="flex items-center gap-3 p-2 border border-white/5" data-testid={`presence-${p.id}`}>
              <span className="w-2 h-2 rounded-full bg-green-400 shadow-[0_0_8px_#4ade80]"/>
              <span className="font-display flex-1">{p.pseudo}</span>
              <span className="text-xs text-orange-500">LVL {p.level}</span></div>))}
            {presence.length === 0 && <div className="text-white/30 text-sm">Aucun joueur connecté</div>}
          </div>
        </div>
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Événements live</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {liveEvents.map((e,i) => (<div key={i} className="flex gap-3 text-sm" data-testid={`live-event-${i}`}>
              <span className="font-mono-display text-orange-500 text-xs">{e.time}</span><span className="text-white/70">{e.msg}</span></div>))}
            {liveEvents.length === 0 && data.events.map((e,i) => (<div key={i} className="flex gap-3 text-sm text-white/40"><span className="font-mono-display text-xs">{e.time}</span><span>{e.msg}</span></div>))}
          </div>
        </div>
        <div className="glass p-6 flex flex-col">
          <h3 className="font-display text-xl uppercase mb-4">Chat</h3>
          <div className="flex-1 space-y-1 max-h-64 overflow-y-auto mb-3 text-sm">
            {chat.map((c,i) => (<div key={i} data-testid={`chat-msg-${i}`}><span className="text-orange-500 font-display">{c.from}</span> <span className="text-white/70">{c.msg}</span></div>))}
            {chat.length === 0 && <div className="text-white/30">Aucun message</div>}
          </div>
          <div className="flex gap-2">
            <input value={msg} onChange={e=>setMsg(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendChat()} placeholder="Message…" className="flex-1" data-testid="chat-input"/>
            <button onClick={sendChat} className="btn-ghost" data-testid="chat-send">→</button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ============== COUNTDOWN 10→0 ============== */
const Countdown = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [n, setN] = useState(10);
  useEffect(() => {
    if (n < 0) { navigate(`/draw/${id}`); return; }
    const t = setTimeout(() => setN(n - 1), 1000);
    return () => clearTimeout(t);
  }, [n, id, navigate]);
  const intensity = n >= 7 ? 1 : n >= 4 ? 1.4 : n >= 2 ? 1.8 : 2.2;
  return (
    <div className="fixed inset-0 bg-black flex items-center justify-center overflow-hidden" data-testid="countdown-screen">
      <Particles/>
      <div className="absolute inset-0 bg-arena bg-grid scanlines opacity-60"/>
      <button onClick={() => navigate(`/draw/${id}`)} className="absolute top-6 right-6 btn-ghost z-10" data-testid="skip-countdown-btn">Passer →</button>
      <AnimatePresence mode="wait">
        <motion.div key={n} initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: intensity, opacity: 1 }} exit={{ scale: 3, opacity: 0 }}
          transition={{ duration: 0.6 }} className="countdown-digit relative z-10" data-testid={`countdown-${n}`}>
          {n === 0 ? "GO" : n}
        </motion.div>
      </AnimatePresence>
      <div className="absolute bottom-10 text-center w-full">
        <p className="font-display uppercase tracking-[0.5em] text-orange-500 text-sm">Le tournoi commence</p>
      </div>
    </div>
  );
};

/* ============== BRACKET DRAW ============== */
const BracketDraw = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [teams, setTeams] = useState([]);
  const [step, setStep] = useState(0);
  useEffect(() => { axios.get(`${API}/teams`).then(r => setTeams(r.data)); }, []);
  useEffect(() => {
    if (step < 8) { const t = setTimeout(() => setStep(step + 1), 700); return () => clearTimeout(t); }
  }, [step]);
  const matchups = [[teams[0], teams[7]], [teams[3], teams[4]], [teams[1], teams[6]], [teams[2], teams[5]]];
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="bracket-draw">
      <div className="text-center">
        <Badge variant="live">TIRAGE EN COURS</Badge>
        <h1 className="font-display text-5xl uppercase mt-3">Révélation du tableau</h1>
      </div>
      <div className="grid md:grid-cols-2 gap-6 mt-10">
        {matchups.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, x: i%2 ? 50 : -50 }} animate={{ opacity: step > i*2+1 ? 1 : 0, x: 0 }} transition={{ duration: 0.5 }}
            className="glass p-6 relative overflow-hidden" data-testid={`matchup-${i}`}>
            <div className="absolute inset-0 bg-gradient-to-r from-orange-500/10 to-red-500/10"/>
            <div className="relative flex items-center justify-between">
              <div className="flex items-center gap-3"><TeamLogo team={m[0] || teams[0]}/><div><div className="font-display">{m[0]?.name}</div><div className="text-xs text-white/40">ELO {m[0]?.elo}</div></div></div>
              <span className="font-display text-3xl text-orange-500">VS</span>
              <div className="flex items-center gap-3 flex-row-reverse"><TeamLogo team={m[1] || teams[1]}/><div className="text-right"><div className="font-display">{m[1]?.name}</div><div className="text-xs text-white/40">ELO {m[1]?.elo}</div></div></div>
            </div>
          </motion.div>))}
      </div>
      <div className="text-center mt-10">
        <button onClick={() => navigate(`/match/m1`)} className="btn-neon" data-testid="open-match-btn"><Swords size={14}/>Ouvrir mon match</button>
      </div>
    </div>
  );
};

/* ============== MATCH ROOM ============== */
const MatchRoom = () => (
  <div className="max-w-7xl mx-auto px-6 py-10" data-testid="match-room">
    <Badge variant="live">EN COURS</Badge>
    <h1 className="font-display text-4xl uppercase mt-3">Nova Strike vs Pixel Reapers</h1>
    <p className="text-white/50">BO3 • Mirage / Inferno / Anubis</p>
    <div className="glass p-8 mt-6 text-center">
      <div className="grid grid-cols-3 items-center">
        <div><div className="font-display text-2xl">Nova Strike</div><div className="font-display text-7xl text-orange-500 mt-2">13</div></div>
        <div className="text-white/40 font-display uppercase">Round 24 — Mirage</div>
        <div><div className="font-display text-2xl">Pixel Reapers</div><div className="font-display text-7xl text-cyan-neon mt-2">11</div></div>
      </div>
    </div>
    <div className="grid md:grid-cols-2 gap-4 mt-6">
      <div className="glass p-6"><h3 className="font-display uppercase mb-3">Serveur</h3><p className="text-white/60 text-sm">EU-FR-01 • 64 tick • MatchZy 2.4.1</p><p className="text-xs text-white/40 mt-2">connect 185.x.x.x:27015</p></div>
      <div className="glass p-6"><h3 className="font-display uppercase mb-3">Actions arbitre</h3>
        <div className="flex gap-2 flex-wrap">
          <button className="btn-ghost text-xs" data-testid="report-btn"><AlertTriangle size={12}/>Signaler</button>
          <button className="btn-ghost text-xs"><Clock size={12}/>Demander pause</button>
          <button className="btn-ghost text-xs">Soumettre score</button>
        </div></div>
    </div>
  </div>
);

/* ============== PROFILE ============== */
const Profile = () => {
  const { user: currentUser } = useAuth();
  const fallback = { pseudo: "Vortex", country: "FR", level: 47, xp: 8420, xp_next: 10000, elo: 2240, rank_cs2: "Global Elite", kdr: 1.42, role: "AWP", steam_verified: true, reliability: 97 };
  const p = currentUser ? { ...fallback, ...currentUser, xp_next: Math.max(currentUser.xp + 500, 1000) } : fallback;
  const xpPct = (p.xp / p.xp_next) * 100;
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="profile-page">
      <div className="glass p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-orange-500/10 blur-3xl"/>
        <div className="flex items-center gap-6 relative">
          <div className="relative">
            <div className="w-28 h-28 bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center font-display text-5xl font-bold">V</div>
            <div className="absolute -bottom-2 -right-2 bg-black border border-orange-500 px-2 py-0.5 text-xs font-display">LVL {p.level}</div>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-display text-4xl uppercase">{p.pseudo}</h1>
              {p.steam_verified && <Badge variant="verified" testid="steam-verified-badge"><Shield size={12}/>STEAM VÉRIFIÉ</Badge>}
              <span className="text-white/50 text-sm">🇫🇷 {p.country}</span>
            </div>
            <p className="text-white/50 mt-1">{p.role} • Recherche d'équipe</p>
            <div className="mt-4">
              <div className="flex justify-between text-xs text-white/60 mb-1"><span>XP {p.xp}/{p.xp_next}</span><span>Niveau {p.level + 1} dans {p.xp_next - p.xp} XP</span></div>
              <div className="h-2 bg-white/5 overflow-hidden"><div className="h-full bg-gradient-to-r from-orange-500 to-red-500" style={{ width: `${xpPct}%`, boxShadow: "0 0 12px rgba(255,70,0,0.6)" }}/></div>
            </div>
          </div>
        </div>
      </div>

      <SectionTitle sub="Statistiques tierces" title="Stats externes vérifiées"/>
      <div className="grid md:grid-cols-3 gap-4">
        {[
          { label: "Premier Rating", value: "27,420", src: "Valve Premier", state: "verified", color: "text-orange-500" },
          { label: "FACEIT ELO", value: p.elo, src: "CSStats.gg", state: "synced", color: "text-cyan-neon" },
          { label: "K/D Ratio (30j)", value: p.kdr.toFixed(2), src: "CSWAT.CH", state: "synced", color: "text-yellow-neon" },
        ].map((s,i) => (
          <div key={i} className="glass p-6" data-testid={`stat-card-${i}`}>
            <div className="text-xs uppercase tracking-widest text-white/50">{s.label}</div>
            <div className={`font-display text-5xl font-bold mt-2 ${s.color}`}>{s.value}</div>
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5 text-xs">
              <span className="text-white/40">Source : <span className="text-white/70">{s.src}</span></span>
              <Badge variant="verified">{s.state}</Badge>
            </div>
            <div className="text-[10px] text-white/30 mt-2">Synchro : il y a 4 min</div>
          </div>))}
      </div>

      <SectionTitle sub="Récompenses" title="Badges & Trophées"/>
      <div className="flex flex-wrap gap-3">
        {[{icon: Crown, label: "Champion S1", c: "text-yellow-neon"}, {icon: Shield, label: "Steam vérifié", c: "text-cyan-neon"}, {icon: Star, label: "MVP", c: "text-orange-500"}, {icon: Heart, label: "Fair-play", c: "text-pink-400"}, {icon: TrendingUp, label: "Renfort fiable", c: "text-green-400"}, {icon: Award, label: "Vétéran", c: "text-purple-400"}].map((b,i) => (
          <div key={i} className="glass p-4 flex items-center gap-2" data-testid={`badge-${i}`}>
            <b.icon className={b.c} size={20}/><span className="font-display text-sm uppercase">{b.label}</span>
          </div>))}
      </div>
    </div>
  );
};

/* ============== TEAMS ============== */
const TeamsPage = () => {
  const [teams, setTeams] = useState([]);
  useEffect(() => { axios.get(`${API}/teams`).then(r => setTeams(r.data)); }, []);
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="teams-page">
      <h1 className="font-display text-5xl uppercase">Équipes</h1>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {teams.map((t,i) => (
          <div key={t.id} className="glass glass-hover p-6" data-testid={`team-${t.id}`}>
            <div className="flex items-start justify-between"><TeamLogo team={t} size={64}/><span className="font-mono-display text-white/30">#{i+1}</span></div>
            <h3 className="font-display text-2xl mt-3">{t.name}</h3>
            <p className="text-white/40 text-sm">{t.tag} • {t.country}</p>
            <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-white/5 text-center">
              <div><div className="font-display text-orange-500">{t.elo}</div><div className="text-[10px] text-white/40 uppercase">ELO</div></div>
              <div><div className="font-display">{t.level}</div><div className="text-[10px] text-white/40 uppercase">LVL</div></div>
              <div><div className="font-display text-green-400">{t.wins}</div><div className="text-[10px] text-white/40 uppercase">W</div></div>
              <div><div className="font-display text-yellow-neon">{t.trophies}</div><div className="text-[10px] text-white/40 uppercase">🏆</div></div>
            </div>
          </div>))}
      </div>
    </div>
  );
};

/* ============== RANKINGS ============== */
const Rankings = () => {
  const [teams, setTeams] = useState([]);
  const [players, setPlayers] = useState([]);
  useEffect(() => { axios.get(`${API}/teams`).then(r=>setTeams(r.data)); axios.get(`${API}/players`).then(r=>setPlayers(r.data)); }, []);
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="rankings-page">
      <h1 className="font-display text-5xl uppercase">Classements — Saison 1</h1>
      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <div className="glass p-6"><h3 className="font-display text-xl uppercase mb-4">Top équipes</h3>
          {teams.sort((a,b)=>b.elo-a.elo).map((t,i) => (
            <div key={t.id} className="flex items-center gap-3 py-3 border-b border-white/5" data-testid={`rank-team-${i}`}>
              <span className={`font-display text-2xl w-8 ${i<3 ? "text-yellow-neon" : "text-white/30"}`}>{i+1}</span>
              <TeamLogo team={t} size={36}/><span className="flex-1 font-display">{t.name}</span>
              <span className="text-orange-500 font-display">{t.elo}</span>
            </div>))}</div>
        <div className="glass p-6"><h3 className="font-display text-xl uppercase mb-4">Top joueurs</h3>
          {players.sort((a,b)=>b.elo-a.elo).map((p,i) => (
            <div key={p.id} className="flex items-center gap-3 py-3 border-b border-white/5" data-testid={`rank-player-${i}`}>
              <span className={`font-display text-2xl w-8 ${i<3 ? "text-yellow-neon" : "text-white/30"}`}>{i+1}</span>
              <span className="flex-1 font-display">{p.pseudo}{p.steam_verified && <Shield size={12} className="inline ml-2 text-cyan-400"/>}</span>
              <span className="text-cyan-neon font-display">{p.elo}</span>
            </div>))}</div>
      </div>
    </div>
  );
};

/* ============== DUELS 1v1 ============== */
const Duels = () => {
  const { user, token } = useAuth();
  const [balance, setBalance] = useState(null);
  const [duels, setDuels] = useState([]);
  const [form, setForm] = useState({ map: "Mirage", stake: 100 });
  const [busy, setBusy] = useState(false);
  const authH = token ? { Authorization: `Bearer ${token}` } : {};

  const refresh = async () => {
    const ds = await axios.get(`${API}/duels`);
    setDuels(ds.data);
    if (token) {
      try { const b = await axios.get(`${API}/duels/balance`, { headers: authH }); setBalance(b.data.tokens); } catch {}
    }
  };
  useEffect(() => {
    const run = async () => {
      const ds = await axios.get(`${API}/duels`);
      setDuels(ds.data);
      if (token) {
        try {
          const b = await axios.get(`${API}/duels/balance`, { headers: { Authorization: `Bearer ${token}` } });
          setBalance(b.data.tokens);
        } catch {}
      }
    };
    run();
  }, [token]);

  const create = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      await axios.post(`${API}/duels/create`, { map: form.map, stake: parseInt(form.stake) }, { headers: authH });
      await refresh();
    } catch (e2) { alert(e2.response?.data?.detail || "Erreur"); }
    finally { setBusy(false); }
  };
  const accept = async (id) => {
    try { await axios.post(`${API}/duels/${id}/accept`, {}, { headers: authH }); await refresh(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="duels-page">
      <div className="flex items-center gap-3"><Coins className="text-yellow-neon" size={32}/><h1 className="font-display text-5xl uppercase">Duels 1v1</h1></div>
      <p className="text-white/50 mt-2">Mise en jetons virtuels non achetables, sans valeur réelle.</p>
      {user ? (
        <div className="glass p-6 mt-6 flex items-center justify-between">
          <div><div className="text-xs uppercase tracking-widest text-white/40">Votre solde</div>
            <div className="font-display text-4xl text-yellow-neon mt-1" data-testid="duel-balance">⚡ {balance ?? "—"}</div></div>
          <form onSubmit={create} className="flex items-end gap-2">
            <div><label className="text-xs uppercase text-white/40">Map</label>
              <select value={form.map} onChange={e=>setForm({...form,map:e.target.value})} data-testid="duel-map-select">
                {["Mirage","Inferno","Anubis","Nuke","Vertigo","Ancient","Dust2"].map(m=><option key={m}>{m}</option>)}
              </select></div>
            <div><label className="text-xs uppercase text-white/40">Mise (10-5000)</label>
              <input type="number" min={10} max={5000} value={form.stake} onChange={e=>setForm({...form,stake:e.target.value})} className="w-28" data-testid="duel-stake-input"/></div>
            <button disabled={busy} className="btn-neon" data-testid="duel-create-btn"><Swords size={14}/>Créer un défi</button>
          </form>
        </div>
      ) : (
        <div className="glass p-6 mt-6 text-center"><p className="text-white/60">Connectez-vous pour créer ou accepter des duels.</p>
          <Link to="/login" className="btn-neon mt-3" data-testid="duel-login-cta">Se connecter</Link></div>
      )}
      <SectionTitle sub="Défis ouverts" title="Tous les duels en attente"/>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {duels.length === 0 && <div className="glass p-6 text-white/40">Aucun duel ouvert pour le moment.</div>}
        {duels.map(d => (
          <div key={d.id} className="glass glass-hover p-5" data-testid={`duel-${d.id}`}>
            <div className="flex items-center justify-between">
              <div className="font-display text-xl">{d.creator_pseudo}</div>
              <Badge variant="soon">OUVERT</Badge>
            </div>
            <div className="mt-3 text-sm text-white/60">Map : <span className="text-white">{d.map}</span></div>
            <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
              <div><div className="text-xs uppercase text-white/40">Mise</div><div className="font-display text-yellow-neon">⚡ {d.stake}</div></div>
              {user && user.id !== d.creator_id && <button onClick={()=>accept(d.id)} className="btn-neon" data-testid={`accept-duel-${d.id}`}>Accepter</button>}
              {user && user.id === d.creator_id && <span className="text-xs text-white/40">Votre défi</span>}
            </div>
          </div>))}
      </div>
    </div>
  );
};

/* ============== TOURNAMENT STATE MACHINE (admin) ============== */
const TRANSITIONS = { open:["registering","closed"], registering:["starting","open","closed"], starting:["live","closed"], live:["closed"], closed:[] };
const STATE_FR = { open:"Ouvert", registering:"Inscriptions", starting:"Lancement", live:"En direct", closed:"Terminé" };
const TournamentAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [tours, setTours] = useState([]);
  const [busy, setBusy] = useState(false);
  const refresh = () => axios.get(`${API}/tournaments`).then(r => setTours(r.data));
  useEffect(() => { refresh(); }, []);
  const transition = async (id, to) => {
    setBusy(true);
    try { await axios.post(`${API}/tournaments/${id}/transition`, { to }, { headers: authH }); await refresh(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); } finally { setBusy(false); }
  };
  return (
    <div data-testid="tournament-admin">
      <SectionTitle sub="Machine à états" title="Cycle de vie des tournois"/>
      <div className="grid md:grid-cols-2 gap-4">
        {tours.map(t => (
          <div key={t.id} className="glass p-5" data-testid={`tadmin-${t.id}`}>
            <div className="flex items-center justify-between">
              <span className="font-display text-lg uppercase">{t.name}</span>
              <span className="px-3 py-1 font-display text-xs uppercase tracking-widest bg-white/10 text-cyan-neon" data-testid={`tstate-${t.id}`}>{STATE_FR[t.status] || t.status}</span>
            </div>
            <div className="text-xs text-white/40 mt-1">{t.registered}/{t.capacity} inscrits • {t.format}</div>
            {isAdmin && (
              <div className="flex flex-wrap gap-2 mt-3">
                {(TRANSITIONS[t.status] || []).length === 0 && <span className="text-xs text-white/30">Aucune transition disponible</span>}
                {(TRANSITIONS[t.status] || []).map(to => (
                  <button key={to} disabled={busy} onClick={() => transition(t.id, to)} className="btn-ghost text-xs" data-testid={`transition-${t.id}-${to}`}>→ {STATE_FR[to]}</button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

/* ============== CS2 SERVER ORCHESTRATION (RCON + MatchZy) ============== */
const Cs2Panel = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [servers, setServers] = useState([]);
  const [events, setEvents] = useState([]);
  const [form, setForm] = useState({ name:"", host:"", port:27015, rcon_password:"" });
  const [selected, setSelected] = useState(null);
  const [cmd, setCmd] = useState("status");
  const [output, setOutput] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const r = await axios.get(`${API}/cs2/servers`); setServers(r.data);
    const e = await axios.get(`${API}/cs2/events?limit=10`); setEvents(e.data);
  };
  useEffect(() => { refresh(); }, []);

  const addServer = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await axios.post(`${API}/cs2/servers`, { ...form, port: parseInt(form.port) }, { headers: authH });
      setForm({ name:"", host:"", port:27015, rcon_password:"" }); await refresh(); }
    catch (e2) { alert(e2.response?.data?.detail || "Erreur"); } finally { setBusy(false); }
  };
  const del = async (id) => { if (!window.confirm("Supprimer ce serveur ?")) return;
    try { await axios.delete(`${API}/cs2/servers/${id}`, { headers: authH }); if (selected===id) setSelected(null); await refresh(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); } };
  const ping = async (id) => { setBusy(true); setSelected(id); setOutput("Connexion RCON…");
    try { const r = await axios.post(`${API}/cs2/servers/${id}/ping`, {}, { headers: authH }); setOutput(r.data.output); await refresh(); }
    catch (e) { setOutput(e.response?.data?.detail || "Erreur RCON"); } finally { setBusy(false); } };
  const runCmd = async () => { if (!selected) { alert("Sélectionnez un serveur via Ping d'abord."); return; } setBusy(true); setOutput("Exécution…");
    try { const r = await axios.post(`${API}/cs2/servers/${selected}/rcon`, { command: cmd }, { headers: authH }); setOutput(r.data.output); }
    catch (e) { setOutput(e.response?.data?.detail || "Erreur RCON"); } finally { setBusy(false); } };

  return (
    <div data-testid="cs2-panel">
      <SectionTitle sub="Pilotage CS2 (RCON live)" title="Serveurs de match"/>
      {isAdmin && (
        <form onSubmit={addServer} className="glass p-6 grid md:grid-cols-5 gap-3 items-end mb-4" data-testid="cs2-add-form">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Nom</label>
            <input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="EU-FR-01" required data-testid="cs2-name-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Hôte / IP</label>
            <input value={form.host} onChange={e=>setForm({...form,host:e.target.value})} placeholder="cs2.example.net" required data-testid="cs2-host-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Port</label>
            <input type="number" value={form.port} onChange={e=>setForm({...form,port:e.target.value})} required data-testid="cs2-port-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Mot de passe RCON</label>
            <input type="password" value={form.rcon_password} onChange={e=>setForm({...form,rcon_password:e.target.value})} required data-testid="cs2-rcon-input"/></div>
          <button disabled={busy} className="btn-neon" data-testid="cs2-add-btn"><Plus size={14}/>Ajouter</button>
        </form>
      )}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {servers.length === 0 && <div className="glass p-6 text-white/40">Aucun serveur CS2 enregistré.</div>}
        {servers.map(s => (
          <div key={s.id} className={`glass p-5 ${selected===s.id ? "ring-1 ring-cyan-neon" : ""}`} data-testid={`cs2-server-${s.id}`}>
            <div className="flex items-center justify-between">
              <span className="font-display text-lg flex items-center gap-2"><Server size={16}/>{s.name}</span>
              <span className={`w-2 h-2 rounded-full ${s.status==="online"||s.status==="live" ? "bg-green-400 shadow-[0_0_6px_#4ade80]" : "bg-yellow-400"}`}/>
            </div>
            <div className="text-xs text-white/40 mt-2 font-mono-display">{s.host}:{s.port}</div>
            <div className="text-xs text-white/60 mt-1">Statut : {s.status}</div>
            {isAdmin && (
              <div className="flex flex-wrap gap-2 mt-4">
                <button disabled={busy} onClick={()=>ping(s.id)} className="btn-ghost text-xs" data-testid={`cs2-ping-${s.id}`}><RefreshCw size={12}/>Ping / Sélectionner</button>
                <button onClick={()=>del(s.id)} className="btn-ghost text-xs text-red-400" data-testid={`cs2-del-${s.id}`}><Trash2 size={12}/></button>
              </div>
            )}
          </div>
        ))}
      </div>

      {isAdmin && (
        <div className="glass p-6 mt-4" data-testid="cs2-console">
          <h3 className="font-display text-sm uppercase tracking-widest text-white/60 flex items-center gap-2"><Terminal size={14}/>Console RCON {selected ? "" : "(sélectionnez un serveur)"}</h3>
          <div className="flex gap-2 mt-3">
            <input value={cmd} onChange={e=>setCmd(e.target.value)} placeholder="status" className="flex-1 font-mono-display" data-testid="cs2-cmd-input"/>
            <button disabled={busy || !selected} onClick={runCmd} className="btn-neon" data-testid="cs2-run-btn"><Play size={14}/>Exécuter</button>
          </div>
          <pre className="mt-3 p-3 bg-black/50 border border-white/5 text-xs text-cyan-neon whitespace-pre-wrap max-h-64 overflow-auto font-mono-display" data-testid="cs2-output">{output || "— sortie RCON —"}</pre>
        </div>
      )}

      <div className="glass p-6 mt-4" data-testid="matchzy-events">
        <h3 className="font-display text-sm uppercase tracking-widest text-white/60">Événements MatchZy récents</h3>
        <div className="mt-3 space-y-2">
          {events.length === 0 && <div className="text-white/30 text-sm">Aucun événement MatchZy reçu.</div>}
          {events.map(ev => (
            <div key={ev.id} className="flex items-center gap-3 text-xs border border-white/5 p-2" data-testid={`matchzy-event-${ev.id}`}>
              <span className="font-display text-yellow-neon uppercase">{ev.event}</span>
              <span className="text-white/40">match {ev.matchid || "—"}</span>
              <span className="text-white/30 ml-auto">{new Date(ev.received_at).toLocaleTimeString("fr-FR")}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ============== ADMIN ============== */
const Admin = () => {
  const { user, token } = useAuth();
  const [cards, setCards] = useState([]);
  const [form, setForm] = useState({ target_user_id: "", severity: "yellow", reason: "" });
  const [busy, setBusy] = useState(false);
  const authH = token ? { Authorization: `Bearer ${token}` } : {};

  const refresh = async () => {
    const r = await axios.get(`${API}/cards?status_f=active`);
    setCards(r.data);
  };
  useEffect(() => { refresh(); }, []);

  const issue = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      await axios.post(`${API}/cards`, form, { headers: authH });
      setForm({ target_user_id: "", severity: "yellow", reason: "" });
      await refresh();
    } catch (e2) { alert(e2.response?.data?.detail || "Erreur"); }
    finally { setBusy(false); }
  };
  const revoke = async (id) => {
    try { await axios.post(`${API}/cards/${id}/revoke`, {}, { headers: authH }); await refresh(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); }
  };

  const yellows = cards.filter(c => c.severity === "yellow").length;
  const reds = cards.filter(c => c.severity === "red").length;
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="admin-page">
      <h1 className="font-display text-5xl uppercase">Tableau de bord — Organisateur</h1>
      <div className="grid md:grid-cols-4 gap-4 mt-6">
        {[{l:"Tournois actifs",v:5,c:"text-orange-500"},{l:"Joueurs en ligne",v:487,c:"text-cyan-neon"},{l:"Cartons jaunes",v:yellows,c:"text-yellow-neon"},{l:"Cartons rouges",v:reds,c:"text-red-500"}].map((s,i) => (
          <div key={s.l} className="glass p-6" data-testid={`admin-stat-${i}`}>
            <div className="text-xs uppercase tracking-widest text-white/40">{s.l}</div>
            <div className={`font-display text-5xl font-bold mt-2 ${s.c}`}>{s.v}</div>
          </div>))}
      </div>

      <SectionTitle sub="Modération en direct" title="Émettre un carton"/>
      {!user ? <div className="glass p-6 text-white/60">Connectez-vous comme modérateur pour émettre des cartons.</div> : (
        <form onSubmit={issue} className="glass p-6 grid md:grid-cols-4 gap-3 items-end">
          <div><label className="text-xs uppercase tracking-widest text-white/40">User ID cible</label>
            <input value={form.target_user_id} onChange={e=>setForm({...form,target_user_id:e.target.value})} placeholder="UUID utilisateur" required data-testid="card-target-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Sévérité</label>
            <select value={form.severity} onChange={e=>setForm({...form,severity:e.target.value})} data-testid="card-severity-select">
              <option value="yellow">🟨 Jaune</option><option value="red">🟥 Rouge</option>
            </select></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Raison</label>
            <input value={form.reason} onChange={e=>setForm({...form,reason:e.target.value})} placeholder="Motif détaillé" minLength={3} required data-testid="card-reason-input"/></div>
          <button disabled={busy} className="btn-neon" data-testid="card-issue-btn"><AlertTriangle size={14}/>Émettre</button>
        </form>
      )}

      <SectionTitle sub="Cartons actifs" title={`${cards.length} carton(s) en cours`}/>
      <div className="grid md:grid-cols-3 gap-4">
        {cards.length === 0 && <div className="glass p-6 text-white/40">Aucun carton actif.</div>}
        {cards.map((c) => (
          <div key={c.id} className="glass p-5" data-testid={`card-case-${c.id}`}>
            <div className="flex items-center justify-between">
              <span className="font-display text-lg">{c.target_pseudo}</span>
              <div className={`px-3 py-1 font-display text-xs uppercase tracking-widest ${c.severity === "red" ? "bg-red-600 text-white" : "bg-yellow-500 text-black"}`}>
                {c.severity === "red" ? "🟥 ROUGE" : "🟨 JAUNE"} {c.auto && "(auto)"}
              </div>
            </div>
            <p className="text-sm text-white/60 mt-3">{c.reason}</p>
            <p className="text-xs text-white/30 mt-1">Émis par {c.issuer_pseudo} • {new Date(c.created_at).toLocaleString("fr-FR")}</p>
            {user && (
              <div className="flex gap-2 mt-4">
                <button onClick={()=>revoke(c.id)} className="btn-ghost text-xs" data-testid={`revoke-card-${c.id}`}>Lever le carton</button>
              </div>
            )}
          </div>))}
      </div>

      <TournamentAdmin/>
      <Cs2Panel/>
    </div>
  );
};

/* ============== DONATIONS ============== */
const Donate = () => {
  const [kind, setKind] = useState("one_time");
  const [amount, setAmount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const navigate = useNavigate();
  // Detect session_id in URL → poll status
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const sid = sp.get("session_id");
    const cancelled = sp.get("cancelled");
    if (cancelled) setStatus({ payment_status: "cancelled" });
    if (sid) {
      let attempts = 0;
      const poll = async () => {
        try {
          const r = await axios.get(`${API}/donations/status/${sid}`);
          setStatus(r.data);
          if (r.data.payment_status !== "paid" && attempts < 8) { attempts++; setTimeout(poll, 2000); }
        } catch (e) { setStatus({ payment_status: "error", err: e.message }); }
      };
      poll();
    }
  }, []);
  const submit = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/donations/checkout-session`, { amount, kind, origin: window.location.origin });
      window.location.href = r.data.url; // Redirect to Stripe Checkout
    } catch (e) {
      alert("Erreur Stripe: " + (e.response?.data?.detail || e.message));
      setBusy(false);
    }
  };
  return (
    <div className="max-w-3xl mx-auto px-6 py-10" data-testid="donate-page">
      <div className="flex items-center gap-3"><Heart className="text-red-500" size={32}/><h1 className="font-display text-5xl uppercase">Soutenir la plateforme</h1></div>
      <p className="text-white/50 mt-2">Le soutien financier est <span className="text-white">facultatif</span> et n'accorde <span className="text-white">aucun avantage compétitif</span>.</p>
      {status && (
        <div className="glass p-6 mt-6 border border-orange-500/30" data-testid="payment-status">
          <h3 className="font-display uppercase tracking-widest">État du paiement</h3>
          <div className="mt-2 text-sm">
            {status.payment_status === "paid" && <div className="text-green-400 flex items-center gap-2"><CheckCircle2 size={18}/>Paiement confirmé — merci pour votre soutien ! ({(status.amount_total/100).toFixed(2)} {status.currency?.toUpperCase()})</div>}
            {status.payment_status === "unpaid" && <div className="text-yellow-neon">Paiement en attente de confirmation…</div>}
            {status.payment_status === "cancelled" && <div className="text-white/60">Paiement annulé</div>}
            {status.payment_status === "error" && <div className="text-red-400">Erreur — {status.err}</div>}
          </div>
        </div>
      )}
      <div className="glass p-8 mt-6">
        <h3 className="font-display uppercase tracking-widest text-sm text-white/60">Type de soutien</h3>
        <div className="flex gap-2 mt-3">
          {[{k:"one_time",l:"Ponctuel"},{k:"monthly",l:"Mensuel"}].map(o => (
            <button key={o.k} onClick={()=>setKind(o.k)} data-testid={`don-kind-${o.k}`}
              className={`px-6 py-2 font-display uppercase text-sm tracking-widest ${kind===o.k?"bg-orange-500 text-black":"border border-white/10"}`}>{o.l}</button>))}
        </div>
        <h3 className="font-display uppercase tracking-widest text-sm text-white/60 mt-6">Montant (€)</h3>
        <div className="grid grid-cols-4 gap-2 mt-3">
          {[1,2,3,4,5,10,20,50].map(a => (
            <button key={a} onClick={()=>setAmount(a)} data-testid={`don-amount-${a}`}
              className={`py-3 font-display text-xl ${amount===a?"bg-orange-500 text-black":"border border-white/10 hover:border-orange-500"}`}>{a} €</button>))}
        </div>
        <button onClick={submit} disabled={busy} className="btn-neon w-full mt-6" data-testid="donate-stripe-btn">
          {busy?"Redirection…":`💳 Payer ${amount}€ avec Stripe`}
        </button>
        <p className="text-xs text-white/30 mt-4">Paiement sécurisé Stripe en mode TEST. Carte test : 4242 4242 4242 4242, n'importe quelle date future, CVC 123.</p>
      </div>
    </div>
  );
};

/* ============== LOGIN / REGISTER ============== */
const AuthZone = () => {
  const { user, logout } = useAuth();
  if (!user) return <Link to="/login" className="btn-neon" data-testid="nav-login-btn">Connexion</Link>;
  return (
    <div className="flex items-center gap-2">
      <Link to="/profile" className="flex items-center gap-2 px-3 py-2 border border-white/10 hover:border-orange-500" data-testid="nav-user-chip">
        <div className="w-7 h-7 bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center font-display font-bold text-sm">{user.pseudo[0]}</div>
        <span className="font-display text-sm hidden md:block">{user.pseudo}</span>
        <span className="text-xs text-orange-500 hidden md:block">LVL {user.level}</span>
      </Link>
      <button onClick={logout} className="btn-ghost" data-testid="nav-logout-btn" title="Déconnexion"><LogOut size={14}/></button>
    </div>
  );
};

const Login = () => {
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ pseudo: "", email: "", password: "", country: "FR" });
  const [err, setErr] = useState(""); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) navigate("/profile"); }, [user, navigate]);
  const handleSteam = () => { window.location.href = `${API}/auth/steam/login`; };
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setMsg(""); setBusy(true);
    try {
      if (mode === "forgot") {
        const r = await axios.post(`${API}/auth/forgot-password`, { email: form.email });
        setMsg(r.data.message);
      } else if (mode === "login") { await login(form.email, form.password); navigate("/profile"); }
      else { await register(form.pseudo, form.email, form.password, form.country); navigate("/profile"); }
    } catch (e2) { setErr(e2.response?.data?.detail || "Erreur"); }
    finally { setBusy(false); }
  };
  return (
    <div className="min-h-[80vh] flex items-center justify-center px-6 py-10" data-testid="login-page">
      <div className="glass p-10 w-full max-w-md">
        <div className="text-center"><Logo size={48}/></div>
        <div className="flex gap-2 mt-6">
          <button onClick={() => setMode("login")} data-testid="tab-login"
            className={`flex-1 py-2 font-display uppercase text-sm tracking-widest ${mode==="login"?"bg-orange-500 text-black":"border border-white/10"}`}>Connexion</button>
          <button onClick={() => setMode("register")} data-testid="tab-register"
            className={`flex-1 py-2 font-display uppercase text-sm tracking-widest ${mode==="register"?"bg-orange-500 text-black":"border border-white/10"}`}>Inscription</button>
        </div>
        <button onClick={handleSteam} className="w-full mt-6 py-4 bg-[#171a21] hover:bg-[#1f242c] border border-white/10 flex items-center justify-center gap-3 font-display uppercase tracking-widest text-sm" data-testid="steam-login-btn">
          <Gamepad2 size={20} className="text-cyan-400"/>Se connecter avec Steam
        </button>
        <div className="flex items-center gap-3 my-6"><div className="h-px bg-white/10 flex-1"/><span className="text-xs uppercase tracking-widest text-white/30">ou</span><div className="h-px bg-white/10 flex-1"/></div>
        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (<input className="w-full" placeholder="Pseudo (min 3)" value={form.pseudo} onChange={e=>setForm({...form,pseudo:e.target.value})} required minLength={3} data-testid="register-pseudo"/>)}
          <input className="w-full" type="email" placeholder="Email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} required data-testid="login-email"/>
          {mode !== "forgot" && (<input className="w-full" type="password" placeholder="Mot de passe (min 8)" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} required minLength={8} data-testid="login-password"/>)}
          {err && <div className="text-red-400 text-sm" data-testid="auth-error">{err}</div>}
          {msg && <div className="text-cyan-neon text-sm" data-testid="auth-msg">{msg}</div>}
          <button type="submit" disabled={busy} className="btn-neon w-full" data-testid="login-submit">{busy?"…":(mode==="forgot"?"Envoyer le lien":mode==="login"?"Se connecter":"Créer mon compte")}</button>
        </form>
        {mode === "login" && <button onClick={()=>{setMode("forgot");setErr("");setMsg("");}} className="text-xs text-white/50 hover:text-cyan-neon mt-4 block mx-auto" data-testid="forgot-password-link">Mot de passe oublié ?</button>}
        {mode === "forgot" && <button onClick={()=>{setMode("login");setErr("");setMsg("");}} className="text-xs text-white/50 hover:text-cyan-neon mt-4 block mx-auto" data-testid="back-to-login-link">← Retour à la connexion</button>}
      </div>
    </div>
  );
};

const SteamComplete = () => {
  const { token: ctxToken } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const tok = sp.get("token");
    if (tok) {
      localStorage.setItem("ru_token", tok);
      window.location.href = "/profile"; // Force reload with new token
    }
  }, []);
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-6" data-testid="steam-complete">
      <div className="glass p-10 text-center">
        <CheckCircle2 className="text-cyan-400 mx-auto" size={64}/>
        <h1 className="font-display text-3xl uppercase mt-4">Steam vérifié</h1>
        <p className="text-white/50 mt-2">SteamID64 lié — connexion en cours…</p>
      </div>
    </div>
  );
};

const Generic = ({ title, children }) => (
  <div className="max-w-4xl mx-auto px-6 py-12" data-testid={`generic-${title.toLowerCase()}`}>
    <h1 className="font-display text-5xl uppercase">{title}</h1>
    <div className="glass p-8 mt-6 text-white/70 leading-relaxed">{children}</div>
  </div>
);

/* ============== LIVE MATCHES ============== */
const LiveMatches = () => {
  const [matches, setMatches] = useState([]);
  useEffect(() => {
    const load = () => axios.get(`${API}/matches/live`).then(r => setMatches(r.data)).catch(() => {});
    load(); const iv = setInterval(load, 5000); return () => clearInterval(iv);
  }, []);
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="live-matches-page">
      <h1 className="font-display text-5xl uppercase tracking-tight">Matchs en direct</h1>
      <p className="text-white/50 mt-2">Scores en temps réel alimentés par MatchZy — actualisation automatique toutes les 5s.</p>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {matches.length === 0 && <div className="glass p-6 text-white/40" data-testid="no-live">Aucun match en direct pour le moment.</div>}
        {matches.map(m => (
          <div key={m.matchid} className="glass p-5" data-testid={`live-match-${m.matchid}`}>
            <div className="flex items-center justify-between">
              <Badge variant="live">EN DIRECT</Badge>
              <span className="text-xs text-white/40">{m.map_name}</span>
            </div>
            <div className="mt-4 flex items-center justify-between gap-2">
              <span className="font-display text-base flex-1 truncate">{m.team1_name}</span>
              <span className="font-display text-2xl text-cyan-neon" data-testid={`live-score-${m.matchid}`}>{m.team1_score} : {m.team2_score}</span>
              <span className="font-display text-base flex-1 truncate text-right">{m.team2_name}</span>
            </div>
            {m.server && <div className="text-xs text-white/30 mt-3">Serveur {m.server}</div>}
            <div className="text-xs text-white/30 mt-1">{m.events} événements • dernier : {m.last_event}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ============== RESET PASSWORD ============== */
const ResetPassword = () => {
  const navigate = useNavigate();
  const [pw, setPw] = useState(""); const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const token = new URLSearchParams(window.location.search).get("token");
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { const r = await axios.post(`${API}/auth/reset-password`, { token, new_password: pw }); setMsg(r.data.message); setTimeout(() => navigate("/login"), 2200); }
    catch (e2) { setErr(e2.response?.data?.detail || "Erreur"); } finally { setBusy(false); }
  };
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6 py-10" data-testid="reset-password-page">
      <div className="glass p-10 w-full max-w-md">
        <div className="text-center"><Logo size={44}/></div>
        <h1 className="font-display text-2xl uppercase mt-6 text-center">Nouveau mot de passe</h1>
        {!token ? <p className="text-red-400 text-sm mt-4 text-center">Lien invalide (token manquant).</p> : (
          <form onSubmit={submit} className="space-y-3 mt-6">
            <input className="w-full" type="password" placeholder="Nouveau mot de passe (min 8)" value={pw} onChange={e=>setPw(e.target.value)} required minLength={8} data-testid="reset-password-input"/>
            {err && <div className="text-red-400 text-sm" data-testid="reset-error">{err}</div>}
            {msg && <div className="text-cyan-neon text-sm" data-testid="reset-msg">{msg}</div>}
            <button type="submit" disabled={busy} className="btn-neon w-full" data-testid="reset-submit">{busy?"…":"Réinitialiser"}</button>
          </form>
        )}
      </div>
    </div>
  );
};

/* ============== APP ROOT ============== */
function App() {
  return (
    <AuthProvider>
    <BrowserRouter>
      <NavBar/>
      <Routes>
        <Route path="/" element={<Home/>}/>
        <Route path="/tournaments" element={<TournamentsList/>}/>
        <Route path="/tournament/:id" element={<TournamentDetail/>}/>
        <Route path="/waiting-room/:id" element={<WaitingRoom/>}/>
        <Route path="/countdown/:id" element={<Countdown/>}/>
        <Route path="/draw/:id" element={<BracketDraw/>}/>
        <Route path="/match/:id" element={<MatchRoom/>}/>
        <Route path="/profile" element={<Profile/>}/>
        <Route path="/teams" element={<TeamsPage/>}/>
        <Route path="/rankings" element={<Rankings/>}/>
        <Route path="/duels" element={<Duels/>}/>
        <Route path="/live" element={<LiveMatches/>}/>
        <Route path="/admin" element={<Admin/>}/>
        <Route path="/donate" element={<Donate/>}/>
        <Route path="/login" element={<Login/>}/>
        <Route path="/reset-password" element={<ResetPassword/>}/>
        <Route path="/auth/steam/complete" element={<SteamComplete/>}/>
        <Route path="/faq" element={<Generic title="FAQ"><p>Toutes les questions fréquentes concernant la plateforme, les tournois, le système de renforts et les sanctions.</p></Generic>}/>
        <Route path="/legal" element={<Generic title="Mentions légales"><p>ReadyUp Arena est une plateforme indépendante de tournois e-sport. Non affiliée, sponsorisée ou approuvée par Valve Corporation. Counter-Strike 2 est une marque déposée de Valve Corporation.</p></Generic>}/>
      </Routes>
      <Footer/>
    </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
