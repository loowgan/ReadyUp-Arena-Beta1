"""Seed data for ReadyUp Arena — migrates former in-memory mocks into MongoDB.
Collections seeded only when empty (idempotent)."""
from datetime import datetime, timezone, timedelta

TEAMS = [
    {"id": "t1", "name": "Nova Strike", "tag": "NOVA", "logo_color": "#FF4600", "country": "FR", "level": 42, "elo": 2150, "wins": 87, "losses": 23, "trophies": 5, "reliability": 96},
    {"id": "t2", "name": "Pixel Reapers", "tag": "PXR", "logo_color": "#00F0FF", "country": "DE", "level": 38, "elo": 2080, "wins": 72, "losses": 31, "trophies": 3, "reliability": 92},
    {"id": "t3", "name": "Arctic Wolves", "tag": "AWLV", "logo_color": "#3B82F6", "country": "SE", "level": 35, "elo": 1980, "wins": 65, "losses": 28, "trophies": 2, "reliability": 89},
    {"id": "t4", "name": "Rush B Legends", "tag": "RBL", "logo_color": "#FFB800", "country": "RU", "level": 33, "elo": 1920, "wins": 58, "losses": 35, "trophies": 4, "reliability": 88},
    {"id": "t5", "name": "Crimson Five", "tag": "CR5", "logo_color": "#FF003C", "country": "PT", "level": 31, "elo": 1870, "wins": 52, "losses": 33, "trophies": 1, "reliability": 85},
    {"id": "t6", "name": "Tactical Ducks", "tag": "TDX", "logo_color": "#10B981", "country": "NL", "level": 28, "elo": 1810, "wins": 47, "losses": 38, "trophies": 1, "reliability": 90},
    {"id": "t7", "name": "Echo Squad", "tag": "ECHO", "logo_color": "#8B5CF6", "country": "PL", "level": 26, "elo": 1760, "wins": 41, "losses": 39, "trophies": 0, "reliability": 82},
    {"id": "t8", "name": "Midnight Aces", "tag": "MAC", "logo_color": "#EC4899", "country": "ES", "level": 24, "elo": 1710, "wins": 38, "losses": 42, "trophies": 0, "reliability": 80},
]

PLAYERS = [
    {"id": "p1", "pseudo": "Vortex", "country": "FR", "level": 47, "xp": 8420, "xp_next": 10000, "elo": 2240, "rank_cs2": "Global Elite", "kdr": 1.42, "role": "AWP", "steam_verified": True, "online": True, "available": True, "team_id": "t1", "reliability": 97},
    {"id": "p2", "pseudo": "Cipher", "country": "DE", "level": 44, "xp": 7200, "xp_next": 9000, "elo": 2180, "rank_cs2": "Supreme", "kdr": 1.31, "role": "IGL", "steam_verified": True, "online": True, "available": False, "team_id": "t2", "reliability": 95},
    {"id": "p3", "pseudo": "NoxFury", "country": "SE", "level": 41, "xp": 6800, "xp_next": 8500, "elo": 2090, "rank_cs2": "Legendary Eagle Master", "kdr": 1.24, "role": "Entry", "steam_verified": True, "online": True, "available": True, "team_id": None, "reliability": 91},
    {"id": "p4", "pseudo": "Spectre", "country": "RU", "level": 38, "xp": 5600, "xp_next": 7000, "elo": 1980, "rank_cs2": "Legendary Eagle", "kdr": 1.18, "role": "Support", "steam_verified": True, "online": True, "available": True, "team_id": None, "reliability": 88},
    {"id": "p5", "pseudo": "Halcyon", "country": "PT", "level": 35, "xp": 4900, "xp_next": 6000, "elo": 1890, "rank_cs2": "Distinguished Master Guardian", "kdr": 1.09, "role": "Rifler", "steam_verified": False, "online": True, "available": True, "team_id": None, "reliability": 84},
    {"id": "p6", "pseudo": "Blaze", "country": "NL", "level": 33, "xp": 4200, "xp_next": 5500, "elo": 1820, "rank_cs2": "Master Guardian Elite", "kdr": 1.04, "role": "Lurker", "steam_verified": True, "online": False, "available": False, "team_id": "t6", "reliability": 87},
    {"id": "p7", "pseudo": "Quantum", "country": "PL", "level": 30, "xp": 3500, "xp_next": 4500, "elo": 1750, "rank_cs2": "Master Guardian II", "kdr": 0.98, "role": "AWP", "steam_verified": True, "online": True, "available": True, "team_id": None, "reliability": 78},
    {"id": "p8", "pseudo": "Wraith", "country": "ES", "level": 28, "xp": 2900, "xp_next": 4000, "elo": 1690, "rank_cs2": "Master Guardian I", "kdr": 0.95, "role": "Entry", "steam_verified": False, "online": True, "available": True, "team_id": None, "reliability": 76},
]

NEWS = [
    {"id": "n1", "title": "Lancement public de ReadyUp Arena", "_offset_hours": -48, "excerpt": "La plateforme entre en bêta ouverte avec automatisation complète."},
    {"id": "n2", "title": "Major CS2 — Programme en direct", "_offset_hours": -24, "excerpt": "Suivez tous les matchs du Major directement depuis l'accueil via Twitch."},
    {"id": "n3", "title": "Système de cartons jaunes & rouges actif", "_offset_hours": -10, "excerpt": "Modération automatisée des signalements en direct durant les matchs."},
]

ANNOUNCEMENTS = [
    {
        "id": "a1",
        "title": "Beta ouverte ReadyUp Arena",
        "body": "Les premiers tournois publics sont en ligne avec salle d'attente, draw, bracket et supervision CS2.",
        "kind": "beta",
        "priority": 5,
        "is_active": True,
        "cta_label": "Voir les tournois",
        "cta_url": "/tournaments",
        "_starts_offset_hours": -12,
        "_ends_offset_hours": 240,
    },
    {
        "id": "a2",
        "title": "Hub CS2 désormais visible",
        "body": "La couche serveurs, MatchZy et état des services est maintenant accessible depuis la navigation principale.",
        "kind": "feature",
        "priority": 4,
        "is_active": True,
        "cta_label": "Ouvrir le hub",
        "cta_url": "/cs2",
        "_starts_offset_hours": -2,
        "_ends_offset_hours": 168,
    },
]

CONTESTS = [
    {
        "id": "c1",
        "title": "Concours ouverture beta",
        "summary": "Tirage communautaire pour celebrer l'ouverture des premiers tournois publics.",
        "body": "Une participation par compte. Les gagnants recoivent un badge fondateur et un lot communautaire valide par l'administration.",
        "reward_label": "Badge fondateur + lot communautaire",
        "is_active": True,
        "max_entries": 500,
        "banner_color": "#FF4600",
        "cta_label": "Participer",
        "cta_url": "/concours",
        "_starts_offset_hours": -24,
        "_ends_offset_hours": 240,
    },
    {
        "id": "c2",
        "title": "Weekend duo spotlight",
        "summary": "Mets en avant ton binome et tente de gagner un role Discord exclusif.",
        "body": "Concours reserve a la communaute beta. Les gagnants seront annonces dans les news et sur Discord.",
        "reward_label": "Role Discord + mise en avant front page",
        "is_active": True,
        "max_entries": 200,
        "banner_color": "#00F0FF",
        "cta_label": "Voir le concours",
        "cta_url": "/concours",
        "_starts_offset_hours": -6,
        "_ends_offset_hours": 120,
    },
]

REWARDS = [
    {
        "id": "rw1",
        "title": "Badge Fondateur",
        "summary": "Badge permanent visible sur le profil public.",
        "description": "Attribue un badge de soutien beta sur le profil et dans les salons de match.",
        "category": "badge",
        "cost_tokens": 250,
        "stock": 150,
        "is_active": True,
        "accent_color": "#00F0FF",
        "delivery_notes": "Attribution automatique apres validation.",
    },
    {
        "id": "rw2",
        "title": "Role Discord Arena",
        "summary": "Acces a un role communautaire exclusif sur Discord.",
        "description": "Permet d'obtenir un role saisonnier cote communaute sans avantage competitif.",
        "category": "community",
        "cost_tokens": 400,
        "stock": 80,
        "is_active": True,
        "accent_color": "#FFB800",
        "delivery_notes": "Traitement manuel par un administrateur.",
    },
    {
        "id": "rw3",
        "title": "Mise en avant equipe",
        "summary": "Carte equipe mise en avant sur l'accueil pendant une rotation editoriale.",
        "description": "La mise en avant reste purement visuelle et n'influe sur aucun match.",
        "category": "spotlight",
        "cost_tokens": 900,
        "stock": 12,
        "is_active": True,
        "accent_color": "#10B981",
        "delivery_notes": "Planification editoriale sous 7 jours.",
    },
]

# status uses the tournament state machine: open -> registering -> starting -> live -> closed
TOURNAMENTS = [
    {"id": "tr1", "name": "ReadyUp Cup #12", "organizer": "ReadyUp Official", "format": "5v5", "mode": "Single Elim BO3",
     "capacity": 16, "registered": 14, "status": "registering", "_starts_offset_hours": 2,
     "prize": "1500 € + Skins sponsorisés", "region": "EU", "level_min": 20, "image_color": "#FF4600"},
    {"id": "tr2", "name": "Neon Strike Open", "organizer": "Pixel League", "format": "5v5", "mode": "Double Elim BO1",
     "capacity": 32, "registered": 32, "status": "live", "_starts_offset_hours": -1,
     "prize": "800 € + Trophée", "region": "EU/NA", "level_min": 15, "image_color": "#00F0FF"},
    {"id": "tr3", "name": "Crimson Showdown 3v3", "organizer": "Crimson Five", "format": "3v3", "mode": "Round Robin BO1",
     "capacity": 12, "registered": 8, "status": "open", "_starts_offset_hours": 24,
     "prize": "400 € + Badges", "region": "EU", "level_min": 10, "image_color": "#FF003C"},
    {"id": "tr4", "name": "Midnight Express 1v1", "organizer": "Midnight Aces", "format": "1v1", "mode": "Single Elim BO1",
     "capacity": 64, "registered": 47, "status": "registering", "_starts_offset_hours": 6,
     "prize": "200 € + Cosmétiques", "region": "WORLD", "level_min": 5, "image_color": "#FFB800"},
    {"id": "tr5", "name": "Veteran Trials 5v5", "organizer": "ReadyUp Official", "format": "5v5", "mode": "Swiss BO3",
     "capacity": 24, "registered": 24, "status": "live", "_starts_offset_hours": -4,
     "prize": "2500 € + Skin AWP Sponsorisé", "region": "EU", "level_min": 30, "image_color": "#8B5CF6"},
    {"id": "tr6", "name": "Arctic Brawl", "organizer": "Arctic Wolves", "format": "2v2", "mode": "Single Elim BO1",
     "capacity": 16, "registered": 11, "status": "open", "_starts_offset_hours": 72,
     "prize": "150 € + Rôles Discord", "region": "EU", "level_min": 1, "image_color": "#3B82F6"},
]


async def seed_all(db):
    """Insert seed docs into Mongo only if each collection is empty."""
    now = datetime.now(timezone.utc)
    if await db.teams.count_documents({}) == 0:
        await db.teams.insert_many([dict(t) for t in TEAMS])
    if await db.players.count_documents({}) == 0:
        await db.players.insert_many([dict(p) for p in PLAYERS])
    if await db.news.count_documents({}) == 0:
        docs = []
        for n in NEWS:
            d = dict(n)
            d["date"] = (now + timedelta(hours=d.pop("_offset_hours"))).isoformat()
            d["body"] = d["excerpt"]
            d["created_at"] = now.isoformat()
            d["updated_at"] = None
            docs.append(d)
        await db.news.insert_many(docs)
    if await db.announcements.count_documents({}) == 0:
        docs = []
        for a in ANNOUNCEMENTS:
            d = dict(a)
            d["starts_at"] = (now + timedelta(hours=d.pop("_starts_offset_hours"))).isoformat()
            d["ends_at"] = (now + timedelta(hours=d.pop("_ends_offset_hours"))).isoformat()
            d["created_at"] = now.isoformat()
            d["updated_at"] = None
            docs.append(d)
        await db.announcements.insert_many(docs)
    if await db.contests.count_documents({}) == 0:
        docs = []
        for contest in CONTESTS:
            d = dict(contest)
            d["starts_at"] = (now + timedelta(hours=d.pop("_starts_offset_hours"))).isoformat()
            d["ends_at"] = (now + timedelta(hours=d.pop("_ends_offset_hours"))).isoformat()
            d["created_at"] = now.isoformat()
            d["updated_at"] = None
            docs.append(d)
        await db.contests.insert_many(docs)
    if await db.rewards.count_documents({}) == 0:
        docs = []
        for reward in REWARDS:
            d = dict(reward)
            d["created_at"] = now.isoformat()
            d["updated_at"] = None
            docs.append(d)
        await db.rewards.insert_many(docs)
    if await db.tournaments.count_documents({}) == 0:
        docs = []
        for t in TOURNAMENTS:
            d = dict(t)
            d["starts_at"] = (now + timedelta(hours=d.pop("_starts_offset_hours"))).isoformat()
            d["created_at"] = now.isoformat()
            d["updated_at"] = None
            d["description"] = f"{d['name']} est un tournoi {d['format']} de demonstration avec orchestration automatisee, salle d'attente temps reel et suivi CS2."
            d["maps"] = ["Mirage", "Inferno", "Anubis"]
            d["rules"] = [
                "Presence requise avant le verrouillage du roster.",
                "Les remplacements suivent les regles de la salle d'attente.",
                "Les decisions sensibles sont journalisees.",
            ]
            docs.append(d)
        await db.tournaments.insert_many(docs)
