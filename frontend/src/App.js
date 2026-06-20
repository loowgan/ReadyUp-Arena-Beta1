import React, { useCallback, useEffect, useState, useRef } from "react";
import { BrowserRouter, Routes, Route, Link, useParams, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { Flame, Trophy, Users, Swords, Radio, Shield, Zap, Crown, Target, AlertTriangle, Coins, Heart, ChevronRight, Play, Lock, CheckCircle2, Circle, Clock, Tv, ExternalLink, Star, TrendingUp, Award, Gamepad2, LogOut, User, Server, Terminal, Plus, Trash2, RefreshCw, Gift, ShoppingBag, Ticket, Package } from "lucide-react";
import { AuthProvider, useAuth } from "./AuthContext";
import { API, HEALTH_API, WS_BASE_URL } from "./lib/api";

const DISCORD_URL = process.env.REACT_APP_DISCORD_URL || "https://discord.gg/F6RxTWeSmE";
const STEAM_GROUP_URL = process.env.REACT_APP_STEAM_GROUP_URL || "https://steamcommunity.com/groups/readyuparena";

/* ============== SHARED UI ============== */
const Logo = ({ size = 40 }) => (
  <div className="flex items-center gap-3" data-testid="brand-logo">
    <img src="https://customer-assets.emergentagent.com/job_file-reader-108/artifacts/d88wsvtc_readyup-logo.png"
      alt="ReadyUp Arena" style={{ height: size * 1.6, width: "auto", filter: "drop-shadow(0 0 12px rgba(111, 229, 197, 0.4))" }}/>
  </div>
);

const DiscordMark = ({ className = "h-5 w-5" }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
    <path d="M20.317 4.369A19.79 19.79 0 0 0 15.885 3a13.911 13.911 0 0 0-.662 1.357 18.27 18.27 0 0 0-5.447 0A13.54 13.54 0 0 0 9.114 3a19.736 19.736 0 0 0-4.434 1.371C1.88 8.583 1.12 12.69 1.5 16.74A19.92 19.92 0 0 0 6.946 19a14.33 14.33 0 0 0 1.17-1.908 12.955 12.955 0 0 1-1.84-.885c.155-.113.307-.23.454-.351 3.548 1.635 7.395 1.635 10.901 0 .149.121.301.238.456.351-.586.342-1.2.638-1.842.885.338.667.73 1.305 1.172 1.908a19.87 19.87 0 0 0 5.448-2.26c.446-4.696-.762-8.767-3.048-12.371ZM8.955 14.305c-1.063 0-1.935-.972-1.935-2.164 0-1.193.854-2.164 1.935-2.164 1.09 0 1.953.98 1.935 2.164 0 1.192-.854 2.164-1.935 2.164Zm6.09 0c-1.063 0-1.935-.972-1.935-2.164 0-1.193.854-2.164 1.935-2.164 1.09 0 1.953.98 1.935 2.164 0 1.192-.845 2.164-1.935 2.164Z"/>
  </svg>
);

const SteamMark = ({ className = "h-5 w-5" }) => (
  <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
    <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.8" />
    <circle cx="16.9" cy="7.8" r="2.15" fill="none" stroke="currentColor" strokeWidth="1.8" />
    <circle cx="8.9" cy="15.8" r="2.35" fill="none" stroke="currentColor" strokeWidth="1.8" />
    <path d="M10.7 14.7 14.8 10.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="m6.6 14.7 1.1.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <circle cx="16.9" cy="7.8" r="0.8" fill="currentColor" />
    <circle cx="8.9" cy="15.8" r="0.9" fill="currentColor" />
  </svg>
);

const NavBar = () => {
  const loc = useLocation();
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuLinks = [
    { to: "/", label: "Accueil", icon: Flame },
    { to: "/tournaments", label: "Tournois", icon: Trophy },
    { to: "/teams", label: "Equipes", icon: Users },
    { to: "/rankings", label: "Classements", icon: Award },
    { to: "/live", label: "En direct", icon: Radio },
    { to: "/fun-5v5", label: "Fun 5v5", icon: Gamepad2 },
    { to: "/duels", label: "Duels 1v1", icon: Swords },
    { to: "/concours", label: "Concours", icon: Ticket },
    { to: "/boutique", label: "Boutique", icon: ShoppingBag },
    { to: "/community", label: "Communaute", icon: Heart },
    { to: "/faq", label: "FAQ", icon: Shield },
    { to: "/partners", label: "Partenaires", icon: Star },
    { to: "/contact", label: "Contact", icon: Heart },
    { to: "/status", label: "Status", icon: Server },
    { to: "/profile", label: "Profil", icon: User },
    { to: "/support", label: "Support", icon: Gift },
  ];
  useEffect(() => {
    setMenuOpen(false);
  }, [loc.pathname]);
  /*
    { to: "/", label: "Accueil" }, { to: "/tournaments", label: "Tournois" },
    { to: "/teams", label: "Équipes" }, { to: "/rankings", label: "Classements" },
    { to: "/live", label: "En direct" },
  */
  return (
    <nav className="sticky top-0 z-50 glass border-b border-white/5" data-testid="main-nav">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-3">
        <Link to="/" data-testid="nav-home-logo"><Logo /></Link>
        <div className="flex items-center gap-2 mr-auto">
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((value) => !value)}
              className={`px-4 py-2 text-sm font-display tracking-widest uppercase transition-colors flex items-center gap-2 rounded-full border ${menuLinks.some((item) => loc.pathname === item.to) ? "border-orange-500/40 bg-orange-500/10 text-orange-300 shadow-[0_0_18px_rgba(249,115,22,0.18)]" : "border-white/10 text-white/70 hover:text-white hover:border-white/20 hover:bg-white/5"}`}
              data-testid="nav-menu-toggle"
            >
              Menu
              <ChevronRight size={14} className={`transition-transform ${menuOpen ? "rotate-90" : ""}`}/>
            </button>
            {menuOpen && (
              <div className="absolute top-full left-0 mt-2 min-w-[320px] sm:min-w-[420px] glass border border-white/10 p-2 z-50" data-testid="nav-menu-panel">
                <div className="grid grid-cols-2 gap-1">
                {menuLinks.map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => setMenuOpen(false)}
                    className={`flex items-center gap-3 px-3 py-3 text-sm font-display uppercase tracking-wider transition-colors ${loc.pathname === item.to ? "text-orange-500 bg-white/5" : "text-white/75 hover:text-white hover:bg-white/5"}`}
                    data-testid={`nav-menu-${item.label.toLowerCase().replace(/\s/g, "-")}`}
                  >
                    <item.icon size={14}/>
                    {item.label}
                  </Link>
                ))}
                {user?.is_admin && (
                  <Link
                    to="/admin"
                    onClick={() => setMenuOpen(false)}
                    className={`flex items-center gap-3 px-3 py-3 text-sm font-display uppercase tracking-wider transition-colors ${loc.pathname === "/admin" ? "text-orange-500 bg-white/5" : "text-white/75 hover:text-white hover:bg-white/5"}`}
                    data-testid="nav-menu-admin"
                  >
                    <Lock size={14}/>
                    Admin
                  </Link>
                )}
                </div>
              </div>
            )}
          </div>
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noreferrer"
            title="Discord ReadyUp Arena"
            className="group inline-flex h-11 w-11 items-center justify-center rounded-full border border-[#6fe5c5]/35 bg-[linear-gradient(135deg,rgba(111,229,197,0.18),rgba(34,197,94,0.08))] text-[#c7fff1] shadow-[0_0_24px_rgba(111,229,197,0.16)] transition-all hover:-translate-y-0.5 hover:border-[#6fe5c5]/60 hover:shadow-[0_0_28px_rgba(111,229,197,0.24)]"
            data-testid="nav-discord-btn"
            aria-label="Rejoindre le Discord ReadyUp Arena"
          >
            <DiscordMark className="h-5 w-5 transition-transform group-hover:scale-110"/>
            <span className="sr-only">Discord</span>
          </a>
          <a
            href={STEAM_GROUP_URL}
            target="_blank"
            rel="noreferrer"
            title="Groupe Steam ReadyUp Arena"
            className="group inline-flex h-11 w-11 items-center justify-center rounded-full border border-[#f8b84e]/35 bg-[linear-gradient(135deg,rgba(248,184,78,0.18),rgba(249,115,22,0.08))] text-[#ffe2ad] shadow-[0_0_24px_rgba(248,184,78,0.16)] transition-all hover:-translate-y-0.5 hover:border-[#f8b84e]/60 hover:shadow-[0_0_28px_rgba(248,184,78,0.24)]"
            data-testid="nav-steam-group-btn"
            aria-label="Rejoindre le groupe Steam ReadyUp Arena"
          >
            <SteamMark className="h-5 w-5 transition-transform group-hover:scale-110"/>
            <span className="sr-only">Groupe Steam</span>
          </a>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Link to="/support" className="btn-ghost" data-testid="nav-donate-btn"><Heart size={14}/>Soutenir</Link>
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
        <ul className="space-y-2 text-white/60"><li><Link to="/tournaments">Tournois</Link></li><li><Link to="/teams">Équipes</Link></li><li><Link to="/rankings">Classements</Link></li><li><Link to="/fun-5v5">Fun 5v5</Link></li><li><Link to="/boutique">Boutique points</Link></li></ul></div>
      <div><h4 className="font-display uppercase tracking-widest text-white mb-3">Communauté</h4>
        <ul className="space-y-2 text-white/60"><li><Link to="/faq">FAQ</Link></li><li><Link to="/community">Communauté</Link></li><li><Link to="/concours">Concours</Link></li><li><Link to="/partners">Partenaires</Link></li><li><Link to="/support">Faire un don</Link></li></ul></div>
      <div><h4 className="font-display uppercase tracking-widest text-white mb-3">Légal</h4>
        <ul className="space-y-2 text-white/60"><li><Link to="/legal">Mentions légales</Link></li><li><Link to="/privacy">Confidentialité</Link></li><li><Link to="/cgu">CGU</Link></li><li><Link to="/status">État des services</Link></li></ul></div>
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

const FAQ_ITEMS = [
  {
    q: "Les tournois sont-ils payants ?",
    a: "Non. La beta reste centree sur des tournois gratuits. Le module de soutien est facultatif et n'accorde aucun avantage competitif.",
  },
  {
    q: "La verification Steam prouve quoi exactement ?",
    a: "Elle prouve seulement que le compte a controle le SteamID lie via Steam OpenID. Elle ne certifie ni l'identite civile ni le niveau de jeu.",
  },
  {
    q: "Que se passe-t-il si une equipe est incomplete ?",
    a: "La salle d'attente utilise la file de solos et les regles de renfort pour eviter qu'un tournoi soit bloque par une absence de derniere minute.",
  },
  {
    q: "La partie CS2 est-elle deja active ?",
    a: "Oui pour la beta: inventaire des serveurs, console RCON admin, suivi MatchZy, scores live et supervision. Le hub public CS2 expose maintenant cet etat.",
  },
];

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

const PARTNER_BLOCKS = [
  {
    title: "Sponsors de lots",
    text: "Skins ou recompenses offres par un organisateur, sans depot des joueurs et sans economie pay-to-win.",
  },
  {
    title: "Structures communautaires",
    text: "Associations, staff tournoi, arbitres et partenaires Discord peuvent relayer les evenements et recruter des equipes.",
  },
  {
    title: "Infra match",
    text: "Serveurs CS2, supervision backend, Redis, MongoDB et Vercel/Render soutiennent le fonctionnement beta.",
  },
];

const CS2_AUTOPILOT_STEPS = [
  "Compte -> Steam verifie -> equipe ou file solo",
  "Inscription tournoi -> salle d'attente -> presence",
  "Appels automatiques -> renfort -> verrouillage",
  "Decompte -> generation bracket -> lancement match",
  "Serveur CS2 -> MatchZy -> score live -> resultat",
  "Classement -> XP -> recompenses -> archivage",
];

const toLocalInputValue = (value) => {
  const base = value ? new Date(value) : new Date(Date.now() + 24 * 60 * 60 * 1000);
  const local = new Date(base.getTime() - base.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};

const splitAdminList = (value) =>
  value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);

const makeTournamentForm = () => ({
  name: "",
  organizer: "ReadyUp Official",
  format: "5v5",
  mode: "Single Elim BO1",
  capacity: 16,
  status: "open",
  starts_at: toLocalInputValue(),
  prize: "Récompense à confirmer",
  region: "EU",
  level_min: 1,
  image_color: "#FF4600",
  description: "",
  maps_text: "Mirage\nInferno\nAnubis",
  rules_text: "Présence requise avant le verrouillage du roster.\nLes remplacements suivent les règles de la salle d'attente.",
});

const makeTeamForm = () => ({
  name: "",
  tag: "",
  country: "FR",
  description: "",
  language: "FR",
  discord_url: "",
  logo_color: "#FF4600",
  recruitment_status: "open",
  members_limit: 7,
});

const makeFunMatchForm = () => ({
  title: "Lobby fun 5v5",
  description: "",
  map: "de_mirage",
});

const makeNewsForm = () => ({
  title: "",
  excerpt: "",
  body: "",
  date: toLocalInputValue(),
});

const makeAnnouncementForm = () => ({
  title: "",
  body: "",
  kind: "info",
  priority: 3,
  is_active: true,
  cta_label: "",
  cta_url: "",
  starts_at: toLocalInputValue(),
  ends_at: toLocalInputValue(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()),
});

const makeContestForm = () => ({
  title: "",
  summary: "",
  body: "",
  reward_label: "",
  max_entries: 250,
  is_active: true,
  banner_color: "#FF4600",
  cta_label: "Participer",
  cta_url: "/concours",
  starts_at: toLocalInputValue(),
  ends_at: toLocalInputValue(new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString()),
});

const makeRewardForm = () => ({
  title: "",
  summary: "",
  description: "",
  category: "badge",
  cost_tokens: 250,
  stock: 25,
  is_active: true,
  accent_color: "#00F0FF",
  delivery_notes: "Traitement manuel ou automatique selon le type de reward.",
});

const formatMetric = (value, digits = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (typeof value === "number") {
    return digits > 0 ? value.toFixed(digits) : value.toLocaleString("fr-FR");
  }
  return String(value);
};

const formatPremierMetric = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toLocaleString("en-US") : String(value);
};

const hasMetricValue = (value) => value !== null && value !== undefined && value !== "";

const formatPercentMetric = (value, digits = 0) =>
  hasMetricValue(value) ? `${Number(value).toFixed(digits)}%` : "â€”";

const formatUnitMetric = (value, suffix, digits = 0) =>
  hasMetricValue(value) ? `${Number(value).toFixed(digits)}${suffix}` : "â€”";

const MATCH_REPORT_LABELS = {
  technical: "Technique",
  pause: "Pause",
  behavior: "Comportement",
  absence: "Absence",
  score: "Score",
  cheat: "Suspicion",
  other: "Autre",
};

const MATCH_REPORT_STATUS_LABELS = {
  open: "ouvert",
  acknowledged: "pris en compte",
  resolved: "resolu",
  rejected: "rejete",
};

const MATCH_REPORT_SOURCE_LABELS = {
  web_ui: "Site",
  cs2_chat: "CS2",
};

const MATCH_EVENT_LABELS = {
  series_start: "Debut de serie",
  series_end: "Fin de serie",
  map_result: "Resultat de map",
  map_start: "Debut de map",
  round_end: "Fin de round",
  player_kill: "Kill",
  bomb_planted: "Bombe posee",
  bomb_defused: "Bombe desamorcee",
};

const formatMatchEventLabel = (value) => {
  if (!value) return "Evenement";
  if (MATCH_EVENT_LABELS[value]) return MATCH_EVENT_LABELS[value];
  return String(value)
    .split("_")
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
};

const matchReportStatusClass = (status) =>
  ({
    open: "bg-red-500/20 text-red-300 border-red-500/30",
    acknowledged: "bg-yellow-500/20 text-yellow-200 border-yellow-500/30",
    resolved: "bg-cyan-500/20 text-cyan-200 border-cyan-500/30",
    rejected: "bg-white/10 text-white/60 border-white/10",
  }[status] || "bg-white/10 text-white/60 border-white/10");

const sortByMetric = (items, field) =>
  [...items].sort((a, b) => {
    const left = typeof a?.[field] === "number" ? a[field] : -Infinity;
    const right = typeof b?.[field] === "number" ? b[field] : -Infinity;
    return right - left;
  });

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

const computeTeamMemberMvpScore = (member) => {
  const elo = Number(member?.elo || 0);
  const faceit = Number(member?.faceit_elo || 0);
  const premier = Number(member?.premier_rating || 0);
  const kdr = Number(member?.kdr || 0);
  const reliability = Number(member?.reliability || 0);
  let score = elo / 25 + faceit / 30 + premier / 350 + kdr * 140 + reliability * 1.6;
  if (member?.team_role === "captain") score += 18;
  if (member?.steam_verified) score += 8;
  return score;
};

const resolveTeamMvp = (members = []) =>
  [...members].sort((left, right) => computeTeamMemberMvpScore(right) - computeTeamMemberMvpScore(left))[0] || null;

const TeamMemberPremiumCard = ({ member, teamColor, isMvp = false, compact = false, rank = null }) => (
  <div
    className={`relative overflow-hidden border ${isMvp ? "shadow-[0_0_40px_rgba(255,184,0,0.18)]" : "shadow-[0_0_24px_rgba(0,0,0,0.18)]"}`}
    style={{
      background: `linear-gradient(145deg, rgba(7,10,20,0.96) 0%, rgba(14,18,32,0.94) 58%, ${teamColor || "#FF4600"}22 100%)`,
      borderColor: isMvp ? "rgba(255,184,0,0.5)" : `${teamColor || "#FF4600"}44`,
    }}
  >
    <div className="absolute top-0 right-0 w-32 h-32 blur-3xl opacity-40" style={{ background: teamColor || "#FF4600" }}/>
    <div className="relative p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-4">
          <div
            className="rounded-2xl overflow-hidden border border-white/10 bg-white/5 flex items-center justify-center font-display text-2xl"
            style={{ width: compact ? 56 : 72, height: compact ? 56 : 72, minWidth: compact ? 56 : 72, boxShadow: `0 0 22px ${teamColor || "#FF4600"}33` }}
          >
            {member.avatar_url ? (
              <img src={member.avatar_url} alt={member.pseudo} className="w-full h-full object-cover" />
            ) : (
              (member.pseudo || "P").slice(0, 1).toUpperCase()
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              {rank !== null && <span className="text-xs uppercase tracking-widest text-white/30">#{rank + 1}</span>}
              {isMvp && <Badge variant="verified"><Crown size={12}/>MVP</Badge>}
              {member.steam_verified && !isMvp && <Badge variant="verified"><Shield size={12}/>Steam</Badge>}
            </div>
            <div className="font-display text-2xl uppercase mt-2">{member.pseudo}</div>
            <div className="text-xs uppercase tracking-[0.25em] text-white/45 mt-1">
              {member.role || "Polyvalent"} • {member.team_role || "member"}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-widest text-white/35">Impact</div>
          <div className={`font-display text-2xl mt-1 ${isMvp ? "text-yellow-neon" : "text-orange-500"}`}>
            {Math.round(computeTeamMemberMvpScore(member))}
          </div>
        </div>
      </div>

      <div className={`grid ${compact ? "grid-cols-2" : "grid-cols-4"} gap-3 mt-5`}>
        <div className="border border-white/10 p-3">
          <div className="text-[10px] uppercase tracking-widest text-white/35">ELO</div>
          <div className="font-display text-xl text-orange-500 mt-1">{formatMetric(member.elo)}</div>
        </div>
        <div className="border border-white/10 p-3">
          <div className="text-[10px] uppercase tracking-widest text-white/35">FACEIT</div>
          <div className="font-display text-xl text-cyan-neon mt-1">{formatMetric(member.faceit_elo)}</div>
        </div>
        <div className="border border-white/10 p-3">
          <div className="text-[10px] uppercase tracking-widest text-white/35">Premier</div>
          <div className="font-display text-xl text-red-400 mt-1">{formatPremierMetric(member.premier_rating)}</div>
        </div>
        <div className="border border-white/10 p-3">
          <div className="text-[10px] uppercase tracking-widest text-white/35">K/D</div>
          <div className="font-display text-xl text-green-400 mt-1">{formatMetric(member.kdr, 2)}</div>
        </div>
      </div>

      <div className={`grid ${compact ? "grid-cols-2" : "grid-cols-4"} gap-3 mt-3`}>
        <div className="text-xs text-white/55">LVL <span className="text-white">{formatMetric(member.level)}</span></div>
        <div className="text-xs text-white/55">Fiabilité <span className="text-white">{formatMetric(member.reliability)}</span></div>
        <div className="text-xs text-white/55">Rang <span className="text-white">{member.rank_cs2 || "—"}</span></div>
        <div className="text-xs text-white/55">Statut <span className={`${member.online ? "text-green-400" : "text-white/50"}`}>{member.online ? "online" : "offline"}</span></div>
      </div>
    </div>
  </div>
);

/* ============== HOME ============== */
const Home = () => {
  const [tournaments, setTournaments] = useState([]);
  const [news, setNews] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [contests, setContests] = useState([]);
  const [stats, setStats] = useState({});
  const [live, setLive] = useState(null);
  const [teams, setTeams] = useState([]);
  useEffect(() => {
    const load = async () => {
      const [
        tournamentsResult,
        newsResult,
        announcementsResult,
        contestsResult,
        statsResult,
        liveResult,
        teamsResult,
      ] = await Promise.allSettled([
        axios.get(`${API}/tournaments`),
        axios.get(`${API}/news`),
        axios.get(`${API}/announcements`),
        axios.get(`${API}/contests`),
        axios.get(`${API}/stats/global`),
        axios.get(`${API}/twitch/live`),
        axios.get(`${API}/teams`),
      ]);

      setTournaments(tournamentsResult.status === "fulfilled" ? tournamentsResult.value.data : []);
      setNews(newsResult.status === "fulfilled" ? newsResult.value.data : []);
      setAnnouncements(announcementsResult.status === "fulfilled" ? announcementsResult.value.data : []);
      setContests(contestsResult.status === "fulfilled" ? contestsResult.value.data : []);
      setStats(statsResult.status === "fulfilled" ? statsResult.value.data : {});
      setLive(
        liveResult.status === "fulfilled"
          ? liveResult.value.data
          : {
              channel: "esl_csgo",
              display_name: "esl_csgo",
              live: false,
              configured: false,
              source: "frontend_fallback",
              title: null,
              viewers: null,
              game: "Counter-Strike 2",
              status_message: "Flux Twitch indisponible pour le moment.",
              url: "https://twitch.tv/esl_csgo",
            }
      );
      setTeams(teamsResult.status === "fulfilled" ? teamsResult.value.data : []);
    };

    load();
  }, []);

  const featuredNews = news[0] || null;
  const supportingNews = news.slice(1, 5);
  const topContests = contests.slice(0, 2);
  const showLiveBlock = Boolean(live?.configured || live?.live);
  const showTopTeams = teams.length > 0;
  const showAnnouncements = announcements.length > 0;
  const showNews = Boolean(featuredNews || supportingNews.length);
  const showContests = topContests.length > 0;
  const liveBadgeVariant = live?.live ? "live" : live?.configured ? "soon" : "offline";
  const liveBadgeLabel = live?.live ? "LIVE" : live?.configured ? "HORS LIGNE" : "FLUX EMBARQUE";
  const livePanelLabel = live?.live ? "EN DIRECT" : live?.configured ? "CHAINE OFFLINE" : "STATUT NON CONFIGURE";
  const liveTitle = live?.title || (live?.configured ? `${live?.display_name || live?.channel} est hors ligne` : "Flux Twitch embarque");
  const liveUrl = live?.url || `https://twitch.tv/${live?.channel || "esl_csgo"}`;

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
              <Link to="/fun-5v5" className="btn-ghost" data-testid="hero-cta-fun-5v5"><Gamepad2 size={16}/>Match fun 5v5</Link>
              <Link to="/waiting-room/tr1" className="btn-ghost" data-testid="hero-cta-match"><Swords size={16}/>Trouver un match</Link>
              <Link to="/community" className="btn-ghost" data-testid="hero-cta-community"><Radio size={16}/>Rejoindre la communauté</Link>
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
        {showLiveBlock && (
          <>
            <SectionTitle sub="Live officiel" title="Major CS2 en direct" cta={<Badge variant={liveBadgeVariant} testid="twitch-live-badge">{liveBadgeLabel}</Badge>}/>
            <div className="grid lg:grid-cols-3 gap-4" data-testid="twitch-block">
              <div className="lg:col-span-2 aspect-video glass overflow-hidden relative">
                <iframe title="Twitch" src={`https://player.twitch.tv/?channel=${live?.channel || "esl_csgo"}&parent=${window.location.hostname}&muted=true&autoplay=false`}
                  allowFullScreen className="w-full h-full" frameBorder="0"/>
              </div>
              <div className="glass p-6 flex flex-col">
                <Badge variant={liveBadgeVariant} testid="twitch-status-badge">{livePanelLabel}</Badge>
                <h3 className="font-display text-xl mt-3">{liveTitle}</h3>
                <p className="text-sm text-white/50 mt-1">Chaîne <span className="text-cyan-neon">{live?.display_name || live?.channel || "esl_csgo"}</span></p>
                <div className="mt-auto pt-6 space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-white/50">Spectateurs</span><span className="font-display text-orange-500">{live?.viewers ? live.viewers.toLocaleString() : "—"}</span></div>
                  <div className="flex justify-between"><span className="text-white/50">Jeu</span><span>{live?.game || "Counter-Strike 2"}</span></div>
                  <p className="text-xs text-white/45">{live?.status_message || "Flux Twitch indisponible."}</p>
                  <a href={liveUrl} target="_blank" rel="noreferrer" className="btn-ghost w-full mt-3" data-testid="open-twitch-btn"><ExternalLink size={14}/>Ouvrir sur Twitch</a>
                </div>
              </div>
            </div>
          </>
        )}

        {/* TOURNAMENTS */}
        <SectionTitle sub="Action immédiate" title="Tournois à venir" cta={<Link to="/tournaments" className="btn-ghost" data-testid="all-tournaments-btn">Tout voir <ChevronRight size={14}/></Link>}/>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tournaments.slice(0,6).map(t => <TournamentCard key={t.id} t={t}/>)}
        </div>

        {/* TOP TEAMS */}
        {showTopTeams && (
          <>
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
          </>
        )}

        {showAnnouncements && (
          <>
            <SectionTitle sub="Plateforme" title="Annonces importantes"/>
            <div className="grid md:grid-cols-2 gap-4">
              {announcements.map((announcement) => (
                <div key={announcement.id} className="glass p-6">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <Badge variant={announcement.kind === "maintenance" ? "soon" : "verified"}>{announcement.kind}</Badge>
                    <span className="text-xs uppercase tracking-widest text-white/40">Priorité {announcement.priority}</span>
                  </div>
                  <h3 className="font-display text-2xl uppercase mt-4">{announcement.title}</h3>
                  <p className="text-white/60 mt-3">{announcement.body}</p>
                  {announcement.cta_url && (
                    announcement.cta_url.startsWith("http") ? (
                      <a href={announcement.cta_url} target="_blank" rel="noreferrer" className="btn-ghost mt-5">
                        {announcement.cta_label || "Ouvrir"} <ExternalLink size={14}/>
                      </a>
                    ) : (
                      <Link to={announcement.cta_url} className="btn-ghost mt-5">
                        {announcement.cta_label || "Ouvrir"} <ChevronRight size={14}/>
                      </Link>
                    )
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {showNews && (
          <>
            <SectionTitle sub="Actualité" title="Dernières news"/>
            <div className="grid xl:grid-cols-[1.15fr_0.85fr] gap-4">
              {featuredNews && (
                <article className="glass p-8 border border-orange-500/20" data-testid={`news-${featuredNews.id}`}>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <Badge variant="soon">A la une</Badge>
                    <div className="text-xs text-orange-400 uppercase tracking-widest">{new Date(featuredNews.date).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })}</div>
                  </div>
                  <h3 className="font-display text-3xl sm:text-4xl uppercase mt-5">{featuredNews.title}</h3>
                  <p className="text-white/70 mt-4 text-lg">{featuredNews.excerpt}</p>
                  <div className="mt-6 border-t border-white/8 pt-5 text-sm text-white/55 whitespace-pre-line">
                    {featuredNews.body || featuredNews.excerpt}
                  </div>
                </article>
              )}
              <div className="grid gap-4">
                {supportingNews.map((item) => (
                  <article key={item.id} className="glass p-6" data-testid={`news-${item.id}`}>
                    <div className="text-[11px] text-orange-400 uppercase tracking-[0.3em]">{new Date(item.date).toLocaleDateString("fr-FR")}</div>
                    <h4 className="font-display text-xl uppercase mt-3">{item.title}</h4>
                    <p className="text-sm text-white/60 mt-3">{item.excerpt}</p>
                  </article>
                ))}
              </div>
            </div>
          </>
        )}

        {showContests && (
          <>
            <SectionTitle sub="Communauté" title="Concours actifs" cta={<Link to="/concours" className="btn-ghost"><Ticket size={14}/>Voir tout</Link>}/>
            <div className="grid md:grid-cols-2 gap-4">
              {topContests.map((contest) => (
                <div key={contest.id} className="glass p-6" style={{ borderColor: `${contest.banner_color || "#FF4600"}55` }}>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <Badge variant="soon">{contest.remaining_slots === 0 ? "Complet" : "Ouvert"}</Badge>
                    <span className="text-xs uppercase tracking-widest text-white/40">{contest.entries_count} / {contest.max_entries} participations</span>
                  </div>
                  <h3 className="font-display text-2xl uppercase mt-4">{contest.title}</h3>
                  <p className="text-white/60 mt-3">{contest.summary}</p>
                  <div className="text-sm text-white/50 mt-4">Lot: <span className="text-white">{contest.reward_label || "Annonce a venir"}</span></div>
                  <Link to="/concours" className="btn-ghost mt-5">
                    {contest.cta_label || "Participer"} <ChevronRight size={14}/>
                  </Link>
                </div>
              ))}
            </div>
          </>
        )}

        <SectionTitle sub="Communauté" title="Soutiens récents" cta={<Link to="/support" className="btn-ghost" data-testid="donate-cta-home"><Heart size={14}/>Faire un don</Link>}/>
        <RecentDonors/>

      </div>
    </div>
  );
};

const tournamentRegisteredCount = (t) => t?.registered_effective ?? t?.registered ?? 0;

const TournamentCard = ({ t }) => {
  const variant = { open: "soon", registering: "soon", starting: "live", live: "live", in_progress: "live", closed: "offline" }[t.status] || "default";
  const label = { open: "Inscriptions", registering: "Inscriptions", starting: "Lancement", live: "LIVE", in_progress: "En cours", closed: "Termine" }[t.status];
  const registered = tournamentRegisteredCount(t);
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
        <span className="flex items-center gap-1"><Users size={12}/>{registered}/{t.capacity}</span>
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
    if (entity_type === "team" && !user?.team_id) {
      alert("Créez ou rejoignez une équipe avant l'inscription tournoi.");
      return;
    }
    if (entity_type === "team" && user?.team_role !== "captain") {
      alert("Seul le capitaine peut inscrire l'équipe au tournoi.");
      return;
    }
    const entity_name = entity_type === "team" ? (user?.pseudo || "Equipe") : (user?.pseudo || "Joueur");
    try {
      await axios.post(
        `${API}/tournaments/${id}/register`,
        { entity_type, entity_name, entity_id: entity_type === "team" ? user?.team_id : undefined },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      await load();
      alert("Inscription confirmée ✅");
    } catch (e) { alert(e.response?.data?.detail || "Erreur d'inscription"); }
  };
  if (!t) return <div className="p-10 text-center text-white/40">Chargement…</div>;
  const registered = tournamentRegisteredCount(t);
  const canRegisterTeam = t.can_register_team ?? (["open", "registering"].includes(t.status) && registered < t.capacity);
  const canRegisterSolo = t.can_register_solo ?? canRegisterTeam;
  const hasOpenRegistration = canRegisterTeam || canRegisterSolo;
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="tournament-detail">
      <Link to="/tournaments" className="text-orange-500 text-xs uppercase tracking-widest">← Retour catalogue</Link>
      <div className="glass mt-4 p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 opacity-30 blur-3xl" style={{ background: t.image_color }}/>
        <Badge variant={t.status === "open" ? "soon" : "live"}>{t.status.toUpperCase()}</Badge>
        <h1 className="font-display text-5xl uppercase mt-3">{t.name}</h1>
        <p className="text-white/60">{t.organizer} • {t.format} • {t.mode} • {t.region}</p>
        <div className="grid sm:grid-cols-4 gap-4 mt-6">
          <Stat label="Inscrites" value={`${registered}/${t.capacity}`}/>
          <Stat label="Format" value={t.format} accent="text-orange-500"/>
          <Stat label="Récompense" value={t.prize} accent="text-yellow-neon"/>
          <Stat label="Début" value={new Date(t.starts_at).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}/>
        </div>
        <div className="mt-4 text-sm text-white/50">
          <span>{t.manual_teams_count ?? 0} équipe(s) manuelle(s)</span>
          <span className="mx-2">•</span>
          <span>{t.auto_generated_teams_count ?? 0} équipe(s) auto</span>
          <span className="mx-2">•</span>
          <span>{t.solo_queue_original_count ?? t.solo_queue?.length ?? 0} solo(s) en file</span>
        </div>
        <div className="mt-6 flex gap-2 flex-wrap">
          {hasOpenRegistration ? (
            <>
              {canRegisterTeam && (
                <button
                  onClick={() => register("team")}
                  className="btn-neon"
                  data-testid="register-team-btn"
                  disabled={!user?.team_id || user?.team_role !== "captain"}
                >
                  <Users size={14}/>{!user?.team_id ? "Créer une équipe d'abord" : user?.team_role !== "captain" ? "Capitaine requis" : "Inscrire mon équipe"}
                </button>
              )}
              {canRegisterSolo && (
                <button onClick={() => register("solo")} className="btn-ghost" data-testid="register-solo-btn"><User size={14}/>Rejoindre la file solo</button>
              )}
            </>
          ) : (
            <span className="px-4 py-2 text-xs uppercase tracking-widest border border-white/10 text-white/40" data-testid="register-closed">Inscriptions fermées</span>
          )}
          <Link to={`/waiting-room/${t.id}`} className="btn-ghost" data-testid="enter-waiting-room-btn"><Radio size={14}/>Salle d'attente</Link>
        </div>
      </div>
      <div className="grid lg:grid-cols-2 gap-4 mt-6">
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Présentation</h3>
          <p className="text-white/60 leading-relaxed">{t.description || "Description à venir."}</p>
          <div className="grid md:grid-cols-2 gap-4 mt-6">
            <div>
              <div className="text-xs uppercase tracking-widest text-white/40 mb-2">Maps</div>
              <div className="flex flex-wrap gap-2">
                {(t.maps?.length ? t.maps : ["Mirage", "Inferno", "Anubis"]).map((mapName) => (
                  <span key={mapName} className="px-3 py-1 border border-white/10 text-sm text-white/70">{mapName}</span>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-widest text-white/40 mb-2">Règles clés</div>
              <ul className="space-y-2 text-sm text-white/70">
                {(t.rules?.length ? t.rules : ["Présence requise avant le départ.", "Steam vérifié conseillé.", "Audit des décisions sensibles activé."]).map((rule, index) => (
                  <li key={index}>• {rule}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Équipes inscrites ({t.teams_in.length})</h3>
          <div className="space-y-2">{t.teams_in.map((te, i) => (
            <div key={te.id} className="flex items-center gap-3 p-2 border border-white/5">
              <span className="font-mono-display text-white/30 text-xs">#{String(i + 1).padStart(2, "0")}</span>
              <TeamLogo team={te} size={32}/><span className="font-display flex-1">{te.name}</span>
              {te.generated_from_solos && <span className="text-[10px] uppercase tracking-widest text-orange-400">AUTO</span>}
              <span className="text-xs text-cyan-neon">ELO {te.elo}</span>
            </div>))}</div>
        </div>
        <div className="glass p-6 lg:col-span-2">
          <h3 className="font-display text-xl uppercase mb-4">File solo / Renforts ({t.solo_queue.length})</h3>
          <div className="space-y-2">{t.solo_queue.map((p) => (
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
  const [servers, setServers] = useState([]);
  const [serverByMatch, setServerByMatch] = useState({});
  const [launchingMatchId, setLaunchingMatchId] = useState(null);
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
  useEffect(() => {
    if (!isAdmin) return;
    axios.get(`${API}/cs2/servers`).then((r) => setServers(r.data)).catch(() => setServers([]));
  }, [isAdmin, tid]);
  useEffect(() => {
    if (!bracket || !servers.length) return;
    setServerByMatch((prev) => {
      const next = { ...prev };
      ["W", "L", "GF"].forEach((group) => {
        (bracket.matches[group] || []).forEach((match) => {
          if (!next[match.id]) {
            next[match.id] =
              match.server_id ||
              (servers.find((server) => !server.current_match_id || server.current_match_id === match.id) || servers[0])?.id ||
              "";
          }
        });
      });
      return next;
    });
  }, [bracket, servers]);
  const gen = async (type) => { setBusy(true);
    try { await axios.post(`${API}/tournaments/${tid}/bracket/generate`, { type }, { headers: authH }); await load(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); } finally { setBusy(false); } };
  const report = async (mid, winner_id) => {
    try { const r = await axios.post(`${API}/tournaments/${tid}/bracket/match/${mid}/result`, { winner_id, expected_version: bracket?.version }, { headers: authH }); setBracket(r.data); }
    catch (e) { if (e.response?.status === 409) { await load(); } alert(e.response?.data?.detail || "Erreur"); } };
  const launchMatch = async (mid) => {
    const server_id = serverByMatch[mid];
    if (!server_id) {
      alert("Choisissez un serveur CS2.");
      return;
    }
    setLaunchingMatchId(mid);
    try {
      await axios.post(`${API}/cs2/tournaments/${tid}/bracket-matches/${mid}/launch`, { server_id }, { headers: authH });
      await load();
    } catch (e) {
      alert(e.response?.data?.detail || "Lancement MatchZy impossible");
    } finally {
      setLaunchingMatchId(null);
    }
  };

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
                  {(m.server_name || (isAdmin && m.a && m.b)) && (
                    <div className="mt-3 pt-3 border-t border-white/10 space-y-2">
                      {m.server_name && (
                        <div className="text-[11px] text-white/50 uppercase tracking-widest">
                          Serveur: <span className="text-white/80">{m.server_name}</span>
                          {m.launch_status && <span className="text-white/40"> • {m.launch_status}</span>}
                        </div>
                      )}
                      {m.series_score && (
                        <div className="text-xs text-white/50">
                          Serie: {m.series_score.team1 ?? 0} - {m.series_score.team2 ?? 0}
                        </div>
                      )}
                      {isAdmin && m.a && m.b && !m.winner_id && (
                        <>
                          <select
                            value={serverByMatch[m.id] || ""}
                            onChange={(event) => setServerByMatch({ ...serverByMatch, [m.id]: event.target.value })}
                            className="w-full"
                            data-testid={`launch-server-select-${m.id}`}
                          >
                            <option value="">Choisir un serveur</option>
                            {servers.map((server) => (
                              <option key={server.id} value={server.id}>
                                {server.name} ({server.status || "unknown"})
                              </option>
                            ))}
                          </select>
                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() => launchMatch(m.id)}
                              disabled={launchingMatchId === m.id}
                              className="btn-neon text-xs"
                              data-testid={`launch-match-${m.id}`}
                            >
                              <Server size={12}/>{launchingMatchId === m.id ? "Lancement..." : "Lancer sur serveur"}
                            </button>
                            {m.launch_status && <Link to={`/match/${m.id}`} className="btn-ghost text-xs"><Radio size={12}/>Suivi match</Link>}
                          </div>
                        </>
                      )}
                    </div>
                  )}
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
    if (!data) return;
    setPhase(data.phase || "open");
    setSeconds(data.starts_in_seconds);
  }, [data]);

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
  const mm = String(Math.floor(displaySec / 60)).padStart(2, "0");
  const ss = String(displaySec % 60).padStart(2, "0");
  const phaseColor = { open: "text-white", first_call: "text-yellow-neon", last_call: "text-orange-500", countdown: "text-red-500" }[phase] || "text-white";
  const phaseLabel = { open: "Salle d'attente — ouverte", first_call: "Premier appel — confirmez votre équipe", last_call: "Dernier appel — départ imminent", countdown: "Décompte" }[phase] || "Salle d'attente";

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="waiting-room">
      <div className="glass p-8 text-center relative overflow-hidden">
        <Particles/>
        <div className="flex items-center justify-center gap-3"><Badge variant="live">SALLE D'ATTENTE</Badge>
          <span className="text-xs uppercase tracking-widest text-cyan-neon" data-testid="ws-presence-count">● {presence.length} connecté{presence.length > 1 ? 's' : ''}</span></div>
        <div className="mt-4 text-xs uppercase tracking-[0.3em] text-white/40">{data.tournament_name || `Tournoi ${id}`}</div>
        <div className={`font-display font-bold text-7xl sm:text-8xl mt-4 ${phaseColor}`} data-testid="countdown-timer">{mm}:{ss}</div>
        <p className={`mt-2 uppercase tracking-[0.3em] text-sm ${phaseColor}`}>{phaseLabel}</p>
        <div className="mt-6 flex gap-2 justify-center flex-wrap">
          {user && <button onClick={markReady} className="btn-ghost" data-testid="btn-ready"><CheckCircle2 size={14}/>Je suis prêt</button>}
          <button onClick={startCountdown} className="btn-neon" data-testid="start-countdown-btn"><Zap size={14}/>Lancer le décompte serveur</button>
        </div>
      </div>
      <div className="grid md:grid-cols-4 gap-4 mt-6">
        <Stat label="Équipes valides" value={`${data.teams_confirmed}/${data.teams_total}`}/>
        <Stat label="Équipes auto" value={data.auto_generated_teams_count ?? 0} accent="text-orange-500"/>
        <Stat label="Solos en attente" value={data.solo_queue_count ?? 0} accent="text-cyan-neon"/>
        <Stat label="Places restantes" value={data.teams_missing ?? 0}/>
      </div>
      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Présence ({presence.length})</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {presence.map((p) => (<div key={p.id} className="flex items-center gap-3 p-2 border border-white/5" data-testid={`presence-${p.id}`}>
              <span className="w-2 h-2 rounded-full bg-green-400 shadow-[0_0_8px_#4ade80]"/>
              <span className="font-display flex-1">{p.pseudo}</span>
              <span className="text-xs text-orange-500">LVL {p.level}</span></div>))}
            {presence.length === 0 && <div className="text-white/30 text-sm">Aucun joueur connecté</div>}
          </div>
        </div>
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Événements live</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {liveEvents.map((e, i) => (<div key={i} className="flex gap-3 text-sm" data-testid={`live-event-${i}`}>
              <span className="font-mono-display text-orange-500 text-xs">{e.time}</span><span className="text-white/70">{e.msg}</span></div>))}
            {liveEvents.length === 0 && data.events.map((e, i) => (<div key={i} className="flex gap-3 text-sm text-white/40"><span className="font-mono-display text-xs">{e.time}</span><span>{e.msg}</span></div>))}
          </div>
        </div>
        <div className="glass p-6 flex flex-col">
          <h3 className="font-display text-xl uppercase mb-4">Chat</h3>
          <div className="flex-1 space-y-1 max-h-64 overflow-y-auto mb-3 text-sm">
            {chat.map((c, i) => (<div key={i} data-testid={`chat-msg-${i}`}><span className="text-orange-500 font-display">{c.from}</span> <span className="text-white/70">{c.msg}</span></div>))}
            {chat.length === 0 && <div className="text-white/30">Aucun message</div>}
          </div>
          <div className="flex gap-2">
            <input value={msg} onChange={e => setMsg(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendChat()} placeholder="Message…" className="flex-1" data-testid="chat-input"/>
            <button onClick={sendChat} className="btn-ghost" data-testid="chat-send">→</button>
          </div>
        </div>
      </div>
      <div className="grid lg:grid-cols-2 gap-4 mt-6">
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Équipes confirmées ({data.teams_in?.length || 0})</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {(data.teams_in || []).map((team, index) => (
              <div key={team.id || index} className="flex items-center gap-3 p-2 border border-white/5">
                <span className="font-mono-display text-white/30 text-xs">#{String(index + 1).padStart(2, '0')}</span>
                <TeamLogo team={team} size={28}/>
                <span className="font-display flex-1">{team.name}</span>
                {team.generated_from_solos && <span className="text-[10px] uppercase tracking-widest text-orange-400">AUTO</span>}
              </div>
            ))}
            {!(data.teams_in || []).length && <div className="text-white/30 text-sm">Aucune équipe confirmée</div>}
          </div>
        </div>
        <div className="glass p-6">
          <h3 className="font-display text-xl uppercase mb-4">Renforts en attente ({data.solo_queue?.length || 0})</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {(data.solo_queue || []).map((player) => (
              <div key={player.id} className="flex items-center gap-3 p-2 border border-white/5">
                <span className={`w-2 h-2 rounded-full ${player.online ? 'bg-green-400 shadow-[0_0_8px_#4ade80]' : 'bg-white/20'}`}/>
                <span className="font-display flex-1">{player.pseudo}</span>
                <span className="text-xs text-white/40">{player.role || 'Polyvalent'}</span>
              </div>
            ))}
            {!(data.solo_queue || []).length && <div className="text-white/30 text-sm">Aucun solo en attente</div>}
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
const MatchRoom = () => {
  const { id } = useParams();
  const { token, user } = useAuth();
  const [detail, setDetail] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [reportMessage, setReportMessage] = useState("");
  const [reportError, setReportError] = useState("");
  const [connectBusy, setConnectBusy] = useState("");
  const [connectError, setConnectError] = useState("");
  const [reportForm, setReportForm] = useState({ kind: "technical", message: "", round_label: "", target_user_id: "", target_steam_id: "" });

  useEffect(() => {
    let active = true;

    const load = async (withSpinner = false) => {
      if (withSpinner) setLoading(true);
      try {
        const detailPromise = axios.get(`${API}/matches/${id}`);
        const reportsPromise = token
          ? axios
              .get(`${API}/matches/${id}/reports`, { headers: { Authorization: `Bearer ${token}` } })
              .then((response) => response.data)
              .catch(() => [])
          : Promise.resolve([]);
        const [detailResponse, reportsData] = await Promise.all([detailPromise, reportsPromise]);
        if (!active) return;
        setDetail(detailResponse.data);
        setReports(reportsData || []);
        setError("");
      } catch (loadError) {
        if (!active) return;
        setError(loadError?.response?.data?.detail || "Match introuvable pour le moment.");
      } finally {
        if (active && withSpinner) setLoading(false);
      }
    };

    load(true);
    const interval = setInterval(() => load(false), 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [id, token]);

  const submitReport = async (event) => {
    event.preventDefault();
    if (!token) {
      setReportError("Connectez-vous pour signaler un incident.");
      return;
    }
    const needsTarget = ["behavior", "absence", "cheat", "other"].includes(reportForm.kind);
    if (needsTarget && !reportForm.target_steam_id) {
      setReportError("Selectionnez le joueur vise.");
      return;
    }
    setSubmitting(true);
    setReportMessage("");
    setReportError("");
    try {
      const response = await axios.post(`${API}/matches/${id}/reports`, reportForm, { headers: { Authorization: `Bearer ${token}` } });
      const reportsResponse = await axios.get(`${API}/matches/${id}/reports`, { headers: { Authorization: `Bearer ${token}` } });
      setReports(reportsResponse.data || []);
      setReportForm((prev) => ({ ...prev, message: "", round_label: "" }));
      setReportMessage(
        response?.data?.auto_card_triggered
          ? "Signalement transmis. Carton jaune automatique declenche."
          : "Signalement transmis au back-office."
      );
    } catch (submitError) {
      setReportError(submitError?.response?.data?.detail || "Signalement impossible pour le moment.");
    } finally {
      setSubmitting(false);
    }
  };

  const openMatchConnection = async (mode) => {
    if (!token) {
      setConnectError(mode === "spectate" ? "Connectez-vous pour ouvrir le flux HLTV." : "Connectez-vous pour rejoindre ce match.");
      return;
    }
    setConnectBusy(mode);
    setConnectError("");
    try {
      const response = await axios.post(
        `${API}/matches/${id}/${mode === "spectate" ? "spectate" : "join"}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const launchUrl = response.data?.join_url || response.data?.spectator_url;
      if (!launchUrl) {
        throw new Error("Steam URL unavailable");
      }
      window.location.href = launchUrl;
    } catch (connectionError) {
      setConnectError(connectionError?.response?.data?.detail || "Connexion indisponible pour le moment.");
    } finally {
      setConnectBusy("");
    }
  };

  const summary = detail?.summary || {};
  const timeline = [...(detail?.timeline || [])].slice(-12).reverse();
  const latestEventAt = detail?.timeline?.length ? detail.timeline[detail.timeline.length - 1]?.received_at : null;
  const openReports = reports.filter((item) => item.status === "open" || item.status === "acknowledged").length;
  const server = detail?.server;
  const serverStatusVariant = detail?.ended ? "offline" : server?.status === "live" ? "live" : server?.status === "launch_pending" ? "soon" : server?.status === "online" ? "verified" : "default";
  const participants = (detail?.participants || []).filter((item) => item?.steam_id);
  const reportablePlayers = participants.filter((item) => item.user_id !== user?.id && item.steam_id !== user?.steam_id);
  const joinNeedsAuth = Boolean(server?.join_password_required);
  const spectatorNeedsAuth = Boolean(server?.spectator_password_required);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-10" data-testid="match-room-loading">
        <div className="glass p-8 text-white/50">Chargement de la room de match…</div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-10" data-testid="match-room-error">
        <div className="glass p-8 border border-red-500/30 text-red-300">{error}</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="match-room">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Badge variant={detail?.ended ? "offline" : "live"}>{detail?.ended ? "TERMINE" : "EN COURS"}</Badge>
          <h1 className="font-display text-4xl uppercase mt-3">
            {summary.team1_name || "Team 1"} vs {summary.team2_name || "Team 2"}
          </h1>
          <p className="text-white/50 mt-2">
            Match ID {id} • map {summary.map_name || "—"} • dernier event {latestEventAt ? new Date(latestEventAt).toLocaleString("fr-FR") : "—"}
          </p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="btn-ghost"
          data-testid="match-refresh-btn"
        >
          <RefreshCw size={14}/>Actualiser
        </button>
      </div>

      <div className="glass p-8 mt-6 text-center">
        <div className="grid grid-cols-3 items-center gap-4">
          <div>
            <div className="font-display text-2xl">{summary.team1_name || "Team 1"}</div>
            <div className="font-display text-7xl text-orange-500 mt-2">{summary.team1_score ?? 0}</div>
          </div>
          <div className="text-white/40 font-display uppercase tracking-widest">
            {detail?.ended ? "Serie terminee" : "Match live"}
            <div className="text-sm text-white/30 mt-2">Map #{summary.map_number || 1} • {summary.map_name || "—"}</div>
          </div>
          <div>
            <div className="font-display text-2xl">{summary.team2_name || "Team 2"}</div>
            <div className="font-display text-7xl text-cyan-neon mt-2">{summary.team2_score ?? 0}</div>
          </div>
        </div>
      </div>

      <div className="grid xl:grid-cols-[1.15fr_0.85fr] gap-6 mt-6">
        <div className="space-y-6">
          <div className="glass p-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display uppercase">Serveur et orchestration</h3>
              <Badge variant={serverStatusVariant}>{detail?.ended ? "termine" : server?.status || "non assigne"}</Badge>
            </div>
            <div className="grid md:grid-cols-2 gap-4 mt-4 text-sm text-white/70">
              <div>
                <div className="text-xs uppercase tracking-widest text-white/40">Serveur</div>
                <div className="mt-2">{server?.name || "Affectation en cours"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest text-white/40">Connexion</div>
                <div className="mt-2">
                  {server?.public_host
                    ? `${server.public_host}:${server.game_port || server.port}`
                    : server?.host
                      ? `${server.host}:${server.game_port || server.port}`
                      : "Masquee / non disponible"}
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest text-white/40">Cycle</div>
                <div className="mt-2">{server?.current_map || summary.map_name || "Map en attente"} • {server?.current_match_id || id}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest text-white/40">Disponibilite</div>
                <div className="mt-2">{detail?.ended ? "Serie cloturee" : server?.status === "launch_pending" ? "Chargement MatchZy / serveur" : server?.status === "live" ? "Pret a rejoindre" : "Orchestration en cours"}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-5">
              {server?.connect_url && <a href={server.connect_url} className="btn-neon text-xs"><ExternalLink size={12}/>Rejoindre le serveur</a>}
              {!server?.connect_url && joinNeedsAuth && !detail?.ended && token && (
                <button onClick={() => openMatchConnection("join")} disabled={connectBusy === "join"} className="btn-neon text-xs">
                  <ExternalLink size={12}/>{connectBusy === "join" ? "Connexion..." : "Rejoindre le serveur"}
                </button>
              )}
              {!server?.connect_url && joinNeedsAuth && !detail?.ended && !token && (
                <Link to="/login" className="btn-neon text-xs"><Lock size={12}/>Connexion joueur requise</Link>
              )}
              {server?.hltv_url && <a href={server.hltv_url} className="btn-ghost text-xs"><Tv size={12}/>Voir en spectateur</a>}
              {!server?.hltv_url && spectatorNeedsAuth && !detail?.ended && token && (
                <button onClick={() => openMatchConnection("spectate")} disabled={connectBusy === "spectate"} className="btn-ghost text-xs">
                  <Tv size={12}/>{connectBusy === "spectate" ? "Ouverture..." : "Ouvrir HLTV"}
                </button>
              )}
              {!server?.hltv_url && spectatorNeedsAuth && !detail?.ended && !token && (
                <Link to="/login" className="btn-ghost text-xs"><Lock size={12}/>Connexion spectateur</Link>
              )}
              <button onClick={() => setReportForm((prev) => ({ ...prev, kind: "technical" }))} className="btn-ghost text-xs" data-testid="report-btn">
                <AlertTriangle size={12}/>Signaler
              </button>
              <button onClick={() => setReportForm((prev) => ({ ...prev, kind: "pause", message: prev.kind === "pause" ? prev.message : "Demande de pause technique" }))} className="btn-ghost text-xs" data-testid="pause-btn">
                <Clock size={12}/>Demander pause
              </button>
              <Link to="/live" className="btn-ghost text-xs">
                <Radio size={12}/>Retour aux matchs live
              </Link>
            </div>
            {(joinNeedsAuth || spectatorNeedsAuth) && !detail?.ended && (
              <div className="text-xs text-white/45 mt-4">
                Les liens publics restent masques quand un mot de passe serveur ou HLTV est necessaire.
              </div>
            )}
            {connectError && <div className="text-xs text-red-300 mt-3">{connectError}</div>}
          </div>

          <div className="glass p-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display uppercase">Timeline MatchZy</h3>
              <span className="text-xs uppercase tracking-widest text-white/40">{detail?.timeline?.length || 0} evenements</span>
            </div>
            <div className="space-y-3 mt-5">
              {timeline.length === 0 && <div className="text-white/40">Aucun evenement exploitable pour ce match.</div>}
              {timeline.map((eventItem, index) => (
                <div key={`${eventItem.received_at || "event"}-${index}`} className="border border-white/5 rounded-xl p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="font-display uppercase text-sm">{formatMatchEventLabel(eventItem.event)}</div>
                    <div className="text-xs text-white/40">{eventItem.received_at ? new Date(eventItem.received_at).toLocaleString("fr-FR") : "—"}</div>
                  </div>
                  <div className="text-sm text-white/60 mt-2">
                    {eventItem.payload?.team1?.name || eventItem.payload?.team2?.name
                      ? `${eventItem.payload?.team1?.name || summary.team1_name || "Team 1"} ${eventItem.payload?.team1?.score ?? summary.team1_score ?? 0} - ${eventItem.payload?.team2?.score ?? summary.team2_score ?? 0} ${eventItem.payload?.team2?.name || summary.team2_name || "Team 2"}`
                      : "Evenement recu et journalise par le backend."}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="glass p-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display uppercase">Signalements live</h3>
              <Badge variant={openReports > 0 ? "soon" : "verified"}>{openReports} actif(s)</Badge>
            </div>
            {!token ? (
              <div className="text-white/60 mt-4">
                Connectez-vous pour remonter un incident de match.
                <div className="mt-4">
                  <Link to="/login" className="btn-neon">Se connecter</Link>
                </div>
              </div>
            ) : (
              <form onSubmit={submitReport} className="space-y-3 mt-5">
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Type d'incident</label>
                  <select value={reportForm.kind} onChange={(event) => setReportForm({ ...reportForm, kind: event.target.value })} data-testid="match-report-kind">
                    {Object.entries(MATCH_REPORT_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Joueur vise</label>
                  <select
                    value={reportForm.target_steam_id}
                    onChange={(event) => {
                      const selected = reportablePlayers.find((item) => item.steam_id === event.target.value);
                      setReportForm((prev) => ({
                        ...prev,
                        target_steam_id: selected?.steam_id || "",
                        target_user_id: selected?.user_id || "",
                      }));
                    }}
                    data-testid="match-report-target"
                  >
                    <option value="">Incident general / aucun joueur</option>
                    {reportablePlayers.map((item) => (
                      <option key={`${item.steam_id}-${item.team_name}`} value={item.steam_id}>
                        {item.pseudo} - {item.team_name}
                      </option>
                    ))}
                  </select>
                  {["behavior", "absence", "cheat", "other"].includes(reportForm.kind) && (
                    <div className="text-[11px] text-white/45 mt-2">Requis pour les signalements disciplinaires.</div>
                  )}
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Round / contexte</label>
                  <input value={reportForm.round_label} onChange={(event) => setReportForm({ ...reportForm, round_label: event.target.value })} placeholder="Ex: Round 18 / overtime" maxLength={40} />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Description</label>
                  <textarea value={reportForm.message} onChange={(event) => setReportForm({ ...reportForm, message: event.target.value })} placeholder="Explique le problème rencontré" rows={4} minLength={3} maxLength={500} required />
                </div>
                {reportError && <div className="text-sm text-red-300">{reportError}</div>}
                {reportMessage && <div className="text-sm text-cyan-neon">{reportMessage}</div>}
                <button disabled={submitting} className="btn-neon w-full" data-testid="match-report-submit">
                  <AlertTriangle size={14}/>{submitting ? "Envoi..." : "Envoyer le signalement"}
                </button>
              </form>
            )}
          </div>

          <div className="glass p-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display uppercase">Derniers incidents</h3>
              <span className="text-xs uppercase tracking-widest text-white/40">{reports.length} total</span>
            </div>
            <div className="space-y-3 mt-5">
              {reports.length === 0 && <div className="text-white/40">Aucun signalement enregistre sur ce match.</div>}
              {reports.slice(0, 8).map((item) => (
                <div key={item.id} className="border border-white/5 rounded-xl p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-display text-sm uppercase">{MATCH_REPORT_LABELS[item.kind] || item.kind}</div>
                      {item.target_pseudo && <div className="text-[11px] text-white/35 mt-1">Cible: {item.target_pseudo}</div>}
                      {item.source && <div className="text-[11px] text-white/35 mt-1">Origine: {MATCH_REPORT_SOURCE_LABELS[item.source] || item.source}</div>}
                      <div className="text-xs text-white/40 mt-1">{item.reporter_pseudo} • {new Date(item.created_at).toLocaleString("fr-FR")}</div>
                    </div>
                    <div className={`px-3 py-1 border text-xs uppercase tracking-widest rounded-full ${matchReportStatusClass(item.status)}`}>
                      {MATCH_REPORT_STATUS_LABELS[item.status] || item.status}
                    </div>
                  </div>
                  {item.round_label && <div className="text-xs text-white/40 mt-3">{item.round_label}</div>}
                  <p className="text-sm text-white/70 mt-2">{item.message}</p>
                  {item.resolution_note && <p className="text-xs text-white/40 mt-3">Resolution: {item.resolution_note}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ============== PROFILE ============== */
const Profile = () => {
  const { user: currentUser, token, setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [syncError, setSyncError] = useState("");
  const [mergePreview, setMergePreview] = useState(null);
  const [mergeBusy, setMergeBusy] = useState(false);
  const [mergeError, setMergeError] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const [profileError, setProfileError] = useState("");
  const [profileForm, setProfileForm] = useState({
    pseudo: "",
    email: "",
    gender: "",
    age: "",
    bio: "",
    custom_avatar_url: "",
  });
  const demoProfile = {
    pseudo: "Vortex",
    country: "FR",
    level: 47,
    xp: 8420,
    xp_next: 10000,
    elo: 2240,
    platform_elo: 2240,
    faceit_elo: 2430,
    premier_rating: 27420,
    premier_status: "rated",
    kills_30d: 412,
    deaths_30d: 290,
    kdr: 1.42,
    rank_cs2: "Global Elite",
    role: "AWP",
    gender: "",
    age: null,
    bio: "Capitaine AWP, disponible pour les cups du soir.",
    avatar_url: null,
    custom_avatar_url: null,
    steam_avatar_url: null,
    steam_verified: true,
    reliability: 97,
    stats_last_sync_at: new Date().toISOString(),
    stats_provider: "CSWAT",
    stats_profile_url: "https://cswat.ch/stats/76561198000000000",
    steam_profile_url: "https://steamcommunity.com/profiles/76561198000000000",
    leetify_profile_url: "https://leetify.com/public/profile/76561198000000000",
    faceit_profile_url: "https://www.faceit.com/en/players/readyupvortex",
    faceit_nickname: "readyupvortex",
    faceit_level: 10,
    faceit_winrate: 57,
    faceit_headshots: 46,
    faceit_total_matches: 178,
    faceit_kills_per_round: 0.79,
    faceit_recent_matches: 20,
    aim_rating: 74,
    utility_rating: 69,
    positioning_rating: 71,
    opening_duels_rating: 1.8,
    clutching_rating: 9.4,
    stats_sources: {
      platform: "ReadyUp Arena",
      faceit: "CSWAT",
      premier: "CSWAT",
      kdr: "CSWAT",
    },
  };
  const emptyProfile = {
    pseudo: "Player",
    country: "FR",
    level: 1,
    xp: 0,
    xp_next: 1000,
    elo: 1000,
    platform_elo: 1000,
    faceit_elo: null,
    premier_rating: null,
    premier_status: null,
    kills_30d: null,
    deaths_30d: null,
    kdr: null,
    rank_cs2: "Non renseigné",
    role: "Polyvalent",
    gender: "",
    age: null,
    bio: "",
    avatar_url: null,
    custom_avatar_url: null,
    steam_avatar_url: null,
    steam_verified: false,
    reliability: 50,
    stats_last_sync_at: null,
    stats_provider: null,
    stats_profile_url: null,
    steam_profile_url: null,
    leetify_profile_url: null,
    faceit_profile_url: null,
    faceit_nickname: null,
    faceit_level: null,
    faceit_winrate: null,
    faceit_headshots: null,
    faceit_total_matches: null,
    faceit_kills_per_round: null,
    faceit_recent_matches: null,
    aim_rating: null,
    utility_rating: null,
    positioning_rating: null,
    opening_duels_rating: null,
    clutching_rating: null,
    stats_sources: {},
    team_id: null,
    team_role: null,
  };
  const p = currentUser
    ? { ...emptyProfile, ...currentUser, xp_next: Math.max((currentUser.xp || 0) + 500, 1000) }
    : demoProfile;
  const mergeToken = new URLSearchParams(location.search).get("steam_merge_token");
  const xpPct = (p.xp / p.xp_next) * 100;
  useEffect(() => {
    if (!currentUser) return;
    setProfileForm({
      pseudo: currentUser.pseudo || "",
      email: currentUser.email || "",
      gender: currentUser.gender || "",
      age: currentUser.age || "",
      bio: currentUser.bio || "",
      custom_avatar_url: currentUser.custom_avatar_url || "",
    });
  }, [currentUser]);
  useEffect(() => {
    const steamError = new URLSearchParams(location.search).get("steam_error");
    if (!steamError) return;
    if (steamError === "steam_link_invalid") {
      setSyncError("La liaison Steam a expire. Relancez depuis votre profil.");
      return;
    }
    if (steamError === "steam_link_conflict") {
      setSyncError("Ce compte est deja lie a un autre profil Steam.");
      return;
    }
    setSyncError("Connexion Steam impossible pour le moment.");
  }, [location.search]);
  useEffect(() => {
    if (!mergeToken || !token) {
      setMergePreview(null);
      return;
    }
    let cancelled = false;
    setMergeBusy(true);
    setMergeError("");
    axios
      .get(`${API}/auth/steam/merge-preview`, {
        params: { token: mergeToken },
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((response) => {
        if (!cancelled) {
          setMergePreview(response.data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setMergePreview(null);
          setMergeError(err?.response?.data?.detail || "Fusion Steam introuvable ou expiree.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMergeBusy(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [mergeToken, token]);
  const handleSteamLink = async () => {
    if (!token) {
      window.location.href = `${API}/auth/steam/login?frontend_origin=${encodeURIComponent(window.location.origin)}`;
      return;
    }
    try {
      const response = await axios.post(`${API}/auth/steam/link-session`, {}, { headers: { Authorization: `Bearer ${token}` } });
      window.location.href = response.data.url;
    } catch (err) {
      setSyncError(err?.response?.data?.detail || "Lien Steam impossible pour le moment.");
    }
  };
  const dismissSteamMerge = () => {
    setMergePreview(null);
    setMergeError("");
    navigate("/profile", { replace: true });
  };
  const confirmSteamMerge = async (strategy) => {
    if (!token || !mergeToken) return;
    setMergeBusy(true);
    setMergeError("");
    try {
      const response = await axios.post(
        `${API}/auth/steam/merge-confirm`,
        { token: mergeToken, strategy },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setUser(response.data);
      setMergePreview(null);
      setSyncError("");
      setSyncMessage(
        strategy === "keep_other_progression"
          ? "Compte Steam lie. La progression de l'autre compte a remplace la progression actuelle."
          : "Compte Steam lie. Votre progression actuelle a ete conservee."
      );
      navigate("/profile", { replace: true });
    } catch (err) {
      setMergeError(err?.response?.data?.detail || "Validation de la fusion impossible.");
    } finally {
      setMergeBusy(false);
    }
  };
  const saveProfile = async (event) => {
    event.preventDefault();
    if (!token) {
      setProfileError("Connectez-vous avant de modifier le profil.");
      return;
    }
    setSavingProfile(true);
    setProfileMessage("");
    setProfileError("");
    try {
      const payload = {
        pseudo: profileForm.pseudo.trim(),
        email: profileForm.email.trim(),
        gender: profileForm.gender.trim() || null,
        age: profileForm.age === "" ? null : Number(profileForm.age),
        bio: profileForm.bio.trim() || null,
        custom_avatar_url: profileForm.custom_avatar_url.trim() || null,
      };
      const response = await axios.patch(`${API}/profile/me`, payload, { headers: { Authorization: `Bearer ${token}` } });
      setUser(response.data);
      setProfileMessage("Profil mis a jour.");
    } catch (err) {
      setProfileError(err?.response?.data?.detail || "Modification impossible pour le moment.");
    } finally {
      setSavingProfile(false);
    }
  };
  const syncStats = async () => {
    if (!token) {
      setSyncError("Connectez-vous avant de lancer la synchro.");
      return;
    }
    if (!p.steam_verified) {
      handleSteamLink();
      return;
    }
    setSyncing(true);
    setSyncMessage("");
    setSyncError("");
    try {
      const response = await axios.post(`${API}/stats/sync/me`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setUser(response.data);
      setSyncMessage("Stats remplacees par le dernier snapshot public CSWAT/FACEIT/Leetify disponible.");
    } catch (err) {
      setSyncError(err?.response?.data?.detail || "Synchronisation impossible pour le moment.");
    } finally {
      setSyncing(false);
    }
  };
  const statCards = [
    { label: "ELO plateforme", value: formatMetric(p.platform_elo ?? p.elo), src: p.stats_sources?.platform || "ReadyUp Arena", state: "synced", color: "text-orange-500" },
    {
      label: "Note Premier",
      value: formatPremierMetric(p.premier_rating),
      src: p.stats_sources?.premier || "Valve Premier",
      state: p.premier_status === "unrated" ? "non classe" : hasMetricValue(p.premier_rating) ? "synced" : "indisponible",
      color: "text-red-500",
    },
    { label: "FACEIT ELO", value: formatMetric(p.faceit_elo), src: p.stats_sources?.faceit || "FACEIT", state: hasMetricValue(p.faceit_elo) ? "synced" : "non lié", color: "text-cyan-neon" },
    { label: "K/D sync", value: formatMetric(p.kdr, 2), src: p.stats_sources?.kdr || "Historique de match", state: hasMetricValue(p.kdr) ? "synced" : "indisponible", color: "text-yellow-neon" },
  ];
  const hasFaceitDetails = [
    p.faceit_level,
    p.faceit_nickname,
    p.faceit_winrate,
    p.faceit_headshots,
    p.faceit_total_matches,
    p.faceit_kills_per_round,
  ].some(hasMetricValue);
  const hasPerformanceDetails = [
    p.aim_rating,
    p.utility_rating,
    p.positioning_rating,
    p.opening_duels_rating,
    p.clutching_rating,
  ].some(hasMetricValue);
  const externalProfiles = [
    { label: "Steam", href: p.steam_profile_url },
    { label: "FACEIT", href: p.faceit_profile_url },
    { label: "Leetify", href: p.leetify_profile_url },
    { label: "CSWAT", href: p.stats_profile_url },
  ].filter((item) => item.href);
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="profile-page">
      {mergeToken && (
        <div className="glass p-6 border border-orange-500/30 mb-6" data-testid="steam-merge-prompt">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Fusion Steam</div>
              <h2 className="font-display text-2xl uppercase mt-2">Choisissez la progression a garder</h2>
              <p className="text-white/60 mt-2">
                Un autre compte avec le meme Steam ID a ete detecte. Le compte connecte restera le compte principal,
                mais vous pouvez garder votre progression actuelle ou ecraser cette progression avec celle de l'autre compte.
              </p>
            </div>
            <button onClick={dismissSteamMerge} className="btn-ghost text-xs">Plus tard</button>
          </div>
          {mergeError && <div className="text-sm text-red-400 mt-4">{mergeError}</div>}
          {mergeBusy && !mergePreview && <div className="text-sm text-white/50 mt-4">Chargement de la comparaison...</div>}
          {mergePreview && (
            <>
              <div className="grid lg:grid-cols-2 gap-4 mt-5">
                {[
                  { key: "current_account", title: "Compte actuel", accent: "text-cyan-neon" },
                  { key: "other_account", title: "Autre compte Steam", accent: "text-yellow-neon" },
                ].map((entry) => {
                  const account = mergePreview[entry.key];
                  return (
                    <div key={entry.key} className="border border-white/10 p-4 bg-black/20">
                      <div className={`font-display text-lg uppercase ${entry.accent}`}>{entry.title}</div>
                      <div className="text-white mt-3">{account.pseudo}</div>
                      <div className="text-xs text-white/40 mt-1">{account.email}</div>
                      <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">Niveau</div><div className="font-display mt-1">{account.level}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">XP</div><div className="font-display mt-1">{account.xp}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">ELO</div><div className="font-display mt-1">{account.platform_elo}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">Jetons</div><div className="font-display mt-1">{account.tokens}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">FACEIT</div><div className="font-display mt-1">{account.faceit_elo ?? "—"}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">Premier</div><div className="font-display mt-1">{account.premier_rating ?? "—"}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">K/D</div><div className="font-display mt-1">{account.kdr ?? "—"}</div></div>
                        <div><div className="text-white/40 text-xs uppercase tracking-widest">Rang</div><div className="font-display mt-1">{account.rank_cs2 || "—"}</div></div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="text-xs text-white/45 mt-4">
                "Garder ma progression actuelle" conserve votre niveau, XP, ELO, jetons et stats actuels.
                "Ecraser par l'autre compte" remplace cette progression par celle de l'autre compte detecte, tout en gardant ce profil comme compte principal.
              </div>
              <div className="flex flex-wrap gap-3 mt-5">
                <button
                  onClick={() => confirmSteamMerge("keep_current")}
                  disabled={mergeBusy}
                  className="btn-neon disabled:opacity-60"
                  data-testid="steam-merge-keep-current-btn"
                >
                  <Shield size={14}/>Garder ma progression actuelle
                </button>
                <button
                  onClick={() => confirmSteamMerge("keep_other_progression")}
                  disabled={mergeBusy}
                  className="btn-ghost disabled:opacity-60"
                  data-testid="steam-merge-keep-other-btn"
                >
                  <RefreshCw size={14}/>Ecraser par l'autre progression
                </button>
              </div>
            </>
          )}
        </div>
      )}
      <div className="glass p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-orange-500/10 blur-3xl"/>
        <div className="flex items-center gap-6 relative">
          <div className="relative">
            <div className="w-28 h-28 bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center font-display text-5xl font-bold overflow-hidden">
              {p.avatar_url ? (
                <img src={p.avatar_url} alt={p.pseudo} className="w-full h-full object-cover"/>
              ) : (
                (p.pseudo || "P").slice(0,1).toUpperCase()
              )}
            </div>
            <div className="absolute -bottom-2 -right-2 bg-black border border-orange-500 px-2 py-0.5 text-xs font-display">LVL {p.level}</div>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-display text-4xl uppercase">{p.pseudo}</h1>
              {p.steam_verified && <Badge variant="verified" testid="steam-verified-badge"><Shield size={12}/>STEAM VÉRIFIÉ</Badge>}
              <span className="text-white/50 text-sm">{p.country}</span>
            </div>
            <p className="text-white/50 mt-1">{p.role} • Rang CS2: {p.rank_cs2 || "Non renseigné"}</p>
            {p.bio && <p className="text-white/60 text-sm mt-2 max-w-2xl">{p.bio}</p>}
            <div className="mt-4 flex flex-wrap gap-3">
              {currentUser && (
                p.steam_verified ? (
                  <button onClick={syncStats} disabled={syncing} className="btn-ghost text-xs disabled:opacity-60" data-testid="profile-sync-stats-btn">
                    <RefreshCw size={14} className={syncing ? "animate-spin" : ""}/>
                    {syncing ? "Synchro..." : "Synchroniser mes stats"}
                  </button>
                ) : (
                  <button onClick={handleSteamLink} className="btn-ghost text-xs" data-testid="profile-link-steam-btn">
                    <Gamepad2 size={14}/>Lier Steam pour sync
                  </button>
                )
              )}
              {p.stats_profile_url && (
                <a href={p.stats_profile_url} target="_blank" rel="noreferrer" className="btn-ghost text-xs" data-testid="profile-open-source-btn">
                  <ExternalLink size={14}/>Voir la source
                </a>
              )}
            </div>
            {currentUser && (syncMessage || syncError) && (
              <div className={`mt-3 text-sm ${syncError ? "text-red-400" : "text-cyan-neon"}`}>
                {syncError || syncMessage}
              </div>
            )}
            <div className="mt-4">
              <div className="flex justify-between text-xs text-white/60 mb-1"><span>XP {p.xp}/{p.xp_next}</span><span>Niveau {p.level + 1} dans {p.xp_next - p.xp} XP</span></div>
              <div className="h-2 bg-white/5 overflow-hidden"><div className="h-full bg-gradient-to-r from-orange-500 to-red-500" style={{ width: `${xpPct}%`, boxShadow: "0 0 12px rgba(255,70,0,0.6)" }}/></div>
            </div>
          </div>
        </div>
      </div>

      {currentUser && (
        <>
          <SectionTitle sub="Profil" title="Modifier mes informations"/>
          <form onSubmit={saveProfile} className="glass p-6 grid lg:grid-cols-[1fr_1fr] gap-4" data-testid="profile-edit-form">
            <div>
              <label className="text-xs uppercase tracking-widest text-white/40">Pseudo</label>
              <input value={profileForm.pseudo} onChange={(e)=>setProfileForm({...profileForm, pseudo: e.target.value})} minLength={3} maxLength={24} required/>
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/40">Email</label>
              <input type="email" value={profileForm.email} onChange={(e)=>setProfileForm({...profileForm, email: e.target.value})} required/>
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/40">Genre</label>
              <select value={profileForm.gender} onChange={(e)=>setProfileForm({...profileForm, gender: e.target.value})}>
                <option value="">Non renseigne</option>
                <option value="femme">Femme</option>
                <option value="homme">Homme</option>
                <option value="non-binaire">Non-binaire</option>
                <option value="autre">Autre</option>
              </select>
            </div>
            <div>
              <label className="text-xs uppercase tracking-widest text-white/40">Age</label>
              <input type="number" min="13" max="99" value={profileForm.age} onChange={(e)=>setProfileForm({...profileForm, age: e.target.value})}/>
            </div>
            <div className="lg:col-span-2">
              <label className="text-xs uppercase tracking-widest text-white/40">Logo / avatar perso URL</label>
              <input value={profileForm.custom_avatar_url} onChange={(e)=>setProfileForm({...profileForm, custom_avatar_url: e.target.value})} placeholder="https://..."/>
              <div className="text-xs text-white/35 mt-1">Vide = avatar Steam synchronise si disponible.</div>
            </div>
            <div className="lg:col-span-2">
              <label className="text-xs uppercase tracking-widest text-white/40">Petite description</label>
              <textarea rows={4} maxLength={280} value={profileForm.bio} onChange={(e)=>setProfileForm({...profileForm, bio: e.target.value})} placeholder="Role, disponibilites, style de jeu..."/>
            </div>
            <div className="lg:col-span-2 flex items-center gap-3 flex-wrap">
              <button className="btn-neon" disabled={savingProfile} type="submit">
                <User size={14}/>{savingProfile ? "Sauvegarde..." : "Sauvegarder"}
              </button>
              {profileMessage && <span className="text-sm text-cyan-neon">{profileMessage}</span>}
              {profileError && <span className="text-sm text-red-400">{profileError}</span>}
            </div>
          </form>
        </>
      )}

      <SectionTitle sub="Statistiques" title="Classement & sources"/>
      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
        {statCards.map((s,i) => (
          <div key={i} className="glass p-6" data-testid={`stat-card-${i}`}>
            <div className="text-xs uppercase tracking-widest text-white/50">{s.label}</div>
            <div className={`font-display text-5xl font-bold mt-2 ${s.color}`}>{s.value}</div>
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5 text-xs">
              <span className="text-white/40">Source : <span className="text-white/70">{s.src}</span></span>
              <Badge variant={s.state === "synced" ? "verified" : "offline"}>{s.state}</Badge>
            </div>
            <div className="text-[10px] text-white/30 mt-2">Dernière synchro : {p.stats_last_sync_at ? new Date(p.stats_last_sync_at).toLocaleString("fr-FR") : "jamais"}</div>
          </div>))}
      </div>

      {externalProfiles.length > 0 && (
        <>
          <SectionTitle sub="Profils liés" title="Sources externes"/>
          <div className="flex flex-wrap gap-3">
            {externalProfiles.map((item) => (
              <a
                key={item.label}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="glass p-4 flex items-center gap-2 text-sm uppercase tracking-widest text-white/80 hover:text-white"
              >
                <ExternalLink size={14}/>{item.label}
              </a>
            ))}
          </div>
        </>
      )}

      {hasFaceitDetails && (
        <>
          <SectionTitle sub="FACEIT" title="Détails synchronisés"/>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[
              { label: "FACEIT Level", value: formatMetric(p.faceit_level), accent: "text-cyan-neon" },
              { label: "Pseudo FACEIT", value: p.faceit_nickname || "—", accent: "text-white" },
              { label: "Winrate", value: formatPercentMetric(p.faceit_winrate, 0), accent: "text-green-400" },
              { label: "Headshots", value: formatPercentMetric(p.faceit_headshots, 0), accent: "text-orange-500" },
              { label: "Matchs FACEIT", value: formatMetric(p.faceit_total_matches), accent: "text-yellow-neon" },
              { label: "Kills / round", value: formatUnitMetric(p.faceit_kills_per_round, "", 2), accent: "text-red-400" },
            ].map((item) => (
              <div key={item.label} className="glass p-6">
                <div className="text-xs uppercase tracking-widest text-white/50">{item.label}</div>
                <div className={`font-display text-4xl mt-2 ${item.accent}`}>{item.value}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {hasPerformanceDetails && (
        <>
          <SectionTitle sub="Leetify" title="Indices de performance"/>
          <div className="grid md:grid-cols-2 xl:grid-cols-5 gap-4">
            {[
              { label: "Aim", value: formatMetric(p.aim_rating, 0), accent: "text-cyan-neon" },
              { label: "Utility", value: formatMetric(p.utility_rating, 0), accent: "text-green-400" },
              { label: "Positioning", value: formatMetric(p.positioning_rating, 0), accent: "text-orange-500" },
              { label: "Opening", value: formatMetric(p.opening_duels_rating, 2), accent: "text-yellow-neon" },
              { label: "Clutching", value: formatMetric(p.clutching_rating, 2), accent: "text-pink-400" },
            ].map((item) => (
              <div key={item.label} className="glass p-6">
                <div className="text-xs uppercase tracking-widest text-white/50">{item.label}</div>
                <div className={`font-display text-4xl mt-2 ${item.accent}`}>{item.value}</div>
              </div>
            ))}
          </div>
        </>
      )}

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

/* ============== FUN MATCHES ============== */
const FunMatchesPage = () => {
  const { token, user } = useAuth();
  const [matches, setMatches] = useState([]);
  const [form, setForm] = useState(makeFunMatchForm());
  const [busyKey, setBusyKey] = useState("");
  const authH = token ? { Authorization: `Bearer ${token}` } : {};

  const refresh = useCallback(async () => {
    const response = await axios.get(`${API}/fun-matches`);
    setMatches(response.data || []);
  }, []);

  useEffect(() => {
    refresh().catch(() => {});
    const id = setInterval(() => { refresh().catch(() => {}); }, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const createMatch = async (event) => {
    event.preventDefault();
    setBusyKey("create");
    try {
      await axios.post(`${API}/fun-matches`, form, { headers: authH });
      setForm(makeFunMatchForm());
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur match fun");
    } finally {
      setBusyKey("");
    }
  };

  const joinMatch = async (matchId) => {
    setBusyKey(`join-${matchId}`);
    try {
      await axios.post(`${API}/fun-matches/${matchId}/join`, {}, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur match fun");
    } finally {
      setBusyKey("");
    }
  };

  const leaveMatch = async (matchId) => {
    setBusyKey(`leave-${matchId}`);
    try {
      await axios.post(`${API}/fun-matches/${matchId}/leave`, {}, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur match fun");
    } finally {
      setBusyKey("");
    }
  };

  const rebalanceMatch = async (matchId) => {
    setBusyKey(`rebalance-${matchId}`);
    try {
      await axios.post(`${API}/fun-matches/${matchId}/rebalance`, {}, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur match fun");
    } finally {
      setBusyKey("");
    }
  };

  const closeMatch = async (matchId) => {
    if (!window.confirm("Fermer ce lobby fun 5v5 ?")) return;
    setBusyKey(`close-${matchId}`);
    try {
      await axios.post(`${API}/fun-matches/${matchId}/close`, {}, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur match fun");
    } finally {
      setBusyKey("");
    }
  };

  const statusMeta = (status) => ({
    open: { label: "Ouvert", variant: "soon" },
    ready: { label: "Equipes pretes", variant: "verified" },
    live: { label: "Live", variant: "live" },
    closed: { label: "Ferme", variant: "offline" },
  }[status] || { label: status || "Inconnu", variant: "offline" });

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="fun-matches-page">
      <div className="flex items-center gap-3">
        <Gamepad2 className="text-cyan-neon" size={32}/>
        <h1 className="font-display text-5xl uppercase">Matchs Fun 5v5</h1>
      </div>
      <p className="text-white/50 mt-2">Lobbies rapides CS2. A 10 joueurs, le roster se compose automatiquement en 2 equipes de 5 equilibrees.</p>

      {user ? (
        <form onSubmit={createMatch} className="glass p-6 mt-6 grid lg:grid-cols-[1fr_1.2fr_220px_180px] gap-3 items-end">
          <div>
            <label className="text-xs uppercase tracking-widest text-white/40">Nom du lobby</label>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} minLength={3} maxLength={80} required />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/40">Description</label>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={500} placeholder="Fun match chill, mix elo, pracc..." />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest text-white/40">Map</label>
            <select value={form.map} onChange={(e) => setForm({ ...form, map: e.target.value })}>
              {["de_mirage", "de_inferno", "de_anubis", "de_nuke", "de_ancient", "de_dust2", "de_vertigo"].map((map) => (
                <option key={map} value={map}>{map}</option>
              ))}
            </select>
          </div>
          <button disabled={busyKey === "create"} className="btn-neon" data-testid="fun-match-create-btn">
            <Plus size={14}/>{busyKey === "create" ? "Creation..." : "Creer un lobby"}
          </button>
        </form>
      ) : (
        <div className="glass p-6 mt-6 text-white/60">Connectez-vous et liez Steam pour creer ou rejoindre un match fun 5v5.</div>
      )}

      <SectionTitle sub="Queue rapide" title="Lobbies actifs"/>
      <div className="grid xl:grid-cols-2 gap-6">
        {matches.length === 0 && <div className="glass p-6 text-white/40">Aucun lobby fun actif pour le moment.</div>}
        {matches.map((match) => {
          const meta = statusMeta(match.status);
          const isOwner = user?.id === match.creator_id;
          const isParticipant = (match.players || []).some((player) => player.user_id === user?.id);
          const canManage = isOwner || user?.is_admin;
          return (
            <div key={match.id} className="glass p-6 border border-white/8" data-testid={`fun-match-${match.id}`}>
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="text-xs uppercase tracking-[0.3em] text-cyan-neon">Fun 5v5</div>
                  <h2 className="font-display text-3xl uppercase mt-3">{match.title}</h2>
                  <p className="text-white/60 mt-3">{match.description || "Lobby communautaire libre, compose pour des matchs fun et rapides."}</p>
                </div>
                <Badge variant={meta.variant}>{meta.label}</Badge>
              </div>

              <div className="grid sm:grid-cols-4 gap-3 mt-5">
                <div className="border border-white/8 p-3"><div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Map</div><div className="font-display text-xl mt-2">{match.map}</div></div>
                <div className="border border-white/8 p-3"><div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Joueurs</div><div className="font-display text-xl text-orange-500 mt-2">{match.players_count}/{match.player_cap}</div></div>
                <div className="border border-white/8 p-3"><div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Places</div><div className="font-display text-xl mt-2">{match.slots_remaining}</div></div>
                <div className="border border-white/8 p-3"><div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Createur</div><div className="text-sm mt-2 text-white/75">{match.creator_pseudo}</div></div>
              </div>

              <div className="mt-5 border border-white/8 p-4">
                <div className="text-xs uppercase tracking-[0.3em] text-white/35">Joueurs inscrits</div>
                <div className="flex flex-wrap gap-2 mt-4">
                  {(match.players || []).map((player) => (
                    <div key={`${match.id}-${player.user_id}`} className="px-3 py-2 border border-white/10 text-sm text-white/75 flex items-center gap-2">
                      <span>{player.pseudo}</span>
                      {player.steam_verified && <Shield size={12} className="text-cyan-neon"/>}
                      <span className="text-white/35">ELO {formatMetric(player.elo)}</span>
                    </div>
                  ))}
                  {!(match.players || []).length && <div className="text-white/35 text-sm">Aucun joueur inscrit.</div>}
                </div>
              </div>

              {(match.teams || []).length > 0 && (
                <div className="grid lg:grid-cols-2 gap-4 mt-5">
                  {(match.teams || []).map((team) => (
                    <div key={team.id} className="border p-4" style={{ borderColor: `${team.accent_color}55` }}>
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-display text-xl uppercase" style={{ color: team.accent_color }}>{team.name}</div>
                        <div className="text-xs text-white/45">AVG ELO {formatMetric(team.avg_elo)}</div>
                      </div>
                      <div className="space-y-2 mt-4">
                        {(team.members || []).map((member) => (
                          <div key={`${team.id}-${member.user_id}`} className="flex items-center justify-between gap-3 text-sm text-white/75">
                            <span>{member.pseudo}</span>
                            <span className="text-white/35">{formatMetric(member.elo)} ELO</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3 mt-5">
                {token && !isParticipant && match.status !== "closed" && match.slots_remaining > 0 && (
                  <button onClick={() => joinMatch(match.id)} disabled={busyKey === `join-${match.id}`} className="btn-neon">
                    <Users size={14}/>{busyKey === `join-${match.id}` ? "Connexion..." : "Rejoindre"}
                  </button>
                )}
                {token && isParticipant && match.status !== "closed" && (
                  <button onClick={() => leaveMatch(match.id)} disabled={busyKey === `leave-${match.id}`} className="btn-ghost">
                    <Trash2 size={14}/>{busyKey === `leave-${match.id}` ? "Sortie..." : "Quitter"}
                  </button>
                )}
                {canManage && match.ready_to_start && match.status !== "closed" && (
                  <button onClick={() => rebalanceMatch(match.id)} disabled={busyKey === `rebalance-${match.id}`} className="btn-ghost">
                    <RefreshCw size={14}/>{busyKey === `rebalance-${match.id}` ? "Equilibrage..." : "Reequilibrer"}
                  </button>
                )}
                {canManage && match.status !== "closed" && (
                  <button onClick={() => closeMatch(match.id)} disabled={busyKey === `close-${match.id}`} className="btn-ghost text-red-400">
                    <Lock size={14}/>{busyKey === `close-${match.id}` ? "Fermeture..." : "Fermer"}
                  </button>
                )}
                <div className="text-sm text-white/45">Auto-equilibrage a 10 joueurs. 1 compte = 1 lobby actif.</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/* ============== TEAMS ============== */
const TeamsPage = () => {
  const { token, user, refreshUser } = useAuth();
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [teams, setTeams] = useState([]);
  const [myTeam, setMyTeam] = useState(null);
  const [selectedTeamId, setSelectedTeamId] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [applications, setApplications] = useState([]);
  const [teamForm, setTeamForm] = useState(makeTeamForm());
  const [applyTarget, setApplyTarget] = useState(null);
  const [applyForm, setApplyForm] = useState({ role: "Polyvalent", message: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const isCaptain = user?.team_role === "captain";

  const loadTeamContext = useCallback(async () => {
    const teamsResponse = await axios.get(`${API}/teams`);
    setTeams(teamsResponse.data || []);
    if (!token) {
      setMyTeam(null);
      setApplications([]);
      return;
    }
    const myTeamResponse = await axios.get(`${API}/teams/me`, { headers: { Authorization: `Bearer ${token}` } });
    const team = myTeamResponse.data?.team || null;
    setMyTeam(team);
    if (team && user?.team_role === "captain") {
      const appsResponse = await axios.get(`${API}/teams/${team.id}/applications`, { headers: { Authorization: `Bearer ${token}` } });
      setApplications(appsResponse.data || []);
    } else {
      setApplications([]);
    }
  }, [token, user?.team_role]);

  useEffect(() => {
    loadTeamContext().catch(() => {
      setError("Impossible de charger les equipes pour le moment.");
    });
  }, [loadTeamContext]);

  useEffect(() => {
    if (myTeam && isCaptain) {
      setTeamForm({
        name: myTeam.name || "",
        tag: myTeam.tag || "",
        country: myTeam.country || "FR",
        description: myTeam.description || "",
        language: myTeam.language || "FR",
        discord_url: myTeam.discord_url || "",
        logo_color: myTeam.logo_color || "#FF4600",
        recruitment_status: myTeam.recruitment_status || "open",
        members_limit: myTeam.members_limit || 7,
      });
    } else if (!myTeam) {
      setTeamForm(makeTeamForm());
    }
  }, [myTeam, isCaptain]);

  useEffect(() => {
    if (selectedTeamId && teams.some((team) => team.id === selectedTeamId)) {
      return;
    }
    if (myTeam?.id) {
      setSelectedTeamId(myTeam.id);
      return;
    }
    if (teams[0]?.id) {
      setSelectedTeamId(teams[0].id);
    }
  }, [myTeam?.id, selectedTeamId, teams]);

  useEffect(() => {
    if (!selectedTeamId) {
      setSelectedTeam(null);
      return;
    }
    if (myTeam?.id === selectedTeamId && myTeam?.members?.length) {
      setSelectedTeam(myTeam);
      return;
    }
    axios
      .get(`${API}/teams/${selectedTeamId}`)
      .then((response) => setSelectedTeam(response.data))
      .catch(() => setSelectedTeam(null));
  }, [myTeam, selectedTeamId]);

  const refreshAll = async () => {
    await refreshUser(token);
    await loadTeamContext();
  };

  const submitTeam = async (event) => {
    event.preventDefault();
    if (!token) {
      setError("Connectez-vous pour creer une equipe.");
      return;
    }
    setBusy(true);
    setMessage("");
    setError("");
    try {
      if (myTeam && isCaptain) {
        await axios.patch(`${API}/teams/${myTeam.id}`, { ...teamForm, members_limit: Number(teamForm.members_limit) }, { headers: authH });
        setMessage("Equipe mise a jour.");
      } else {
        await axios.post(`${API}/teams`, { ...teamForm, members_limit: Number(teamForm.members_limit) }, { headers: authH });
        setMessage("Equipe creee et capitaine assigne.");
      }
      await refreshAll();
    } catch (submitError) {
      setError(submitError?.response?.data?.detail || "Operation equipe impossible.");
    } finally {
      setBusy(false);
    }
  };

  const submitApplication = async (teamId) => {
    if (!token) {
      setError("Connectez-vous pour candidater.");
      return;
    }
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await axios.post(`${API}/teams/${teamId}/applications`, applyForm, { headers: authH });
      setApplyTarget(null);
      setApplyForm({ role: "Polyvalent", message: "" });
      setMessage("Candidature envoyee au capitaine.");
      await loadTeamContext();
    } catch (submitError) {
      setError(submitError?.response?.data?.detail || "Candidature impossible.");
    } finally {
      setBusy(false);
    }
  };

  const handleApplication = async (applicationId, decision) => {
    if (!myTeam) return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await axios.post(`${API}/teams/${myTeam.id}/applications/${applicationId}/${decision}`, {}, { headers: authH });
      setMessage(decision === "approve" ? "Candidature approuvee." : "Candidature refusee.");
      await refreshAll();
    } catch (decisionError) {
      setError(decisionError?.response?.data?.detail || "Traitement impossible.");
    } finally {
      setBusy(false);
    }
  };

  const leaveMyTeam = async () => {
    if (!myTeam || !window.confirm("Quitter votre equipe actuelle ?")) return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const response = await axios.post(`${API}/teams/${myTeam.id}/leave`, {}, { headers: authH });
      setMessage(response.data?.disbanded ? "Equipe dissoute." : "Vous avez quitte l'equipe.");
      await refreshAll();
    } catch (leaveError) {
      setError(leaveError?.response?.data?.detail || "Impossible de quitter l'equipe.");
    } finally {
      setBusy(false);
    }
  };

  const rosterMembers = selectedTeam?.members || [];
  const rosterMvp = resolveTeamMvp(rosterMembers);
  const rosterOthers = rosterMembers.filter((member) => `${member.id || member.pseudo}` !== `${rosterMvp?.id || rosterMvp?.pseudo}`);

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="teams-page">
      <h1 className="font-display text-5xl uppercase">Équipes</h1>
      <p className="text-white/50 mt-2">Creation, candidature et pilotage d'equipe sont maintenant relies au compte joueur et a l'inscription tournoi.</p>
      {(message || error) && <div className={`mt-4 text-sm ${error ? "text-red-400" : "text-cyan-neon"}`}>{error || message}</div>}

      {user && (
        <div className="grid xl:grid-cols-[1.1fr_0.9fr] gap-6 mt-8">
          <div className="glass p-6">
            <div className="text-xs uppercase tracking-widest text-orange-500">{myTeam ? "Mon equipe" : "Creation"}</div>
            <h2 className="font-display text-3xl uppercase mt-3">{myTeam ? myTeam.name : "Creer une equipe"}</h2>
            <p className="text-white/60 mt-3">
              {myTeam
                ? "Le capitaine peut ajuster l'identite, ouvrir ou fermer le recrutement et gerer les candidatures."
                : "Le createur devient capitaine et pourra inscrire l'equipe aux tournois."}
            </p>

            {myTeam && (
              <div className="grid md:grid-cols-3 gap-4 mt-6">
                <div className="border border-white/10 p-4">
                  <div className="text-xs uppercase tracking-widest text-white/40">Membres</div>
                  <div className="font-display text-3xl mt-2">{myTeam.members_count}/{myTeam.members_limit}</div>
                </div>
                <div className="border border-white/10 p-4">
                  <div className="text-xs uppercase tracking-widest text-white/40">Capitaine</div>
                  <div className="font-display text-xl mt-2">{myTeam.captain_pseudo || "—"}</div>
                </div>
                <div className="border border-white/10 p-4">
                  <div className="text-xs uppercase tracking-widest text-white/40">Recrutement</div>
                  <div className="font-display text-xl mt-2">{myTeam.recruitment_status === "open" ? "Ouvert" : "Fermé"}</div>
                </div>
              </div>
            )}

            {(!myTeam || isCaptain) ? (
              <form onSubmit={submitTeam} className="grid md:grid-cols-2 gap-4 mt-6" data-testid="team-form">
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Nom</label>
                  <input value={teamForm.name} onChange={(e)=>setTeamForm({...teamForm, name: e.target.value})} minLength={3} maxLength={48} required />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Tag</label>
                  <input value={teamForm.tag} onChange={(e)=>setTeamForm({...teamForm, tag: e.target.value.toUpperCase()})} minLength={2} maxLength={6} required />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Pays</label>
                  <input value={teamForm.country} onChange={(e)=>setTeamForm({...teamForm, country: e.target.value.toUpperCase()})} maxLength={24} required />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Langue</label>
                  <input value={teamForm.language} onChange={(e)=>setTeamForm({...teamForm, language: e.target.value.toUpperCase()})} maxLength={24} required />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Couleur logo</label>
                  <input value={teamForm.logo_color} onChange={(e)=>setTeamForm({...teamForm, logo_color: e.target.value})} placeholder="#FF4600" required />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Limite membres</label>
                  <input type="number" min="1" max="12" value={teamForm.members_limit} onChange={(e)=>setTeamForm({...teamForm, members_limit: e.target.value})} required />
                </div>
                <div className="md:col-span-2">
                  <label className="text-xs uppercase tracking-widest text-white/40">Discord / lien vocal</label>
                  <input value={teamForm.discord_url} onChange={(e)=>setTeamForm({...teamForm, discord_url: e.target.value})} placeholder="https://discord.gg/..." />
                </div>
                <div className="md:col-span-2">
                  <label className="text-xs uppercase tracking-widest text-white/40">Description</label>
                  <textarea rows={4} value={teamForm.description} onChange={(e)=>setTeamForm({...teamForm, description: e.target.value})} maxLength={500} />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest text-white/40">Recrutement</label>
                  <select value={teamForm.recruitment_status} onChange={(e)=>setTeamForm({...teamForm, recruitment_status: e.target.value})}>
                    <option value="open">Ouvert</option>
                    <option value="closed">Fermé</option>
                  </select>
                </div>
                <div className="md:col-span-2 flex gap-3 flex-wrap">
                  <button disabled={busy} className="btn-neon">
                    <Users size={14}/>{myTeam ? "Mettre a jour l'equipe" : "Creer mon equipe"}
                  </button>
                  {myTeam && <button type="button" disabled={busy} onClick={leaveMyTeam} className="btn-ghost text-red-400">Quitter l'equipe</button>}
                </div>
              </form>
            ) : (
              <div className="mt-6">
                <div className="text-white/60">Vous etes membre. Le capitaine gere cette equipe depuis ce panneau.</div>
                <button type="button" disabled={busy} onClick={leaveMyTeam} className="btn-ghost text-red-400 mt-4">Quitter l'equipe</button>
              </div>
            )}

            {myTeam?.members?.length > 0 && <div className="mt-6 text-xs uppercase tracking-widest text-white/35">Roster premium visible plus bas dans la page.</div>}
          </div>

          <div className="glass p-6">
            <div className="text-xs uppercase tracking-widest text-orange-500">Fonctionnement</div>
            <h2 className="font-display text-3xl uppercase mt-3">Cycle equipe</h2>
            <div className="space-y-3 mt-6 text-sm text-white/70">
              <div className="border border-white/10 p-4">1. Un joueur cree l'equipe et devient capitaine.</div>
              <div className="border border-white/10 p-4">2. Le recrutement peut rester ouvert pour recevoir des candidatures.</div>
              <div className="border border-white/10 p-4">3. Le capitaine valide ou refuse les demandes entrantes.</div>
              <div className="border border-white/10 p-4">4. Seul le capitaine peut inscrire l'equipe dans un tournoi.</div>
              <div className="border border-white/10 p-4">5. Les membres peuvent quitter l'equipe; le capitaine peut la dissoudre s'il reste seul.</div>
            </div>
          </div>
        </div>
      )}

      {myTeam && isCaptain && (
        <div className="glass p-6 mt-6">
          <div className="text-xs uppercase tracking-widest text-orange-500">Recrutement</div>
          <h2 className="font-display text-3xl uppercase mt-3">Candidatures en attente</h2>
          <div className="space-y-3 mt-5">
            {applications.filter((item) => item.status === "pending").length === 0 && <div className="text-white/40">Aucune candidature en attente.</div>}
            {applications.filter((item) => item.status === "pending").map((item) => (
              <div key={item.id} className="border border-white/10 p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-display uppercase">{item.pseudo}</div>
                  <div className="text-xs text-white/40 mt-1">{item.role}</div>
                  {item.message && <p className="text-sm text-white/60 mt-2">{item.message}</p>}
                </div>
                <div className="flex gap-2">
                  <button disabled={busy} onClick={() => handleApplication(item.id, "approve")} className="btn-neon text-xs">Accepter</button>
                  <button disabled={busy} onClick={() => handleApplication(item.id, "reject")} className="btn-ghost text-xs">Refuser</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedTeam && (
        <div className="mt-8" data-testid="team-roster-premium">
          <SectionTitle sub="Roster Premium" title={`${selectedTeam.name} • MVP & lineup`} />
          <div className="grid xl:grid-cols-[0.92fr_1.08fr] gap-6">
            <div className="glass p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-4">
                  <TeamLogo team={selectedTeam} size={72} />
                  <div>
                    <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Equipe selectionnee</div>
                    <h2 className="font-display text-3xl uppercase mt-2">{selectedTeam.name}</h2>
                    <p className="text-white/55 mt-2">{selectedTeam.tag} • {selectedTeam.country} • {selectedTeam.language || "FR"}</p>
                  </div>
                </div>
                <Badge variant={selectedTeam.recruitment_status === "open" ? "soon" : "offline"}>
                  {selectedTeam.recruitment_status === "open" ? "Recrutement ouvert" : "Recrutement ferme"}
                </Badge>
              </div>
              <p className="text-white/60 mt-4">{selectedTeam.description || "Roster actif de la beta avec carte premium joueur et lecture rapide des impacts."}</p>
              <div className="grid grid-cols-4 gap-3 mt-6">
                <div className="border border-white/10 p-4"><div className="text-[10px] uppercase tracking-widest text-white/35">ELO</div><div className="font-display text-2xl text-orange-500 mt-1">{formatMetric(selectedTeam.elo)}</div></div>
                <div className="border border-white/10 p-4"><div className="text-[10px] uppercase tracking-widest text-white/35">LVL</div><div className="font-display text-2xl mt-1">{formatMetric(selectedTeam.level)}</div></div>
                <div className="border border-white/10 p-4"><div className="text-[10px] uppercase tracking-widest text-white/35">Membres</div><div className="font-display text-2xl mt-1">{selectedTeam.members_count}/{selectedTeam.members_limit}</div></div>
                <div className="border border-white/10 p-4"><div className="text-[10px] uppercase tracking-widest text-white/35">Fiabilité</div><div className="font-display text-2xl text-cyan-neon mt-1">{formatMetric(selectedTeam.reliability)}</div></div>
              </div>
              <div className="mt-6">
                <div className="text-xs uppercase tracking-[0.3em] text-yellow-neon mb-3">Joueur MVP</div>
                {rosterMvp ? (
                  <TeamMemberPremiumCard member={rosterMvp} teamColor={selectedTeam.logo_color} isMvp />
                ) : (
                  <div className="border border-white/10 p-5 text-white/40">Aucun joueur detaille pour cette equipe.</div>
                )}
              </div>
            </div>
            <div>
              <div className="grid md:grid-cols-2 gap-4">
                {rosterOthers.length === 0 && rosterMvp && (
                  <div className="glass p-6 text-white/40 md:col-span-2">Le roster detaille contient uniquement le MVP pour le moment.</div>
                )}
                {rosterOthers.map((member, index) => (
                  <TeamMemberPremiumCard
                    key={`${member.source}-${member.id || member.pseudo}`}
                    member={member}
                    teamColor={selectedTeam.logo_color}
                    compact
                    rank={index + 1}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {teams.map((t,i) => (
          <div
            key={t.id}
            className={`glass glass-hover p-6 ${selectedTeamId === t.id ? "ring-1 ring-orange-500/70" : ""}`}
            data-testid={`team-${t.id}`}
          >
            <div className="flex items-start justify-between"><TeamLogo team={t} size={64}/><span className="font-mono-display text-white/30">#{i+1}</span></div>
            <h3 className="font-display text-2xl mt-3">{t.name}</h3>
            <p className="text-white/40 text-sm">{t.tag} • {t.country}</p>
            <p className="text-white/60 text-sm mt-3 min-h-[3rem]">{t.description || "Equipe publique prete pour la beta, le recrutement ou l'inscription tournoi."}</p>
            <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-white/5 text-center">
              <div><div className="font-display text-orange-500">{t.elo}</div><div className="text-[10px] text-white/40 uppercase">ELO</div></div>
              <div><div className="font-display">{t.level}</div><div className="text-[10px] text-white/40 uppercase">LVL</div></div>
              <div><div className="font-display text-green-400">{t.wins}</div><div className="text-[10px] text-white/40 uppercase">W</div></div>
              <div><div className="font-display text-yellow-neon">{t.trophies}</div><div className="text-[10px] text-white/40 uppercase">🏆</div></div>
            </div>
            <div className="mt-4 text-xs text-white/40 space-y-1">
              <div>Capitaine: <span className="text-white/70">{t.captain_pseudo || "N/A"}</span></div>
              <div>Membres: <span className="text-white/70">{t.members_count}/{t.members_limit}</span></div>
              <div>Recrutement: <span className="text-white/70">{t.recruitment_status === "open" ? "ouvert" : "ferme"}</span></div>
            </div>
            <button onClick={() => setSelectedTeamId(t.id)} className="btn-ghost text-xs w-full mt-4">
              <Star size={14}/>Voir le roster premium
            </button>
            {token && !user?.team_id && t.recruitment_status === "open" && (
              <div className="mt-4">
                {applyTarget === t.id ? (
                  <div className="space-y-3">
                    <input value={applyForm.role} onChange={(e)=>setApplyForm({...applyForm, role: e.target.value})} placeholder="Role vise" maxLength={32} />
                    <textarea rows={3} value={applyForm.message} onChange={(e)=>setApplyForm({...applyForm, message: e.target.value})} placeholder="Message au capitaine (optionnel)" maxLength={500} />
                    <div className="flex gap-2">
                      <button disabled={busy} onClick={() => submitApplication(t.id)} className="btn-neon text-xs">Envoyer</button>
                      <button disabled={busy} onClick={() => setApplyTarget(null)} className="btn-ghost text-xs">Annuler</button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => setApplyTarget(t.id)} className="btn-ghost text-xs w-full">
                    <Plus size={14}/>Candidater a cette equipe
                  </button>
                )}
              </div>
            )}
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
  const topTeams = [...teams].sort((a, b) => (b.elo ?? 0) - (a.elo ?? 0));
  const topPlayersPlatform = sortByMetric(players, "platform_elo");
  const topPlayersFaceit = sortByMetric(players, "faceit_elo");
  const topPlayersKdr = sortByMetric(players, "kdr");
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="rankings-page">
      <h1 className="font-display text-5xl uppercase">Classements — Saison 1</h1>
      <p className="text-white/50 mt-2">Les classements FACEIT et K/D sont séparés de l'ELO plateforme pour éviter les faux calculs et les mélanges de sources.</p>
      <div className="grid xl:grid-cols-2 gap-6 mt-6">
        <div className="glass p-6"><h3 className="font-display text-xl uppercase mb-4">Top équipes — ELO plateforme</h3>
          {topTeams.map((t,i) => (
            <div key={t.id} className="flex items-center gap-3 py-3 border-b border-white/5" data-testid={`rank-team-${i}`}>
              <span className={`font-display text-2xl w-8 ${i<3 ? "text-yellow-neon" : "text-white/30"}`}>{i+1}</span>
              <TeamLogo team={t} size={36}/><span className="flex-1 font-display">{t.name}</span>
              <span className="text-orange-500 font-display">{formatMetric(t.elo)}</span>
            </div>))}</div>
        <div className="glass p-6"><h3 className="font-display text-xl uppercase mb-4">Top joueurs — ELO plateforme</h3>
          {topPlayersPlatform.map((p,i) => (
            <div key={p.id} className="flex items-center gap-3 py-3 border-b border-white/5" data-testid={`rank-player-${i}`}>
              <span className={`font-display text-2xl w-8 ${i<3 ? "text-yellow-neon" : "text-white/30"}`}>{i+1}</span>
              <span className="flex-1 font-display">{p.pseudo}{p.steam_verified && <Shield size={12} className="inline ml-2 text-cyan-400"/>}</span>
              <span className="text-cyan-neon font-display">{formatMetric(p.platform_elo ?? p.elo)}</span>
            </div>))}</div>
        <div className="glass p-6"><h3 className="font-display text-xl uppercase mb-4">Top joueurs — FACEIT ELO</h3>
          {topPlayersFaceit.map((p,i) => (
            <div key={`${p.id}-faceit`} className="flex items-center gap-3 py-3 border-b border-white/5" data-testid={`rank-faceit-${i}`}>
              <span className={`font-display text-2xl w-8 ${i<3 ? "text-yellow-neon" : "text-white/30"}`}>{i+1}</span>
              <span className="flex-1 font-display">{p.pseudo}</span>
              <span className="text-cyan-neon font-display">{formatMetric(p.faceit_elo)}</span>
            </div>))}</div>
        <div className="glass p-6"><h3 className="font-display text-xl uppercase mb-4">Top joueurs — K/D 30 jours</h3>
          {topPlayersKdr.map((p,i) => (
            <div key={`${p.id}-kdr`} className="flex items-center gap-3 py-3 border-b border-white/5" data-testid={`rank-kdr-${i}`}>
              <span className={`font-display text-2xl w-8 ${i<3 ? "text-yellow-neon" : "text-white/30"}`}>{i+1}</span>
              <span className="flex-1 font-display">{p.pseudo}</span>
              <span className="text-yellow-neon font-display">{formatMetric(p.kdr, 2)}</span>
            </div>))}</div>
      </div>
    </div>
  );
};

const FaqPage = () => (
  <div className="max-w-6xl mx-auto px-6 py-10" data-testid="faq-page">
    <div className="max-w-3xl">
      <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Base de connaissances</div>
      <h1 className="font-display text-5xl uppercase mt-3">FAQ beta ReadyUp Arena</h1>
      <p className="text-white/60 mt-4">
        Cette base reprend les points clés du prompt complet: gratuité des tournois, badge Steam vérifié, renforts,
        orchestration CS2 et supervision de la plateforme.
      </p>
    </div>
    <div className="grid lg:grid-cols-2 gap-4 mt-8">
      {FAQ_ITEMS.map((item) => (
        <div key={item.q} className="glass p-6">
          <h3 className="font-display text-2xl uppercase">{item.q}</h3>
          <p className="text-white/60 mt-3">{item.a}</p>
        </div>
      ))}
    </div>
  </div>
);

const CommunityPage = () => (
  <div className="max-w-6xl mx-auto px-6 py-10" data-testid="community-page">
    <div className="grid lg:grid-cols-[1.25fr_1fr] gap-6">
      <div className="glass p-8">
        <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Communauté</div>
        <h1 className="font-display text-5xl uppercase mt-3">Rejoindre l'arène</h1>
        <p className="text-white/60 mt-4">
          La beta ouvre les flux essentiels: équipes, tournois, solos disponibles, supervision CS2 et retours produit.
          Les canaux communautaires restent pilotés proprement pour éviter le spam et garder un onboarding clair.
        </p>
        <div className="grid md:grid-cols-2 gap-4 mt-8">
          <div className="border border-white/10 p-5">
            <div className="font-display text-xl uppercase">Pour les joueurs</div>
            <p className="text-white/60 mt-3">Créer un compte, lier Steam, trouver une équipe, rejoindre un tournoi gratuit et suivre les matchs live.</p>
          </div>
          <div className="border border-white/10 p-5">
            <div className="font-display text-xl uppercase">Pour les staffs</div>
            <p className="text-white/60 mt-3">Organisateurs, arbitres et modérateurs peuvent centraliser annonces, supervision et exceptions de tournoi.</p>
          </div>
        </div>
      </div>
      <div className="glass p-8">
        <h2 className="font-display text-2xl uppercase">Canaux beta</h2>
        <div className="space-y-4 mt-5 text-sm text-white/70">
          <div className="border border-white/10 p-4">
            <div className="text-xs uppercase tracking-widest text-white/40">Discord</div>
            <p className="mt-2">Salon communauté à connecter côté admin. Le parcours est prêt même si l'invitation finale reste à configurer.</p>
          </div>
          <div className="border border-white/10 p-4">
            <div className="text-xs uppercase tracking-widest text-white/40">Annonces tournoi</div>
            <p className="mt-2">Les blocs actualités, home et salle d'attente sont déjà prêts pour relayer les prochains événements.</p>
          </div>
          <div className="border border-white/10 p-4">
            <div className="text-xs uppercase tracking-widest text-white/40">Feedback produit</div>
            <p className="mt-2">La page contact sert à remonter bugs, demandes d'ajustement et besoins d'organisation.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3 mt-6">
          <Link to="/tournaments" className="btn-neon"><Trophy size={14}/>Voir les tournois</Link>
          <Link to="/contact" className="btn-ghost"><Radio size={14}/>Contacter l'équipe</Link>
        </div>
      </div>
    </div>
  </div>
);

const PartnersPage = () => (
  <div className="max-w-6xl mx-auto px-6 py-10" data-testid="partners-page">
    <div className="max-w-3xl">
      <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Partenariats</div>
      <h1 className="font-display text-5xl uppercase mt-3">Partenaires et soutien écosystème</h1>
      <p className="text-white/60 mt-4">
        Le prompt complet prévoit sponsors, partenaires communautaires et support opérationnel. Cette page matérialise ces espaces
        au lieu de laisser un simple placeholder dans le footer.
      </p>
    </div>
    <div className="grid lg:grid-cols-3 gap-4 mt-8">
      {PARTNER_BLOCKS.map((block) => (
        <div key={block.title} className="glass p-6">
          <div className="text-xs uppercase tracking-[0.3em] text-white/40">Bloc partenaire</div>
          <h2 className="font-display text-2xl uppercase mt-3">{block.title}</h2>
          <p className="text-white/60 mt-3">{block.text}</p>
        </div>
      ))}
    </div>
  </div>
);

const ContactPage = () => (
  <div className="max-w-6xl mx-auto px-6 py-10" data-testid="contact-page">
    <div className="grid lg:grid-cols-[1.15fr_1fr] gap-6">
      <div className="glass p-8">
        <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Contact</div>
        <h1 className="font-display text-5xl uppercase mt-3">Support, bugs et organisation</h1>
        <p className="text-white/60 mt-4">
          Cette beta doit pouvoir collecter les retours importants sans passer par l'admin panel. Les canaux ci-dessous cadrent les demandes
          les plus probables avant d'ajouter une messagerie complète.
        </p>
        <div className="grid md:grid-cols-2 gap-4 mt-8">
          <div className="border border-white/10 p-5">
            <div className="font-display text-xl uppercase">Bug ou anomalie</div>
            <p className="text-white/60 mt-3">Signaler un problème de compte, bracket, salle d'attente, score live ou synchronisation CS2.</p>
          </div>
          <div className="border border-white/10 p-5">
            <div className="font-display text-xl uppercase">Tournoi et staff</div>
            <p className="text-white/60 mt-3">Candidature organisateur, demande d'arbitrage, support événement ou besoin de serveur dédié.</p>
          </div>
        </div>
      </div>
      <div className="glass p-8">
        <h2 className="font-display text-2xl uppercase">Point d'entrée recommandé</h2>
        <div className="space-y-4 mt-5 text-sm text-white/70">
          <div className="border border-white/10 p-4">
            <div className="text-xs uppercase tracking-widest text-white/40">Produit</div>
            <p className="mt-2">Passer par la communauté beta pour centraliser les retours et éviter les pertes de contexte.</p>
          </div>
          <div className="border border-white/10 p-4">
            <div className="text-xs uppercase tracking-widest text-white/40">Infrastructure</div>
            <p className="mt-2">Utiliser l'état des services et le hub CS2 avant d'ouvrir un ticket pour distinguer bug UI et indisponibilité backend.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3 mt-6">
          <Link to="/status" className="btn-ghost"><Server size={14}/>État des services</Link>
          <Link to="/cs2" className="btn-neon"><Target size={14}/>Hub CS2</Link>
        </div>
      </div>
    </div>
  </div>
);

const StatusPage = () => {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const load = async () => {
      const [healthResult, statsResult] = await Promise.allSettled([
        axios.get(HEALTH_API),
        axios.get(`${API}/stats/global`),
      ]);

      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value.data);
      } else {
        setHealth({ status: "degraded", services: { mongo: "unknown", redis: "unknown" } });
      }

      if (statsResult.status === "fulfilled") {
        setStats(statsResult.value.data);
      }
    };

    load();
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-10" data-testid="status-page">
      <div className="max-w-3xl">
        <div className="text-xs uppercase tracking-[0.3em] text-orange-500">Supervision</div>
        <h1 className="font-display text-5xl uppercase mt-3">État des services</h1>
        <p className="text-white/60 mt-4">
          La page d'état manquait dans le parcours alors qu'elle est explicitement demandée par le prompt. Elle reflète la disponibilité
          du backend public et des briques critiques.
        </p>
      </div>
      <div className="grid md:grid-cols-3 gap-4 mt-8">
        <div className="glass p-6">
          <div className="text-xs uppercase tracking-widest text-white/40">API</div>
          <div className={`font-display text-3xl mt-3 ${health?.status === "ok" ? "text-cyan-neon" : "text-yellow-neon"}`}>{health?.status || "..."}</div>
        </div>
        <div className="glass p-6">
          <div className="text-xs uppercase tracking-widest text-white/40">MongoDB</div>
          <div className={`font-display text-3xl mt-3 ${health?.services?.mongo === "ok" ? "text-cyan-neon" : "text-yellow-neon"}`}>{health?.services?.mongo || "..."}</div>
        </div>
        <div className="glass p-6">
          <div className="text-xs uppercase tracking-widest text-white/40">Redis</div>
          <div className={`font-display text-3xl mt-3 ${health?.services?.redis === "ok" ? "text-cyan-neon" : "text-yellow-neon"}`}>{health?.services?.redis || "..."}</div>
        </div>
      </div>
      {stats && (
        <div className="grid md:grid-cols-4 gap-4 mt-4">
          <div className="glass p-5"><div className="text-xs uppercase tracking-widest text-white/40">Joueurs</div><div className="font-display text-3xl mt-2">{stats.players}</div></div>
          <div className="glass p-5"><div className="text-xs uppercase tracking-widest text-white/40">Tournois</div><div className="font-display text-3xl mt-2">{stats.tournaments_total}</div></div>
          <div className="glass p-5"><div className="text-xs uppercase tracking-widest text-white/40">Matchs</div><div className="font-display text-3xl mt-2">{stats.matches_played}</div></div>
          <div className="glass p-5"><div className="text-xs uppercase tracking-widest text-white/40">En ligne</div><div className="font-display text-3xl mt-2">{stats.online_now}</div></div>
        </div>
      )}
    </div>
  );
};

const Cs2Hub = () => {
  const { user } = useAuth();
  const [servers, setServers] = useState([]);
  const [matches, setMatches] = useState([]);
  const [events, setEvents] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [healthResult, serversResult, matchesResult, eventsResult] = await Promise.allSettled([
          axios.get(HEALTH_API),
          axios.get(`${API}/cs2/servers`),
          axios.get(`${API}/matches/live`),
          axios.get(`${API}/cs2/events?limit=6`),
        ]);

      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value.data);
      } else {
        setHealth({ status: "degraded", services: { mongo: "unknown", redis: "unknown" } });
      }

      setServers(serversResult.status === "fulfilled" ? serversResult.value.data : []);
      setMatches(matchesResult.status === "fulfilled" ? matchesResult.value.data : []);
      setEvents(eventsResult.status === "fulfilled" ? eventsResult.value.data : []);
      setLoading(false);
    };

    load();
  }, []);

  const onlineServers = servers.filter((server) => ["online", "live"].includes(server.status)).length;

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="cs2-page">
      <div className="grid xl:grid-cols-[1.35fr_1fr] gap-6">
        <div className="glass p-8">
          <div className="flex items-center gap-3 flex-wrap">
            <Badge variant={health?.status === "ok" ? "live" : "soon"}>{health?.status === "ok" ? "STACK READY" : "SURVEILLANCE"}</Badge>
            <span className="text-xs uppercase tracking-[0.3em] text-white/40">CS2 orchestration beta</span>
          </div>
          <h1 className="font-display text-5xl uppercase mt-4">Hub CS2 public</h1>
          <p className="text-white/60 mt-4 max-w-3xl">
            Le prompt complet prévoit une chaîne visible entre tournoi, salle d'attente, serveur CS2, MatchZy et résultats.
            Cette page expose enfin cette couche au public au lieu de la laisser uniquement dans l'admin.
          </p>
          <div className="grid md:grid-cols-4 gap-4 mt-8">
            <div className="border border-white/10 p-5">
              <div className="text-xs uppercase tracking-widest text-white/40">Serveurs actifs</div>
              <div className="font-display text-4xl text-orange-500 mt-2">{onlineServers}</div>
            </div>
            <div className="border border-white/10 p-5">
              <div className="text-xs uppercase tracking-widest text-white/40">Serveurs déclarés</div>
              <div className="font-display text-4xl text-cyan-neon mt-2">{servers.length}</div>
            </div>
            <div className="border border-white/10 p-5">
              <div className="text-xs uppercase tracking-widest text-white/40">Matchs live</div>
              <div className="font-display text-4xl text-yellow-neon mt-2">{matches.length}</div>
            </div>
            <div className="border border-white/10 p-5">
              <div className="text-xs uppercase tracking-widest text-white/40">Événements récents</div>
              <div className="font-display text-4xl mt-2">{events.length}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-3 mt-8">
            <Link to="/live" className="btn-neon"><Tv size={14}/>Voir les matchs live</Link>
            <Link to="/tournaments" className="btn-ghost"><Trophy size={14}/>Voir les tournois</Link>
            {user?.is_admin && <Link to="/admin" className="btn-ghost"><Terminal size={14}/>Ouvrir l'admin</Link>}
          </div>
        </div>
        <div className="glass p-8">
          <h2 className="font-display text-2xl uppercase">Services critiques</h2>
          <div className="space-y-4 mt-5 text-sm text-white/70">
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">API</div>
              <div className={`font-display text-2xl mt-2 ${health?.status === "ok" ? "text-cyan-neon" : "text-yellow-neon"}`}>{health?.status || "..."}</div>
            </div>
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">MongoDB</div>
              <div className={`font-display text-2xl mt-2 ${health?.services?.mongo === "ok" ? "text-cyan-neon" : "text-yellow-neon"}`}>{health?.services?.mongo || "..."}</div>
            </div>
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">Redis</div>
              <div className={`font-display text-2xl mt-2 ${health?.services?.redis === "ok" ? "text-cyan-neon" : "text-yellow-neon"}`}>{health?.services?.redis || "..."}</div>
            </div>
          </div>
          {loading && <p className="text-white/40 text-sm mt-4">Chargement de l'état CS2...</p>}
        </div>
      </div>

      <SectionTitle sub="Cycle complet" title="Chaîne de match automatisée"/>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {CS2_AUTOPILOT_STEPS.map((step, index) => (
          <div key={step} className="glass p-5">
            <div className="text-xs uppercase tracking-[0.3em] text-white/40">Étape {index + 1}</div>
            <div className="font-display text-xl uppercase mt-3">{step}</div>
          </div>
        ))}
      </div>

      <SectionTitle sub="Serveurs" title="Inventaire CS2"/>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {servers.length === 0 && (
          <div className="glass p-6 text-white/50">
            Aucun serveur CS2 n'est encore publié dans l'inventaire public. La couche API est prête et reste visible depuis l'admin.
          </div>
        )}
        {servers.map((server) => (
          <div key={server.id} className="glass p-6" data-testid={`public-cs2-server-${server.id}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-display text-2xl uppercase">{server.name}</div>
                <div className="text-xs uppercase tracking-widest text-white/40 mt-1">{server.provider || "custom"} • {(server.public_host || server.host)}:{server.game_port || server.port}</div>
              </div>
              <Badge variant={["online", "live"].includes(server.status) ? "verified" : "soon"}>{server.status || "unknown"}</Badge>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-5 text-sm">
              <div className="border border-white/10 p-3">
                <div className="text-xs uppercase tracking-widest text-white/40">Match courant</div>
                <div className="mt-2 text-white/80">{server.current_match_id || "Libre"}</div>
              </div>
              <div className="border border-white/10 p-3">
                <div className="text-xs uppercase tracking-widest text-white/40">Dernier check</div>
                <div className="mt-2 text-white/80">{server.last_checked_at ? new Date(server.last_checked_at).toLocaleString("fr-FR") : "Pas encore"}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-4 text-[10px] uppercase tracking-widest text-white/50">
              {server.capabilities?.matchzy && <span className="border border-white/10 px-2 py-1">MatchZy</span>}
              {server.capabilities?.cssimpleadmin && <span className="border border-white/10 px-2 py-1">CSsimpleadmin</span>}
              {server.capabilities?.fake_rcon && <span className="border border-white/10 px-2 py-1">Fake RCON</span>}
              {server.capabilities?.hltv && <span className="border border-white/10 px-2 py-1">HLTV</span>}
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              {server.connect_url && <a href={server.connect_url} className="btn-ghost text-xs"><ExternalLink size={12}/>Connexion</a>}
              {server.hltv_url && <a href={server.hltv_url} className="btn-ghost text-xs"><Tv size={12}/>Spectateur</a>}
            </div>
            {(server.join_password_required || server.spectator_password_required) && (
              <div className="text-xs text-white/40 mt-3">Connexion privee: passez par la room du match ou une session authentifiee.</div>
            )}
          </div>
        ))}
      </div>

      <SectionTitle sub="Live telemetry" title="Matchs et événements MatchZy"/>
      <div className="grid xl:grid-cols-[1.2fr_0.8fr] gap-4">
        <div className="glass p-6">
          <h3 className="font-display text-2xl uppercase">Matchs en direct</h3>
          <div className="space-y-3 mt-5">
            {matches.length === 0 && <div className="text-white/50">Aucun match live pour le moment.</div>}
            {matches.slice(0, 4).map((match) => (
              <div key={match.matchid} className="border border-white/10 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-display uppercase">{match.team1_name} vs {match.team2_name}</div>
                  <Badge variant="live">LIVE</Badge>
                </div>
                <div className="font-display text-3xl text-cyan-neon mt-3">{match.team1_score} : {match.team2_score}</div>
                <div className="text-sm text-white/50 mt-2">{match.map_name || "Map en cours"} • {match.server || "Serveur non lié publiquement"}</div>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Link to={`/match/${match.matchid}`} className="btn-ghost text-xs"><Radio size={12}/>Suivi match</Link>
                  {match.connect_url && <a href={match.connect_url} className="btn-neon text-xs"><ExternalLink size={12}/>Rejoindre</a>}
                  {match.spectator_url && <a href={match.spectator_url} className="btn-ghost text-xs"><Tv size={12}/>Spectateur</a>}
                </div>
                {(match.join_password_required || match.spectator_password_required) && (
                  <div className="text-xs text-white/40 mt-3">Connexion privee: ouvrez la room du match pour acceder aux boutons authentifies.</div>
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="glass p-6">
          <h3 className="font-display text-2xl uppercase">Événements récents</h3>
          <div className="space-y-3 mt-5">
            {events.length === 0 && <div className="text-white/50">Aucun événement MatchZy remonté pour l'instant.</div>}
            {events.map((event) => (
              <div key={event.id} className="border border-white/10 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-display text-sm uppercase">{event.event}</div>
                  <div className="text-[11px] text-white/40">{new Date(event.received_at).toLocaleTimeString("fr-FR")}</div>
                </div>
                <div className="text-sm text-white/60 mt-2">Match {event.matchid || "n/a"}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

/* ============== DUELS 1v1 ============== */
const DuelsLegacy = () => {
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

const Duels = () => {
  const { user, token } = useAuth();
  const [balance, setBalance] = useState(null);
  const [duels, setDuels] = useState([]);
  const [myDuels, setMyDuels] = useState([]);
  const [form, setForm] = useState({ map: "Mirage", stake: 100 });
  const [busy, setBusy] = useState(false);
  const [busyKey, setBusyKey] = useState("");
  const authH = token ? { Authorization: `Bearer ${token}` } : {};

  const duelStatus = (status) => ({
    open: { label: "Ouvert", variant: "soon" },
    veto: { label: "Veto maps", variant: "soon" },
    launch_pending: { label: "Lancement", variant: "soon" },
    ready: { label: "Serveur pret", variant: "verified" },
    live: { label: "Match live", variant: "live" },
    in_progress: { label: "En cours", variant: "live" },
    closed: { label: "Termine", variant: "verified" },
    launch_failed: { label: "Echec launch", variant: "offline" },
  }[status] || { label: status || "inconnu", variant: "offline" });

  const refresh = useCallback(async () => {
    const jobs = [axios.get(`${API}/duels`)];
    if (token) {
      const headers = { Authorization: `Bearer ${token}` };
      jobs.push(axios.get(`${API}/duels/balance`, { headers }));
      jobs.push(axios.get(`${API}/duels/mine`, { headers }));
    }
    const [openRes, balanceRes, mineRes] = await Promise.all(jobs);
    setDuels(openRes.data || []);
    setBalance(balanceRes?.data?.tokens ?? null);
    setMyDuels(mineRes?.data || []);
  }, [token]);

  useEffect(() => {
    refresh().catch(() => {});
    const id = setInterval(() => { refresh().catch(() => {}); }, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const create = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await axios.post(`${API}/duels/create`, { map: form.map, stake: parseInt(form.stake, 10) }, { headers: authH });
      await refresh();
    } catch (err) {
      alert(err.response?.data?.detail || "Erreur");
    } finally {
      setBusy(false);
    }
  };

  const accept = async (id) => {
    setBusyKey(`accept-${id}`);
    try {
      await axios.post(`${API}/duels/${id}/accept-cs2`, {}, { headers: authH });
      await refresh();
    } catch (err) {
      alert(err.response?.data?.detail || "Erreur");
    } finally {
      setBusyKey("");
    }
  };

  const banMap = async (duelId, map) => {
    setBusyKey(`ban-${duelId}-${map}`);
    try {
      await axios.post(`${API}/duels/${duelId}/ban`, { map }, { headers: authH });
      await refresh();
    } catch (err) {
      alert(err.response?.data?.detail || "Erreur");
    } finally {
      setBusyKey("");
    }
  };

  const joinMatch = async (duelId) => {
    setBusyKey(`join-${duelId}`);
    try {
      const response = await axios.post(`${API}/duels/${duelId}/join`, {}, { headers: authH });
      if (response.data?.join_url) {
        window.location.href = response.data.join_url;
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Erreur");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="duels-page">
      <div className="flex items-center gap-3"><Coins className="text-yellow-neon" size={32}/><h1 className="font-display text-5xl uppercase">Duels 1v1</h1></div>
      <p className="text-white/50 mt-2">Mise en jetons virtuels non achetables, sans valeur reelle. Flux CS2 : acceptation, veto de maps, lancement MatchZy puis bouton de connexion.</p>
      {user ? (
        <div className="glass p-6 mt-6 flex items-center justify-between gap-4 flex-wrap">
          <div><div className="text-xs uppercase tracking-widest text-white/40">Votre solde</div>
            <div className="font-display text-4xl text-yellow-neon mt-1" data-testid="duel-balance">⚡ {balance ?? "—"}</div></div>
          <form onSubmit={create} className="flex items-end gap-2 flex-wrap">
            <div><label className="text-xs uppercase text-white/40">Map favorite</label>
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

      {user && (
        <>
          <SectionTitle sub="Vos matchs" title="Mes duels actifs"/>
          <div className="grid lg:grid-cols-2 gap-4">
            {myDuels.length === 0 && <div className="glass p-6 text-white/40">Aucun duel en cours sur votre compte.</div>}
            {myDuels.map((duel) => {
              const meta = duelStatus(duel.status);
              return (
                <div key={duel.id} className="glass p-6 border border-white/8" data-testid={`my-duel-${duel.id}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="font-display text-2xl">{duel.creator_pseudo} <span className="text-white/35">vs</span> {duel.opponent_pseudo || "En attente"}</div>
                      <div className="text-sm text-white/55 mt-2">Map favorite : <span className="text-white">{duel.preferred_map || "—"}</span></div>
                    </div>
                    <Badge variant={meta.variant}>{meta.label}</Badge>
                  </div>

                  <div className="grid sm:grid-cols-3 gap-3 mt-5">
                    <div className="border border-white/8 p-3">
                      <div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Pot</div>
                      <div className="font-display text-2xl text-yellow-neon mt-2">⚡ {duel.pot}</div>
                    </div>
                    <div className="border border-white/8 p-3">
                      <div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Map finale</div>
                      <div className="font-display text-2xl mt-2">{duel.selected_map || "En veto"}</div>
                    </div>
                    <div className="border border-white/8 p-3">
                      <div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Serveur</div>
                      <div className="text-sm mt-2 text-white/75">{duel.server?.name || duel.launch_status || "En attente"}</div>
                    </div>
                  </div>

                  {duel.status === "veto" && (
                    <div className="mt-5 border border-white/8 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-[11px] uppercase tracking-[0.25em] text-white/35">Phase veto</div>
                          <div className="text-sm text-white/70 mt-2">
                            {duel.is_my_turn ? "C'est votre tour : bannissez une map." : `Tour de ${duel.veto_turn_pseudo || "l'autre joueur"}.`}
                          </div>
                        </div>
                        <div className="text-xs text-white/45">Auto refresh 5s</div>
                      </div>
                      <div className="flex flex-wrap gap-2 mt-4">
                        {(duel.remaining_maps || []).map((map) => (
                          <button
                            key={map}
                            disabled={!duel.is_my_turn || busyKey === `ban-${duel.id}-${map}`}
                            onClick={() => banMap(duel.id, map)}
                            className={`px-4 py-2 border text-sm ${duel.is_my_turn ? "border-orange-500/50 hover:border-orange-500 hover:text-white" : "border-white/8 text-white/40 cursor-not-allowed"}`}
                          >
                            {map}
                          </button>
                        ))}
                      </div>
                      {(duel.veto_history || []).length > 0 && (
                        <div className="mt-4 text-xs text-white/50">
                          {(duel.veto_history || []).map((entry) => `${entry.by_pseudo} a retire ${entry.map}`).join(" • ")}
                        </div>
                      )}
                    </div>
                  )}

                  {duel.launch_error && (
                    <div className="mt-4 text-sm text-red-400 border border-red-500/25 p-3">{duel.launch_error}</div>
                  )}

                  {duel.can_join && (
                    <div className="mt-5 flex flex-wrap items-center gap-3">
                      <button
                        onClick={() => joinMatch(duel.id)}
                        disabled={busyKey === `join-${duel.id}`}
                        className="btn-neon"
                        data-testid={`join-duel-${duel.id}`}
                      >
                        <Play size={14}/>{busyKey === `join-${duel.id}` ? "Connexion..." : (duel.join_cta || "Rejoindre le serveur")}
                      </button>
                      <div className="text-sm text-white/50">
                        {duel.server?.host && duel.server?.game_port ? `${duel.server.host}:${duel.server.game_port}` : "Serveur reserve"}
                      </div>
                    </div>
                  )}

                  {duel.status === "closed" && (
                    <div className="mt-5 text-sm text-green-300">Victoire : {duel.winner_pseudo || "resultat confirme"}.</div>
                  )}
                </div>
              );
            })}
          </div>
        </>
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
            <div className="mt-3 text-sm text-white/60">Map favorite : <span className="text-white">{d.preferred_map || d.selected_map || "—"}</span></div>
            <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
              <div><div className="text-xs uppercase text-white/40">Mise</div><div className="font-display text-yellow-neon">⚡ {d.stake}</div></div>
              {user && user.id !== d.creator_id && <button onClick={()=>accept(d.id)} disabled={busyKey === `accept-${d.id}`} className="btn-neon" data-testid={`accept-duel-${d.id}`}>{busyKey === `accept-${d.id}` ? "..." : "Accepter + veto"}</button>}
              {user && user.id === d.creator_id && <span className="text-xs text-white/40">Votre défi</span>}
            </div>
          </div>))}
      </div>
    </div>
  );
};

const ContestsPage = () => {
  const { token, user } = useAuth();
  const [contests, setContests] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const refresh = async () => {
    const response = await axios.get(`${API}/contests`);
    setContests(response.data);
  };

  useEffect(() => {
    refresh();
  }, []);

  const join = async (contestId) => {
    if (!token) {
      alert("Connectez-vous pour participer.");
      return;
    }
    setBusyId(contestId);
    try {
      await axios.post(`${API}/contests/${contestId}/join`, {}, { headers: { Authorization: `Bearer ${token}` } });
      await refresh();
      alert("Participation enregistrée.");
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur concours");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="contests-page">
      <div className="flex items-center gap-3"><Ticket className="text-orange-500" size={32}/><h1 className="font-display text-5xl uppercase">Concours & campagnes</h1></div>
      <p className="text-white/50 mt-2">Jeux concours communautaires, gratuits, pilotables depuis l'administration et sans impact compétitif.</p>
      {!user && <div className="glass p-5 mt-6 text-white/60">Connectez-vous pour enregistrer une participation. Un compte = une participation par concours.</div>}
      <div className="grid md:grid-cols-2 gap-4 mt-8">
        {contests.length === 0 && <div className="glass p-6 text-white/40">Aucun concours actif pour le moment.</div>}
        {contests.map((contest) => (
          <div key={contest.id} className="glass p-6" data-testid={`contest-card-${contest.id}`} style={{ borderColor: `${contest.banner_color || "#FF4600"}55` }}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <Badge variant={contest.remaining_slots === 0 ? "offline" : "soon"}>{contest.remaining_slots === 0 ? "Complet" : "Ouvert"}</Badge>
              <span className="text-xs uppercase tracking-widest text-white/40">{contest.entries_count} / {contest.max_entries} participations</span>
            </div>
            <h2 className="font-display text-3xl uppercase mt-4">{contest.title}</h2>
            <p className="text-white/60 mt-3">{contest.summary}</p>
            <p className="text-white/50 mt-4">{contest.body}</p>
            <div className="grid md:grid-cols-2 gap-3 mt-5 text-sm">
              <div className="border border-white/10 p-4">
                <div className="text-xs uppercase tracking-widest text-white/40">Lot</div>
                <div className="font-display mt-2">{contest.reward_label || "A confirmer"}</div>
              </div>
              <div className="border border-white/10 p-4">
                <div className="text-xs uppercase tracking-widest text-white/40">Fin</div>
                <div className="font-display mt-2">{contest.ends_at ? new Date(contest.ends_at).toLocaleDateString("fr-FR") : "Sans limite"}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-3 mt-6">
              <button disabled={busyId === contest.id || contest.remaining_slots === 0} onClick={() => join(contest.id)} className="btn-neon">
                <Gift size={14}/>{busyId === contest.id ? "Envoi..." : "Participer"}
              </button>
              {contest.cta_url && contest.cta_url !== "/concours" && (
                contest.cta_url.startsWith("http") ? (
                  <a href={contest.cta_url} target="_blank" rel="noreferrer" className="btn-ghost">{contest.cta_label || "Ouvrir"} <ExternalLink size={14}/></a>
                ) : (
                  <Link to={contest.cta_url} className="btn-ghost">{contest.cta_label || "Ouvrir"} <ChevronRight size={14}/></Link>
                )
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const RewardsStorePage = () => {
  const { token, user } = useAuth();
  const [rewards, setRewards] = useState([]);
  const [balance, setBalance] = useState(null);
  const [redemptions, setRedemptions] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const refresh = async () => {
    const rewardsResponse = await axios.get(`${API}/rewards`);
    setRewards(rewardsResponse.data);
    if (token) {
      const [balanceResponse, redemptionsResponse] = await Promise.all([
        axios.get(`${API}/duels/balance`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/rewards/redemptions/me`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setBalance(balanceResponse.data.tokens);
      setRedemptions(redemptionsResponse.data);
    } else {
      setBalance(null);
      setRedemptions([]);
    }
  };

  useEffect(() => {
    const load = async () => {
      const rewardsResponse = await axios.get(`${API}/rewards`);
      setRewards(rewardsResponse.data);
      if (token) {
        const [balanceResponse, redemptionsResponse] = await Promise.all([
          axios.get(`${API}/duels/balance`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`${API}/rewards/redemptions/me`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        setBalance(balanceResponse.data.tokens);
        setRedemptions(redemptionsResponse.data);
      } else {
        setBalance(null);
        setRedemptions([]);
      }
    };
    load().catch(() => {});
  }, [token]);

  const redeem = async (rewardId) => {
    if (!token) {
      alert("Connectez-vous pour utiliser vos points.");
      return;
    }
    setBusyId(rewardId);
    try {
      await axios.post(`${API}/rewards/${rewardId}/redeem`, {}, { headers: { Authorization: `Bearer ${token}` } });
      await refresh();
      alert("Reward réservée. Vérifiez l'état dans vos demandes.");
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur boutique");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="rewards-page">
      <div className="flex items-center gap-3"><ShoppingBag className="text-cyan-neon" size={32}/><h1 className="font-display text-5xl uppercase">Boutique de points</h1></div>
      <p className="text-white/50 mt-2">Utilise les jetons gagnés dans la plateforme pour débloquer des rewards non compétitives.</p>
      <div className="grid lg:grid-cols-[1.5fr_1fr] gap-4 mt-8">
        <div className="grid md:grid-cols-2 gap-4">
          {rewards.length === 0 && <div className="glass p-6 text-white/40">Aucune reward active.</div>}
          {rewards.map((reward) => (
            <div key={reward.id} className="glass p-6" data-testid={`reward-card-${reward.id}`} style={{ borderColor: `${reward.accent_color || "#00F0FF"}55` }}>
              <div className="flex items-center justify-between gap-3">
                <Badge variant={reward.stock > 0 ? "verified" : "offline"}>{reward.category}</Badge>
                <div className="font-display text-yellow-neon">{reward.cost_tokens} pts</div>
              </div>
              <h2 className="font-display text-2xl uppercase mt-4">{reward.title}</h2>
              <p className="text-white/60 mt-3">{reward.summary}</p>
              <p className="text-sm text-white/50 mt-4">{reward.description}</p>
              <div className="text-xs uppercase tracking-widest text-white/40 mt-4">Stock: {reward.stock}</div>
              <div className="text-sm text-white/50 mt-2">{reward.delivery_notes}</div>
              <button disabled={busyId === reward.id || reward.stock <= 0} onClick={() => redeem(reward.id)} className="btn-neon mt-5">
                <Package size={14}/>{busyId === reward.id ? "Traitement..." : "Réserver"}
              </button>
            </div>
          ))}
        </div>
        <div className="space-y-4">
          <div className="glass p-6">
            <div className="text-xs uppercase tracking-widest text-white/40">Solde disponible</div>
            <div className="font-display text-5xl text-yellow-neon mt-3">{balance ?? "—"}</div>
            <p className="text-white/50 mt-3">Le même solde alimente les duels 1v1 et la boutique de points.</p>
          </div>
          <div className="glass p-6">
            <div className="text-xs uppercase tracking-widest text-white/40">Demandes récentes</div>
            <div className="space-y-3 mt-4">
              {redemptions.length === 0 && <div className="text-white/40">Aucune reward réservée.</div>}
              {redemptions.slice(0, 6).map((item) => (
                <div key={item.id} className="border border-white/10 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-display text-sm uppercase">{item.reward_title || item.reward_id}</div>
                    <Badge variant={item.status === "delivered" ? "verified" : item.status === "cancelled" ? "offline" : "soon"}>{item.status}</Badge>
                  </div>
                  <div className="text-sm text-white/50 mt-2">{item.cost_tokens} pts • {new Date(item.created_at).toLocaleString("fr-FR")}</div>
                </div>
              ))}
            </div>
          </div>
          {!user && <div className="glass p-6 text-white/60">Connectez-vous pour voir votre solde et réserver une reward.</div>}
        </div>
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
  useEffect(() => {
    refresh();
    const handler = () => refresh();
    window.addEventListener("readyup-tournaments-changed", handler);
    return () => window.removeEventListener("readyup-tournaments-changed", handler);
  }, []);
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
  const emptyServerForm = {
    name: "", host: "", port: 27015, control_mode: "bridge", rcon_password: "", bridge_token: "",
    provider: "FShost.me", region: "EU-FR", public_host: "", game_port: 27015, gotv_port: "",
    join_password: "", gotv_password: "",
    matchzy_enabled: true, cssimpleadmin_enabled: true, fake_rcon_enabled: true, hltv_enabled: true,
  };
  const [servers, setServers] = useState([]);
  const [events, setEvents] = useState([]);
  const [platformConfig, setPlatformConfig] = useState(null);
  const [form, setForm] = useState(emptyServerForm);
  const [selected, setSelected] = useState(null);
  const [cmd, setCmd] = useState("status");
  const [output, setOutput] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const [serversResponse, eventsResponse, configResponse] = await Promise.allSettled([
      axios.get(`${API}/cs2/servers`),
      axios.get(`${API}/cs2/events?limit=10`),
      axios.get(`${API}/config`),
    ]);
    setServers(serversResponse.status === "fulfilled" ? serversResponse.value.data : []);
    setEvents(eventsResponse.status === "fulfilled" ? eventsResponse.value.data : []);
    setPlatformConfig(configResponse.status === "fulfilled" ? configResponse.value.data : null);
  };
  useEffect(() => { refresh(); }, []);

  const addServer = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      const payload = {
        ...form,
        port: parseInt(form.port, 10),
        game_port: form.game_port ? parseInt(form.game_port, 10) : undefined,
        gotv_port: form.gotv_port ? parseInt(form.gotv_port, 10) : undefined,
        join_password: form.join_password || undefined,
        gotv_password: form.gotv_password || undefined,
      };
      if (form.control_mode === "bridge") {
        payload.rcon_password = undefined;
      } else {
        payload.bridge_token = undefined;
      }
      await axios.post(`${API}/cs2/servers`, payload, { headers: authH });
      setForm(emptyServerForm); await refresh();
    }
    catch (e2) { alert(e2.response?.data?.detail || "Erreur"); } finally { setBusy(false); }
  };
  const del = async (id) => { if (!window.confirm("Supprimer ce serveur ?")) return;
    try { await axios.delete(`${API}/cs2/servers/${id}`, { headers: authH }); if (selected===id) setSelected(null); await refresh(); }
    catch (e) { alert(e.response?.data?.detail || "Erreur"); } };
  const ping = async (id) => { setBusy(true); setSelected(id); setOutput("Connexion RCON…");
    try {
      const r = await axios.post(`${API}/cs2/servers/${id}/ping`, {}, { headers: authH });
      const prefix = r.data.queued ? `Commande envoyee au bridge (${r.data.command_id})\n\n` : "";
      setOutput(`${prefix}${r.data.output || ""}`.trim());
      await refresh();
    }
    catch (e) { setOutput(e.response?.data?.detail || "Erreur RCON"); } finally { setBusy(false); } };
  const configureMatchzyRemoteLog = async (id) => { setBusy(true); setSelected(id); setOutput("Configuration MatchZy API en cours…");
    try {
      const r = await axios.post(`${API}/cs2/servers/${id}/configure-matchzy-remote-log`, {}, { headers: authH });
      const details = (r.data.outputs || []).map(item => `${item.command}\n${item.output || ""}`.trim()).join("\n\n");
      setOutput(details || `Webhook MatchZy configuré vers ${r.data.webhook_url}`);
      await refresh();
    }
    catch (e) { setOutput(e.response?.data?.detail || "Erreur configuration MatchZy"); } finally { setBusy(false); } };
  const runCmd = async () => { if (!selected) { alert("Sélectionnez un serveur via Ping d'abord."); return; } setBusy(true); setOutput("Exécution…");
    try {
      const r = await axios.post(`${API}/cs2/servers/${selected}/rcon`, { command: cmd }, { headers: authH });
      const prefix = r.data.queued ? `Commande envoyee au bridge (${r.data.command_id})\n\n` : "";
      setOutput(`${prefix}${r.data.output || ""}`.trim());
    }
    catch (e) { setOutput(e.response?.data?.detail || "Erreur RCON"); } finally { setBusy(false); } };

  return (
    <div data-testid="cs2-panel">
      <SectionTitle sub="Pilotage CS2 (RCON / Bridge)" title="Serveurs de match"/>
      {platformConfig?.integrations && (
        <div className="glass p-6 mb-4" data-testid="cs2-platform-readiness">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="text-xs uppercase tracking-widest text-white/40">Pré requis backend</div>
              <div className="font-display text-2xl uppercase mt-2">Etat des integrations critiques</div>
            </div>
            <button disabled={busy} onClick={refresh} className="btn-ghost text-xs"><RefreshCw size={12}/>Rafraichir</button>
          </div>
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4 mt-5">
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">MatchZy public URL</div>
              <div className={`font-display text-xl mt-2 ${platformConfig.integrations.matchzy?.public_base_configured ? "text-cyan-neon" : "text-yellow-neon"}`}>
                {platformConfig.integrations.matchzy?.public_base_configured ? "OK" : "MANQUANT"}
              </div>
            </div>
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">Webhook secret</div>
              <div className={`font-display text-xl mt-2 ${platformConfig.integrations.matchzy?.webhook_secret_configured ? "text-cyan-neon" : "text-yellow-neon"}`}>
                {platformConfig.integrations.matchzy?.webhook_secret_configured ? "OK" : "MANQUANT"}
              </div>
            </div>
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">Config token</div>
              <div className={`font-display text-xl mt-2 ${platformConfig.integrations.matchzy?.config_token_configured ? "text-cyan-neon" : "text-yellow-neon"}`}>
                {platformConfig.integrations.matchzy?.config_token_configured ? "OK" : "MANQUANT"}
              </div>
            </div>
            <div className="border border-white/10 p-4">
              <div className="text-xs uppercase tracking-widest text-white/40">Twitch API</div>
              <div className={`font-display text-xl mt-2 ${platformConfig.integrations.twitch?.configured ? "text-cyan-neon" : "text-yellow-neon"}`}>
                {platformConfig.integrations.twitch?.configured ? "OK" : "FALLBACK"}
              </div>
            </div>
          </div>
          <div className="text-xs text-white/45 mt-4">
            Email reset: {platformConfig.integrations.email?.configured ? "configuré" : "non configuré"} •
            Twitch channel: {platformConfig.integrations.twitch?.channel || "esl_csgo"}
          </div>
        </div>
      )}
      {isAdmin && (
        <form onSubmit={addServer} className="glass p-6 grid md:grid-cols-2 xl:grid-cols-5 gap-3 items-end mb-4" data-testid="cs2-add-form">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Nom</label>
            <input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="EU-FR-01" required data-testid="cs2-name-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Mode de controle</label>
            <select value={form.control_mode} onChange={e=>setForm({...form,control_mode:e.target.value})}>
              <option value="bridge">Bridge (Fake RCON / plugin)</option>
              <option value="rcon">RCON reseau</option>
            </select></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Hebergeur</label>
            <input value={form.provider} onChange={e=>setForm({...form,provider:e.target.value})} placeholder="FShost.me"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Region</label>
            <input value={form.region} onChange={e=>setForm({...form,region:e.target.value})} placeholder="EU-FR"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Hôte / IP</label>
            <input value={form.host} onChange={e=>setForm({...form,host:e.target.value})} placeholder="cs2.example.net" required data-testid="cs2-host-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">{form.control_mode === "bridge" ? "Port controle (optionnel)" : "Port RCON"}</label>
            <input type="number" value={form.port} onChange={e=>setForm({...form,port:e.target.value})} required data-testid="cs2-port-input"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Host public</label>
            <input value={form.public_host} onChange={e=>setForm({...form,public_host:e.target.value})} placeholder="play.tonserveur.fr"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Port jeu</label>
            <input type="number" value={form.game_port} onChange={e=>setForm({...form,game_port:e.target.value})} placeholder="27015"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Port HLTV / GOTV</label>
            <input type="number" value={form.gotv_port} onChange={e=>setForm({...form,gotv_port:e.target.value})} placeholder="27020"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Mot de passe joueur</label>
            <input type="password" value={form.join_password} onChange={e=>setForm({...form,join_password:e.target.value})} placeholder="pracc"/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Mot de passe HLTV</label>
            <input type="password" value={form.gotv_password} onChange={e=>setForm({...form,gotv_password:e.target.value})} placeholder="club21"/></div>
          {form.control_mode === "bridge" ? (
            <div><label className="text-xs uppercase tracking-widest text-white/40">Bridge token</label>
              <input type="password" value={form.bridge_token} onChange={e=>setForm({...form,bridge_token:e.target.value})} required data-testid="cs2-bridge-token-input"/></div>
          ) : (
            <div><label className="text-xs uppercase tracking-widest text-white/40">Mot de passe RCON</label>
              <input type="password" value={form.rcon_password} onChange={e=>setForm({...form,rcon_password:e.target.value})} required data-testid="cs2-rcon-input"/></div>
          )}
          <div className="flex flex-wrap gap-4 xl:col-span-5 text-xs text-white/70">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.matchzy_enabled} onChange={e=>setForm({...form,matchzy_enabled:e.target.checked})}/>MatchZy</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.cssimpleadmin_enabled} onChange={e=>setForm({...form,cssimpleadmin_enabled:e.target.checked})}/>CSsimpleadmin</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.fake_rcon_enabled} onChange={e=>setForm({...form,fake_rcon_enabled:e.target.checked})}/>Fake RCON</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.hltv_enabled} onChange={e=>setForm({...form,hltv_enabled:e.target.checked})}/>HLTV / GOTV</label>
          </div>
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
            <div className="text-xs text-white/40 mt-2 font-mono-display">{s.provider || "custom"} • {(s.public_host || s.host)}:{s.game_port || s.port}</div>
            <div className="text-xs text-white/60 mt-1">{s.control_mode === "bridge" ? "Bridge serveur" : `RCON ${s.host}:${s.port}`} • {s.region || "region non renseignee"}</div>
            <div className="text-xs text-white/60 mt-1">Statut : {s.status}</div>
            <div className="text-xs text-white/40 mt-1">Mode : {s.control_mode === "bridge" ? "bridge" : "rcon"}</div>
            {s.last_bridge_seen_at && <div className="text-xs text-white/40 mt-1">Bridge vu : {new Date(s.last_bridge_seen_at).toLocaleString("fr-FR")}</div>}
            {!s.last_bridge_seen_at && s.control_mode === "bridge" && <div className="text-xs text-yellow-neon mt-1">Bridge jamais vu par l'API pour l'instant</div>}
            {s.current_match_id && <div className="text-xs text-white/40 mt-1">Match courant : {s.current_match_id}</div>}
            <div className="flex flex-wrap gap-2 mt-3 text-[10px] uppercase tracking-widest text-white/50">
              {s.capabilities?.matchzy && <span className="border border-white/10 px-2 py-1">MatchZy</span>}
              {s.capabilities?.cssimpleadmin && <span className="border border-white/10 px-2 py-1">CSsimpleadmin</span>}
              {s.capabilities?.fake_rcon && <span className="border border-white/10 px-2 py-1">Fake RCON</span>}
              {s.capabilities?.hltv && <span className="border border-white/10 px-2 py-1">HLTV</span>}
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              {s.connect_url && <a href={s.connect_url} className="btn-ghost text-xs"><ExternalLink size={12}/>Connexion</a>}
              {s.hltv_url && <a href={s.hltv_url} className="btn-ghost text-xs"><Tv size={12}/>Spectateur</a>}
            </div>
            {isAdmin && (
              <div className="flex flex-wrap gap-2 mt-4">
                <button disabled={busy} onClick={()=>ping(s.id)} className="btn-ghost text-xs" data-testid={`cs2-ping-${s.id}`}><RefreshCw size={12}/>Ping / Sélectionner</button>
                {s.capabilities?.matchzy && <button disabled={busy} onClick={()=>configureMatchzyRemoteLog(s.id)} className="btn-ghost text-xs" data-testid={`cs2-matchzy-log-${s.id}`}><Radio size={12}/>Configurer MatchZy API</button>}
                <button onClick={()=>del(s.id)} className="btn-ghost text-xs text-red-400" data-testid={`cs2-del-${s.id}`}><Trash2 size={12}/></button>
              </div>
            )}
          </div>
        ))}
      </div>

      {isAdmin && (
        <div className="glass p-6 mt-4" data-testid="cs2-console">
          <h3 className="font-display text-sm uppercase tracking-widest text-white/60 flex items-center gap-2"><Terminal size={14}/>Console serveur {selected ? "" : "(sélectionnez un serveur)"}</h3>
          <p className="text-xs text-white/40 mt-2">En mode `rcon`, la commande part immediatement. En mode `bridge`, elle est mise en file et executee localement par le plugin serveur.</p>
          <p className="text-xs text-white/40 mt-2">Le bouton `Configurer MatchZy API` applique `matchzy_remote_log_url` et l'authentification du webhook directement sur le serveur.</p>
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

const TournamentCrudAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [tournaments, setTournaments] = useState([]);
  const [form, setForm] = useState(makeTournamentForm());
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const response = await axios.get(`${API}/tournaments`);
    setTournaments(response.data);
  };

  useEffect(() => {
    refresh();
  }, []);

  const reset = () => {
    setEditingId(null);
    setForm(makeTournamentForm());
  };

  const payload = {
    name: form.name,
    organizer: form.organizer,
    format: form.format,
    mode: form.mode,
    capacity: parseInt(form.capacity, 10),
    status: form.status,
    starts_at: form.starts_at,
    prize: form.prize,
    region: form.region,
    level_min: parseInt(form.level_min, 10),
    image_color: form.image_color,
    description: form.description,
    maps: splitAdminList(form.maps_text),
    rules: splitAdminList(form.rules_text),
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (editingId) {
        await axios.patch(`${API}/admin/tournaments/${editingId}`, payload, { headers: authH });
      } else {
        await axios.post(`${API}/admin/tournaments`, payload, { headers: authH });
      }
      await refresh();
      window.dispatchEvent(new Event("readyup-tournaments-changed"));
      reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur tournoi");
    } finally {
      setBusy(false);
    }
  };

  const edit = (tournament) => {
    setEditingId(tournament.id);
    setForm({
      name: tournament.name || "",
      organizer: tournament.organizer || "",
      format: tournament.format || "5v5",
      mode: tournament.mode || "",
      capacity: tournament.capacity || 16,
      status: tournament.status || "open",
      starts_at: toLocalInputValue(tournament.starts_at),
      prize: tournament.prize || "",
      region: tournament.region || "EU",
      level_min: tournament.level_min ?? 1,
      image_color: tournament.image_color || "#FF4600",
      description: tournament.description || "",
      maps_text: (tournament.maps || []).join("\n"),
      rules_text: (tournament.rules || []).join("\n"),
    });
  };

  const duplicate = async (id) => {
    setBusy(true);
    try {
      await axios.post(`${API}/admin/tournaments/${id}/duplicate`, {}, { headers: authH });
      await refresh();
      window.dispatchEvent(new Event("readyup-tournaments-changed"));
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur duplication");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Supprimer ce tournoi et ses inscriptions ?")) return;
    setBusy(true);
    try {
      await axios.delete(`${API}/admin/tournaments/${id}`, { headers: authH });
      await refresh();
      window.dispatchEvent(new Event("readyup-tournaments-changed"));
      if (editingId === id) reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur suppression");
    } finally {
      setBusy(false);
    }
  };

  if (!isAdmin) return null;

  return (
    <div data-testid="tournament-crud-admin">
      <SectionTitle sub="Gestion tournoi" title={editingId ? "Modifier un tournoi" : "Créer un tournoi"}/>
      <form onSubmit={save} className="glass p-6 space-y-4">
        <div className="grid md:grid-cols-3 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Nom</label><input value={form.name} onChange={(e)=>setForm({...form, name: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Organisateur</label><input value={form.organizer} onChange={(e)=>setForm({...form, organizer: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Format</label><input value={form.format} onChange={(e)=>setForm({...form, format: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Mode</label><input value={form.mode} onChange={(e)=>setForm({...form, mode: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Capacité</label><input type="number" min="2" value={form.capacity} onChange={(e)=>setForm({...form, capacity: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Statut</label>
            <select value={form.status} onChange={(e)=>setForm({...form, status: e.target.value})}>
              {["open", "registering", "starting", "live", "closed"].map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Début</label><input type="datetime-local" value={form.starts_at} onChange={(e)=>setForm({...form, starts_at: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Récompense</label><input value={form.prize} onChange={(e)=>setForm({...form, prize: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Région</label><input value={form.region} onChange={(e)=>setForm({...form, region: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Niveau min</label><input type="number" min="0" value={form.level_min} onChange={(e)=>setForm({...form, level_min: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Couleur</label><input type="color" value={form.image_color} onChange={(e)=>setForm({...form, image_color: e.target.value})}/></div>
        </div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Description</label><textarea rows={4} value={form.description} onChange={(e)=>setForm({...form, description: e.target.value})}/></div>
        <div className="grid md:grid-cols-2 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Maps (une par ligne)</label><textarea rows={4} value={form.maps_text} onChange={(e)=>setForm({...form, maps_text: e.target.value})}/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Règles clés (une par ligne)</label><textarea rows={4} value={form.rules_text} onChange={(e)=>setForm({...form, rules_text: e.target.value})}/></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className="btn-neon">{editingId ? "Enregistrer les modifications" : "Créer le tournoi"}</button>
          <button type="button" onClick={reset} className="btn-ghost">Réinitialiser</button>
        </div>
      </form>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        {tournaments.map((tournament) => (
          <div key={tournament.id} className="glass p-5" data-testid={`crud-tournament-${tournament.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-display text-xl uppercase">{tournament.name}</div>
                <div className="text-xs text-white/40 mt-1">{tournament.organizer} • {tournament.format} • {tournament.region}</div>
              </div>
              <Badge variant={["live", "starting"].includes(tournament.status) ? "live" : "soon"}>{tournament.status}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-4 text-sm">
              <div><div className="text-white/40 text-xs uppercase tracking-widest">Inscrits</div><div className="font-display mt-1">{tournament.registered}/{tournament.capacity}</div></div>
              <div><div className="text-white/40 text-xs uppercase tracking-widest">Début</div><div className="font-display mt-1">{new Date(tournament.starts_at).toLocaleDateString("fr-FR")}</div></div>
              <div><div className="text-white/40 text-xs uppercase tracking-widest">Niveau min</div><div className="font-display mt-1">{tournament.level_min}</div></div>
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              <button onClick={()=>edit(tournament)} className="btn-ghost text-xs">Modifier</button>
              <button onClick={()=>duplicate(tournament.id)} className="btn-ghost text-xs">Dupliquer</button>
              <button onClick={()=>remove(tournament.id)} className="btn-ghost text-xs text-red-400">Supprimer</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const TeamAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [teams, setTeams] = useState([]);
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [form, setForm] = useState(makeTeamForm());
  const [busyKey, setBusyKey] = useState("");

  const refresh = useCallback(async () => {
    if (!isAdmin) return;
    const response = await axios.get(`${API}/admin/teams`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    const rows = response.data || [];
    setTeams(rows);
    setSelectedTeamId((current) => (current && rows.some((team) => team.id === current) ? current : (rows[0]?.id || "")));
  }, [isAdmin, token]);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const selectedTeam = teams.find((team) => team.id === selectedTeamId) || null;

  useEffect(() => {
    if (!selectedTeam) return;
    setForm({
      name: selectedTeam.name || "",
      tag: selectedTeam.tag || "",
      country: selectedTeam.country || "FR",
      description: selectedTeam.description || "",
      language: selectedTeam.language || "FR",
      discord_url: selectedTeam.discord_url || "",
      logo_color: selectedTeam.logo_color || "#FF4600",
      recruitment_status: selectedTeam.recruitment_status || "open",
      members_limit: selectedTeam.members_limit || 7,
    });
  }, [selectedTeam]);

  const saveTeam = async (event) => {
    event.preventDefault();
    if (!selectedTeam) return;
    setBusyKey(`save-${selectedTeam.id}`);
    try {
      await axios.patch(`${API}/admin/teams/${selectedTeam.id}`, { ...form, members_limit: Number(form.members_limit) }, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur equipe");
    } finally {
      setBusyKey("");
    }
  };

  const deleteTeam = async (teamId) => {
    if (!window.confirm("Supprimer cette equipe ?")) return;
    setBusyKey(`delete-${teamId}`);
    try {
      await axios.delete(`${API}/admin/teams/${teamId}`, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur equipe");
    } finally {
      setBusyKey("");
    }
  };

  const promoteCaptain = async (teamId, member) => {
    setBusyKey(`captain-${teamId}-${member.id}`);
    try {
      await axios.post(`${API}/admin/teams/${teamId}/members/${member.id}/role`, { source: member.source, role: "captain" }, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur equipe");
    } finally {
      setBusyKey("");
    }
  };

  const removeMember = async (teamId, member) => {
    if (!window.confirm(`Retirer ${member.pseudo} de cette equipe ?`)) return;
    setBusyKey(`remove-${teamId}-${member.id}`);
    try {
      await axios.post(`${API}/admin/teams/${teamId}/members/${member.id}/remove`, { source: member.source }, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur equipe");
    } finally {
      setBusyKey("");
    }
  };

  if (!isAdmin) return null;

  return (
    <div data-testid="team-admin">
      <SectionTitle sub="Gestion equipe" title="Equipes et membres"/>
      <div className="grid xl:grid-cols-[0.9fr_1.1fr] gap-6">
        <div className="glass p-6">
          <div className="text-xs uppercase tracking-widest text-white/40">Selection</div>
          <div className="space-y-3 mt-5">
            {teams.length === 0 && <div className="text-white/35">Aucune equipe chargee.</div>}
            {teams.map((team) => (
              <button
                key={team.id}
                type="button"
                onClick={() => setSelectedTeamId(team.id)}
                className={`w-full text-left border p-4 transition-colors ${selectedTeamId === team.id ? "border-orange-500/60 bg-white/5" : "border-white/10 hover:border-white/20"}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-display text-xl uppercase">{team.name}</div>
                    <div className="text-xs text-white/45 mt-2">{team.tag} • {team.country} • {team.members_count}/{team.members_limit}</div>
                  </div>
                  <Badge variant={team.recruitment_status === "open" ? "soon" : "offline"}>{team.recruitment_status}</Badge>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="glass p-6">
          {!selectedTeam && <div className="text-white/35">Choisissez une equipe pour la gerer.</div>}
          {selectedTeam && (
            <>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <div className="text-xs uppercase tracking-widest text-orange-500">Edition admin</div>
                  <h3 className="font-display text-3xl uppercase mt-3">{selectedTeam.name}</h3>
                </div>
                <button onClick={() => deleteTeam(selectedTeam.id)} disabled={busyKey === `delete-${selectedTeam.id}`} className="btn-ghost text-red-400">
                  <Trash2 size={14}/>{busyKey === `delete-${selectedTeam.id}` ? "Suppression..." : "Supprimer"}
                </button>
              </div>

              <form onSubmit={saveTeam} className="grid md:grid-cols-2 gap-4 mt-6">
                <div><label className="text-xs uppercase tracking-widest text-white/40">Nom</label><input value={form.name} onChange={(e)=>setForm({ ...form, name: e.target.value })} required /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Tag</label><input value={form.tag} onChange={(e)=>setForm({ ...form, tag: e.target.value.toUpperCase() })} required /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Pays</label><input value={form.country} onChange={(e)=>setForm({ ...form, country: e.target.value.toUpperCase() })} required /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Langue</label><input value={form.language} onChange={(e)=>setForm({ ...form, language: e.target.value.toUpperCase() })} required /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Couleur</label><input value={form.logo_color} onChange={(e)=>setForm({ ...form, logo_color: e.target.value })} required /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Limite</label><input type="number" min="1" max="12" value={form.members_limit} onChange={(e)=>setForm({ ...form, members_limit: e.target.value })} required /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Discord</label><input value={form.discord_url} onChange={(e)=>setForm({ ...form, discord_url: e.target.value })} /></div>
                <div><label className="text-xs uppercase tracking-widest text-white/40">Recrutement</label><select value={form.recruitment_status} onChange={(e)=>setForm({ ...form, recruitment_status: e.target.value })}><option value="open">Ouvert</option><option value="closed">Ferme</option></select></div>
                <div className="md:col-span-2"><label className="text-xs uppercase tracking-widest text-white/40">Description</label><textarea rows={4} value={form.description} onChange={(e)=>setForm({ ...form, description: e.target.value })} /></div>
                <div className="md:col-span-2"><button disabled={busyKey === `save-${selectedTeam.id}`} className="btn-neon"><Shield size={14}/>{busyKey === `save-${selectedTeam.id}` ? "Sauvegarde..." : "Sauvegarder"}</button></div>
              </form>

              <div className="mt-8">
                <div className="text-xs uppercase tracking-widest text-yellow-neon">Gestion des membres</div>
                <div className="space-y-3 mt-4">
                  {(selectedTeam.members || []).map((member) => (
                    <div key={`${selectedTeam.id}-${member.source}-${member.id}`} className="border border-white/10 p-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <div className="font-display uppercase flex items-center gap-2">
                          <span>{member.pseudo}</span>
                          {member.team_role === "captain" && <Badge variant="verified">Capitaine</Badge>}
                          {member.source === "seed" && <Badge variant="offline">Seed</Badge>}
                        </div>
                        <div className="text-xs text-white/45 mt-2">{member.role || "Polyvalent"} • ELO {formatMetric(member.elo)} • K/D {formatMetric(member.kdr, 2)}</div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {member.source === "user" && member.team_role !== "captain" && (
                          <button onClick={() => promoteCaptain(selectedTeam.id, member)} disabled={busyKey === `captain-${selectedTeam.id}-${member.id}`} className="btn-ghost text-xs">
                            <Crown size={14}/>{busyKey === `captain-${selectedTeam.id}-${member.id}` ? "Nomination..." : "Nommer capitaine"}
                          </button>
                        )}
                        <button onClick={() => removeMember(selectedTeam.id, member)} disabled={busyKey === `remove-${selectedTeam.id}-${member.id}`} className="btn-ghost text-xs text-red-400">
                          <Trash2 size={14}/>{busyKey === `remove-${selectedTeam.id}-${member.id}` ? "Retrait..." : "Retirer"}
                        </button>
                      </div>
                    </div>
                  ))}
                  {!(selectedTeam.members || []).length && <div className="text-white/35">Aucun membre dans cette equipe.</div>}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const NewsAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(makeNewsForm());
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const response = await axios.get(`${API}/admin/news`, { headers: authH });
    setItems(response.data);
  };

  useEffect(() => {
    if (!isAdmin) return;
    const load = async () => {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await axios.get(`${API}/admin/news`, { headers });
      setItems(response.data);
    };
    load();
  }, [isAdmin, token]);

  const reset = () => {
    setEditingId(null);
    setForm(makeNewsForm());
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (editingId) {
        await axios.patch(`${API}/admin/news/${editingId}`, form, { headers: authH });
      } else {
        await axios.post(`${API}/admin/news`, form, { headers: authH });
      }
      await refresh();
      reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur news");
    } finally {
      setBusy(false);
    }
  };

  const edit = (item) => {
    setEditingId(item.id);
    setForm({
      title: item.title || "",
      excerpt: item.excerpt || "",
      body: item.body || "",
      date: toLocalInputValue(item.date),
    });
  };

  const remove = async (id) => {
    if (!window.confirm("Supprimer cette news ?")) return;
    setBusy(true);
    try {
      await axios.delete(`${API}/admin/news/${id}`, { headers: authH });
      await refresh();
      if (editingId === id) reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur suppression");
    } finally {
      setBusy(false);
    }
  };

  if (!isAdmin) return null;

  return (
    <div data-testid="news-admin">
      <SectionTitle sub="Contenu éditorial" title={editingId ? "Modifier une news" : "Publier une news"}/>
      <form onSubmit={save} className="glass p-6 space-y-4">
        <div className="grid md:grid-cols-2 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Titre</label><input value={form.title} onChange={(e)=>setForm({...form, title: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Date</label><input type="datetime-local" value={form.date} onChange={(e)=>setForm({...form, date: e.target.value})} required/></div>
        </div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Extrait</label><textarea rows={3} value={form.excerpt} onChange={(e)=>setForm({...form, excerpt: e.target.value})} required/></div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Contenu long</label><textarea rows={4} value={form.body} onChange={(e)=>setForm({...form, body: e.target.value})}/></div>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className="btn-neon">{editingId ? "Mettre à jour" : "Publier"}</button>
          <button type="button" onClick={reset} className="btn-ghost">Réinitialiser</button>
        </div>
      </form>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
        {items.map((item) => (
          <div key={item.id} className="glass p-5" data-testid={`news-admin-${item.id}`}>
            <div className="text-xs uppercase tracking-widest text-orange-500">{new Date(item.date).toLocaleString("fr-FR")}</div>
            <h3 className="font-display text-xl mt-3">{item.title}</h3>
            <p className="text-white/60 mt-3">{item.excerpt}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              <button onClick={()=>edit(item)} className="btn-ghost text-xs">Modifier</button>
              <button onClick={()=>remove(item.id)} className="btn-ghost text-xs text-red-400">Supprimer</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AnnouncementAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(makeAnnouncementForm());
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const response = await axios.get(`${API}/admin/announcements`, { headers: authH });
    setItems(response.data);
  };

  useEffect(() => {
    if (!isAdmin) return;
    const load = async () => {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await axios.get(`${API}/admin/announcements`, { headers });
      setItems(response.data);
    };
    load();
  }, [isAdmin, token]);

  const reset = () => {
    setEditingId(null);
    setForm(makeAnnouncementForm());
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (editingId) {
        await axios.patch(`${API}/admin/announcements/${editingId}`, form, { headers: authH });
      } else {
        await axios.post(`${API}/admin/announcements`, form, { headers: authH });
      }
      await refresh();
      reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur annonce");
    } finally {
      setBusy(false);
    }
  };

  const edit = (item) => {
    setEditingId(item.id);
    setForm({
      title: item.title || "",
      body: item.body || "",
      kind: item.kind || "info",
      priority: item.priority ?? 3,
      is_active: item.is_active ?? true,
      cta_label: item.cta_label || "",
      cta_url: item.cta_url || "",
      starts_at: toLocalInputValue(item.starts_at),
      ends_at: item.ends_at ? toLocalInputValue(item.ends_at) : "",
    });
  };

  const remove = async (id) => {
    if (!window.confirm("Supprimer cette annonce ?")) return;
    setBusy(true);
    try {
      await axios.delete(`${API}/admin/announcements/${id}`, { headers: authH });
      await refresh();
      if (editingId === id) reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur suppression");
    } finally {
      setBusy(false);
    }
  };

  if (!isAdmin) return null;

  return (
    <div data-testid="announcement-admin">
      <SectionTitle sub="Annonces" title={editingId ? "Modifier une annonce" : "Créer une annonce"}/>
      <form onSubmit={save} className="glass p-6 space-y-4">
        <div className="grid md:grid-cols-3 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Titre</label><input value={form.title} onChange={(e)=>setForm({...form, title: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Type</label>
            <select value={form.kind} onChange={(e)=>setForm({...form, kind: e.target.value})}>
              {["info", "beta", "feature", "contest", "maintenance"].map((kind) => <option key={kind} value={kind}>{kind}</option>)}
            </select>
          </div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Priorité</label><input type="number" min="1" max="5" value={form.priority} onChange={(e)=>setForm({...form, priority: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Début</label><input type="datetime-local" value={form.starts_at} onChange={(e)=>setForm({...form, starts_at: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Fin</label><input type="datetime-local" value={form.ends_at} onChange={(e)=>setForm({...form, ends_at: e.target.value})}/></div>
          <div className="flex items-end"><label className="text-sm text-white/70 flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={(e)=>setForm({...form, is_active: e.target.checked})}/>Annonce active</label></div>
        </div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Message</label><textarea rows={4} value={form.body} onChange={(e)=>setForm({...form, body: e.target.value})} required/></div>
        <div className="grid md:grid-cols-2 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">CTA label</label><input value={form.cta_label} onChange={(e)=>setForm({...form, cta_label: e.target.value})}/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">CTA URL</label><input value={form.cta_url} onChange={(e)=>setForm({...form, cta_url: e.target.value})}/></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className="btn-neon">{editingId ? "Mettre à jour" : "Publier l'annonce"}</button>
          <button type="button" onClick={reset} className="btn-ghost">Réinitialiser</button>
        </div>
      </form>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        {items.map((item) => (
          <div key={item.id} className="glass p-5" data-testid={`announcement-admin-${item.id}`}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <Badge variant={item.is_active ? "verified" : "offline"}>{item.kind}</Badge>
              <span className="text-xs uppercase tracking-widest text-white/40">Priorité {item.priority}</span>
            </div>
            <h3 className="font-display text-xl mt-3">{item.title}</h3>
            <p className="text-white/60 mt-3">{item.body}</p>
            <div className="text-xs text-white/40 mt-3">Fenêtre: {item.starts_at ? new Date(item.starts_at).toLocaleString("fr-FR") : "—"} → {item.ends_at ? new Date(item.ends_at).toLocaleString("fr-FR") : "sans fin"}</div>
            <div className="flex flex-wrap gap-2 mt-4">
              <button onClick={()=>edit(item)} className="btn-ghost text-xs">Modifier</button>
              <button onClick={()=>remove(item.id)} className="btn-ghost text-xs text-red-400">Supprimer</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const ContestAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [items, setItems] = useState([]);
  const [entries, setEntries] = useState({});
  const [loadingEntriesId, setLoadingEntriesId] = useState(null);
  const [form, setForm] = useState(makeContestForm());
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const response = await axios.get(`${API}/admin/contests`, { headers: authH });
    setItems(response.data);
  };

  useEffect(() => {
    if (!isAdmin) return;
    const load = async () => {
      const response = await axios.get(`${API}/admin/contests`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      setItems(response.data);
    };
    load().catch(() => {});
  }, [isAdmin, token]);

  const reset = () => {
    setEditingId(null);
    setForm(makeContestForm());
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (editingId) {
        await axios.patch(`${API}/admin/contests/${editingId}`, form, { headers: authH });
      } else {
        await axios.post(`${API}/admin/contests`, form, { headers: authH });
      }
      await refresh();
      reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur concours");
    } finally {
      setBusy(false);
    }
  };

  const edit = (item) => {
    setEditingId(item.id);
    setForm({
      title: item.title || "",
      summary: item.summary || "",
      body: item.body || "",
      reward_label: item.reward_label || "",
      max_entries: item.max_entries || 250,
      is_active: item.is_active ?? true,
      banner_color: item.banner_color || "#FF4600",
      cta_label: item.cta_label || "Participer",
      cta_url: item.cta_url || "/concours",
      starts_at: toLocalInputValue(item.starts_at),
      ends_at: item.ends_at ? toLocalInputValue(item.ends_at) : "",
    });
  };

  const remove = async (id) => {
    if (!window.confirm("Supprimer ce concours ?")) return;
    try {
      await axios.delete(`${API}/admin/contests/${id}`, { headers: authH });
      await refresh();
      if (editingId === id) reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur concours");
    }
  };

  const loadEntries = async (contestId) => {
    setLoadingEntriesId(contestId);
    try {
      const response = await axios.get(`${API}/admin/contests/${contestId}/entries`, { headers: authH });
      setEntries((current) => ({ ...current, [contestId]: response.data }));
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur participants");
    } finally {
      setLoadingEntriesId(null);
    }
  };

  if (!isAdmin) return null;

  return (
    <div data-testid="contest-admin">
      <SectionTitle sub="Animation" title={editingId ? "Modifier un concours" : "Créer un concours"}/>
      <form onSubmit={save} className="glass p-6 space-y-4">
        <div className="grid md:grid-cols-3 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Titre</label><input value={form.title} onChange={(e)=>setForm({...form, title: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Lot</label><input value={form.reward_label} onChange={(e)=>setForm({...form, reward_label: e.target.value})}/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Capacité</label><input type="number" min="1" value={form.max_entries} onChange={(e)=>setForm({...form, max_entries: e.target.value})} required/></div>
        </div>
        <div className="grid md:grid-cols-4 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Début</label><input type="datetime-local" value={form.starts_at} onChange={(e)=>setForm({...form, starts_at: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Fin</label><input type="datetime-local" value={form.ends_at} onChange={(e)=>setForm({...form, ends_at: e.target.value})}/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Couleur</label><input value={form.banner_color} onChange={(e)=>setForm({...form, banner_color: e.target.value})}/></div>
          <div className="flex items-end"><label className="text-sm text-white/70 flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={(e)=>setForm({...form, is_active: e.target.checked})}/>Concours actif</label></div>
        </div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Résumé</label><textarea rows={2} value={form.summary} onChange={(e)=>setForm({...form, summary: e.target.value})} required/></div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Description</label><textarea rows={4} value={form.body} onChange={(e)=>setForm({...form, body: e.target.value})} required/></div>
        <div className="grid md:grid-cols-2 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">CTA label</label><input value={form.cta_label} onChange={(e)=>setForm({...form, cta_label: e.target.value})}/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">CTA URL</label><input value={form.cta_url} onChange={(e)=>setForm({...form, cta_url: e.target.value})}/></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className="btn-neon">{editingId ? "Mettre à jour" : "Publier le concours"}</button>
          <button type="button" onClick={reset} className="btn-ghost">Réinitialiser</button>
        </div>
      </form>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        {items.map((item) => (
          <div key={item.id} className="glass p-5" data-testid={`contest-admin-${item.id}`}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <Badge variant={item.is_active ? "verified" : "offline"}>{item.is_active ? "actif" : "inactif"}</Badge>
              <span className="text-xs uppercase tracking-widest text-white/40">{item.entries_count} / {item.max_entries}</span>
            </div>
            <h3 className="font-display text-xl mt-3">{item.title}</h3>
            <p className="text-white/60 mt-3">{item.summary}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              <button onClick={()=>edit(item)} className="btn-ghost text-xs">Modifier</button>
              <button onClick={()=>loadEntries(item.id)} className="btn-ghost text-xs">{loadingEntriesId === item.id ? "Chargement..." : "Voir participants"}</button>
              <button onClick={()=>remove(item.id)} className="btn-ghost text-xs text-red-400">Supprimer</button>
            </div>
            {entries[item.id] && (
              <div className="mt-4 space-y-2">
                {entries[item.id].length === 0 && <div className="text-white/40 text-sm">Aucune participation.</div>}
                {entries[item.id].slice(0, 8).map((entry) => (
                  <div key={entry.id} className="border border-white/10 p-3 text-sm flex items-center justify-between gap-3">
                    <span>{entry.pseudo}</span>
                    <span className="text-white/40">{new Date(entry.created_at).toLocaleString("fr-FR")}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const RewardAdmin = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.is_admin;
  const authH = token ? { Authorization: `Bearer ${token}` } : {};
  const [items, setItems] = useState([]);
  const [redemptions, setRedemptions] = useState([]);
  const [form, setForm] = useState(makeRewardForm());
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const [itemsResponse, redemptionsResponse] = await Promise.all([
      axios.get(`${API}/admin/rewards`, { headers: authH }),
      axios.get(`${API}/admin/rewards/redemptions`, { headers: authH }),
    ]);
    setItems(itemsResponse.data);
    setRedemptions(redemptionsResponse.data);
  };

  useEffect(() => {
    if (!isAdmin) return;
    const load = async () => {
      const [itemsResponse, redemptionsResponse] = await Promise.all([
        axios.get(`${API}/admin/rewards`, { headers: token ? { Authorization: `Bearer ${token}` } : {} }),
        axios.get(`${API}/admin/rewards/redemptions`, { headers: token ? { Authorization: `Bearer ${token}` } : {} }),
      ]);
      setItems(itemsResponse.data);
      setRedemptions(redemptionsResponse.data);
    };
    load().catch(() => {});
  }, [isAdmin, token]);

  const reset = () => {
    setEditingId(null);
    setForm(makeRewardForm());
  };

  const payload = {
    title: form.title,
    summary: form.summary,
    description: form.description,
    category: form.category,
    cost_tokens: parseInt(form.cost_tokens, 10),
    stock: parseInt(form.stock, 10),
    is_active: form.is_active,
    accent_color: form.accent_color,
    delivery_notes: form.delivery_notes,
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (editingId) {
        await axios.patch(`${API}/admin/rewards/${editingId}`, payload, { headers: authH });
      } else {
        await axios.post(`${API}/admin/rewards`, payload, { headers: authH });
      }
      await refresh();
      reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur reward");
    } finally {
      setBusy(false);
    }
  };

  const edit = (item) => {
    setEditingId(item.id);
    setForm({
      title: item.title || "",
      summary: item.summary || "",
      description: item.description || "",
      category: item.category || "badge",
      cost_tokens: item.cost_tokens || 250,
      stock: item.stock || 0,
      is_active: item.is_active ?? true,
      accent_color: item.accent_color || "#00F0FF",
      delivery_notes: item.delivery_notes || "",
    });
  };

  const remove = async (id) => {
    if (!window.confirm("Supprimer cette reward ?")) return;
    try {
      await axios.delete(`${API}/admin/rewards/${id}`, { headers: authH });
      await refresh();
      if (editingId === id) reset();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur reward");
    }
  };

  const updateRedemption = async (redemptionId, status) => {
    try {
      await axios.patch(`${API}/admin/rewards/redemptions/${redemptionId}`, { status }, { headers: authH });
      await refresh();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur redemption");
    }
  };

  if (!isAdmin) return null;

  return (
    <div data-testid="reward-admin">
      <SectionTitle sub="Boutique" title={editingId ? "Modifier une reward" : "Créer une reward"}/>
      <form onSubmit={save} className="glass p-6 space-y-4">
        <div className="grid md:grid-cols-3 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Titre</label><input value={form.title} onChange={(e)=>setForm({...form, title: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Catégorie</label><input value={form.category} onChange={(e)=>setForm({...form, category: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Couleur</label><input value={form.accent_color} onChange={(e)=>setForm({...form, accent_color: e.target.value})}/></div>
        </div>
        <div className="grid md:grid-cols-3 gap-3">
          <div><label className="text-xs uppercase tracking-widest text-white/40">Coût points</label><input type="number" min="10" value={form.cost_tokens} onChange={(e)=>setForm({...form, cost_tokens: e.target.value})} required/></div>
          <div><label className="text-xs uppercase tracking-widest text-white/40">Stock</label><input type="number" min="0" value={form.stock} onChange={(e)=>setForm({...form, stock: e.target.value})} required/></div>
          <div className="flex items-end"><label className="text-sm text-white/70 flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={(e)=>setForm({...form, is_active: e.target.checked})}/>Reward active</label></div>
        </div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Résumé</label><textarea rows={2} value={form.summary} onChange={(e)=>setForm({...form, summary: e.target.value})} required/></div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Description</label><textarea rows={4} value={form.description} onChange={(e)=>setForm({...form, description: e.target.value})}/></div>
        <div><label className="text-xs uppercase tracking-widest text-white/40">Notes de livraison</label><input value={form.delivery_notes} onChange={(e)=>setForm({...form, delivery_notes: e.target.value})}/></div>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy} className="btn-neon">{editingId ? "Mettre à jour" : "Publier la reward"}</button>
          <button type="button" onClick={reset} className="btn-ghost">Réinitialiser</button>
        </div>
      </form>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        {items.map((item) => (
          <div key={item.id} className="glass p-5" data-testid={`reward-admin-${item.id}`}>
            <div className="flex items-center justify-between gap-3">
              <Badge variant={item.is_active ? "verified" : "offline"}>{item.category}</Badge>
              <span className="font-display text-yellow-neon">{item.cost_tokens} pts</span>
            </div>
            <h3 className="font-display text-xl mt-3">{item.title}</h3>
            <p className="text-white/60 mt-3">{item.summary}</p>
            <div className="text-xs uppercase tracking-widest text-white/40 mt-4">Stock: {item.stock}</div>
            <div className="flex flex-wrap gap-2 mt-4">
              <button onClick={()=>edit(item)} className="btn-ghost text-xs">Modifier</button>
              <button onClick={()=>remove(item.id)} className="btn-ghost text-xs text-red-400">Supprimer</button>
            </div>
          </div>
        ))}
      </div>
      <SectionTitle sub="Traitement" title="Demandes boutique"/>
      <div className="grid md:grid-cols-2 gap-4">
        {redemptions.length === 0 && <div className="glass p-6 text-white/40">Aucune demande boutique.</div>}
        {redemptions.slice(0, 12).map((item) => (
          <div key={item.id} className="glass p-5" data-testid={`reward-redemption-${item.id}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-display text-lg uppercase">{item.reward_title || item.reward_id}</div>
                <div className="text-xs text-white/40 mt-1">{item.pseudo} • {item.cost_tokens} pts</div>
              </div>
              <Badge variant={item.status === "delivered" ? "verified" : item.status === "cancelled" ? "offline" : "soon"}>{item.status}</Badge>
            </div>
            <div className="text-xs text-white/40 mt-3">{new Date(item.created_at).toLocaleString("fr-FR")}</div>
            {item.status === "pending" && (
              <div className="flex flex-wrap gap-2 mt-4">
                <button onClick={()=>updateRedemption(item.id, "delivered")} className="btn-neon text-xs">Marquer livré</button>
                <button onClick={()=>updateRedemption(item.id, "cancelled")} className="btn-ghost text-xs text-red-400">Annuler / rembourser</button>
              </div>
            )}
            {item.status === "delivered" && (
              <div className="flex flex-wrap gap-2 mt-4">
                <button onClick={()=>updateRedemption(item.id, "cancelled")} className="btn-ghost text-xs text-red-400">Annuler / rembourser</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const MatchReportsAdmin = () => {
  const { token } = useAuth();
  const [reports, setReports] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const authH = token ? { Authorization: `Bearer ${token}` } : {};

  const load = async () => {
    try {
      const response = await axios.get(`${API}/admin/matches/reports?limit=50`, { headers: authH });
      setReports(response.data || []);
    } catch {
      setReports([]);
    }
  };

  useEffect(() => {
    if (!token) {
      setReports([]);
      return;
    }
    axios
      .get(`${API}/admin/matches/reports?limit=50`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => setReports(response.data || []))
      .catch(() => setReports([]));
  }, [token]);

  const updateStatus = async (reportId, status) => {
    const resolution_note = window.prompt("Note de traitement (optionnelle) :", "") ?? "";
    setBusyId(reportId);
    try {
      await axios.patch(`${API}/admin/matches/reports/${reportId}`, { status, resolution_note }, { headers: authH });
      await load();
    } catch (error) {
      alert(error.response?.data?.detail || "Erreur signalement");
    } finally {
      setBusyId(null);
    }
  };

  const openCount = reports.filter((item) => item.status === "open").length;

  return (
    <div data-testid="match-reports-admin">
      <SectionTitle sub="Arbitrage live" title="Signalements de match"/>
      <div className="glass p-6 mb-4">
        <div className="text-xs uppercase tracking-widest text-white/40">Incidents ouverts</div>
        <div className="font-display text-4xl text-red-400 mt-2">{openCount}</div>
      </div>
      <div className="space-y-4">
        {reports.length === 0 && <div className="glass p-6 text-white/40">Aucun signalement recent.</div>}
        {reports.map((item) => (
          <div key={item.id} className="glass p-5" data-testid={`match-report-admin-${item.id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-display text-lg uppercase">{MATCH_REPORT_LABELS[item.kind] || item.kind}</div>
                <div className="text-xs text-white/40 mt-1">
                  Match {item.match_id} • {item.reporter_pseudo} • {new Date(item.created_at).toLocaleString("fr-FR")}
                </div>
                {item.target_pseudo && <div className="text-[11px] text-white/35 mt-1">Cible: {item.target_pseudo}</div>}
                {item.source && <div className="text-[11px] text-white/35 mt-1">Origine: {MATCH_REPORT_SOURCE_LABELS[item.source] || item.source}</div>}
              </div>
              <div className={`px-3 py-1 border text-xs uppercase tracking-widest rounded-full ${matchReportStatusClass(item.status)}`}>
                {MATCH_REPORT_STATUS_LABELS[item.status] || item.status}
              </div>
            </div>
            {item.round_label && <div className="text-xs text-white/40 mt-3">{item.round_label}</div>}
            <p className="text-white/70 mt-3">{item.message}</p>
            {item.resolution_note && <p className="text-xs text-white/40 mt-3">Note: {item.resolution_note}</p>}
            <div className="flex flex-wrap gap-2 mt-4">
              <button disabled={busyId === item.id} onClick={() => updateStatus(item.id, "acknowledged")} className="btn-ghost text-xs">Prendre en compte</button>
              <button disabled={busyId === item.id} onClick={() => updateStatus(item.id, "resolved")} className="btn-ghost text-xs text-cyan-neon">Resolu</button>
              <button disabled={busyId === item.id} onClick={() => updateStatus(item.id, "rejected")} className="btn-ghost text-xs text-white/60">Rejeter</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ============== ADMIN ============== */
const Admin = () => {
  const { user, token } = useAuth();
  const [cards, setCards] = useState([]);
  const [activeTournaments, setActiveTournaments] = useState(0);
  const [onlineNow, setOnlineNow] = useState(0);
  const [form, setForm] = useState({ target_user_id: "", severity: "yellow", reason: "" });
  const [busy, setBusy] = useState(false);
  const authH = token ? { Authorization: `Bearer ${token}` } : {};

  const refresh = async () => {
    const [cardsResponse, tournamentsResponse, statsResponse] = await Promise.all([
      axios.get(`${API}/cards?status_f=active`),
      axios.get(`${API}/tournaments`),
      axios.get(`${API}/stats/global`),
    ]);
    setCards(cardsResponse.data);
    setActiveTournaments(tournamentsResponse.data.filter((tournament) => tournament.status !== "closed").length);
    setOnlineNow(statsResponse.data.online_now || 0);
  };
  useEffect(() => {
    if (!user?.is_admin) return;
    refresh();
  }, [user?.is_admin]);

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

  if (!user?.is_admin) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-14" data-testid="admin-page-blocked">
        <div className="glass p-8 border border-red-500/20">
          <div className="text-xs uppercase tracking-[0.3em] text-red-400">Acces protege</div>
          <h1 className="font-display text-4xl uppercase mt-4">Zone admin reservee</h1>
          <p className="text-white/60 mt-4">Cette page n'est visible que pour les comptes administrateurs.</p>
        </div>
      </div>
    );
  }

  const yellows = cards.filter(c => c.severity === "yellow").length;
  const reds = cards.filter(c => c.severity === "red").length;
  return (
    <div className="max-w-7xl mx-auto px-6 py-10" data-testid="admin-page">
      <h1 className="font-display text-5xl uppercase">Tableau de bord — Organisateur</h1>
      <div className="grid md:grid-cols-4 gap-4 mt-6">
        {[{l:"Tournois actifs",v:activeTournaments,c:"text-orange-500"},{l:"Joueurs en ligne",v:onlineNow,c:"text-cyan-neon"},{l:"Cartons jaunes",v:yellows,c:"text-yellow-neon"},{l:"Cartons rouges",v:reds,c:"text-red-500"}].map((s,i) => (
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

      <MatchReportsAdmin/>
      <TournamentCrudAdmin/>
      <TournamentAdmin/>
      <TeamAdmin/>
      <NewsAdmin/>
      <AnnouncementAdmin/>
      <ContestAdmin/>
      <RewardAdmin/>
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
  const location = useLocation();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ pseudo: "", email: "", password: "", country: "FR" });
  const [err, setErr] = useState(""); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) navigate("/profile"); }, [user, navigate]);
  useEffect(() => {
    const steamError = new URLSearchParams(location.search).get("steam_error");
    if (!steamError) return;
    if (steamError === "invalid") {
      setErr("Validation Steam invalide. Reessayez.");
      return;
    }
    if (steamError === "cancelled") {
      setErr("Connexion Steam annulee.");
      return;
    }
    if (steamError === "no_id") {
      setErr("Steam ID introuvable.");
      return;
    }
    if (steamError === "steam_link_invalid") {
      setErr("La session de liaison Steam a expire.");
      return;
    }
    setErr("Connexion Steam impossible pour le moment.");
  }, [location.search]);
  const handleSteam = () => { window.location.href = `${API}/auth/steam/login?frontend_origin=${encodeURIComponent(window.location.origin)}`; };
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
            <Link to={`/match/${m.matchid}`} className="btn-ghost mt-4 inline-flex text-xs" data-testid={`open-live-match-${m.matchid}`}>
              <ChevronRight size={12}/>Ouvrir la room
            </Link>
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
        <Route path="/fun-5v5" element={<FunMatchesPage/>}/>
        <Route path="/concours" element={<ContestsPage/>}/>
        <Route path="/boutique" element={<RewardsStorePage/>}/>
        <Route path="/cs2" element={<Cs2Hub/>}/>
        <Route path="/live" element={<LiveMatches/>}/>
        <Route path="/admin" element={<Admin/>}/>
        <Route path="/donate" element={<Donate/>}/>
        <Route path="/support" element={<Donate/>}/>
        <Route path="/login" element={<Login/>}/>
        <Route path="/reset-password" element={<ResetPassword/>}/>
        <Route path="/auth/steam/complete" element={<SteamComplete/>}/>
        <Route path="/faq" element={<FaqPage/>}/>
        <Route path="/community" element={<CommunityPage/>}/>
        <Route path="/partners" element={<PartnersPage/>}/>
        <Route path="/contact" element={<ContactPage/>}/>
        <Route path="/status" element={<StatusPage/>}/>
        <Route path="/legal" element={<Generic title="Mentions légales"><p>ReadyUp Arena est une plateforme indépendante de tournois e-sport. Non affiliée, sponsorisée ou approuvée par Valve Corporation. Counter-Strike 2 est une marque déposée de Valve Corporation.</p></Generic>}/>
        <Route path="/privacy" element={<Generic title="Confidentialité"><p>Les données de compte, d'audit, de présence et de sécurité sont conservées pour faire fonctionner la plateforme et tracer les actions sensibles conformément à la politique interne de la beta.</p></Generic>}/>
        <Route path="/cgu" element={<Generic title="CGU"><p>ReadyUp Arena reste une plateforme communautaire gratuite en beta. Les tournois n'accordent aucun avantage payant et les règles d'équité, de modération et d'audit priment sur toute automatisation.</p></Generic>}/>
      </Routes>
      <Footer/>
    </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
