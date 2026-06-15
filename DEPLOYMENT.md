# Deployment Guide

## Cible recommandee

- Frontend : `Vercel`
- Backend API : `Google Cloud Run`
- Base de donnees : `MongoDB Atlas`
- Cache / job queue : `Redis` managé
- Domaine : `Amen`

## Option totalement gratuite

Si tu refuses toute activation de facturation Google Cloud, utilise plutot :

- frontend : `Vercel Hobby`
- backend : `Render Free`
- base de donnees : `MongoDB Atlas Free`
- Redis : `Upstash Free`

Le fichier [render.yaml](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/render.yaml) prepare le backend pour Render.

Limites a accepter :

- le service backend gratuit de Render se met en veille apres 15 minutes sans trafic et redemarre ensuite en environ une minute ;
- Render donne 750 heures gratuites par mois pour les web services free ;
- Atlas Free et Upstash Free ont des quotas ;
- sans methode de paiement ajoutee sur Render, les services sont suspendus si tu depasses les quotas gratuits au lieu d'etre factures.

## 1. MongoDB Atlas

1. Creer un cluster.
2. Creer un utilisateur applicatif.
3. Autoriser les IP du service backend.
   Pour un premier deploiement Cloud Run, `0.0.0.0/0` peut depanner temporairement, puis il faut resserrer.
4. Recuperer l'URI `mongodb+srv://...`.
5. Reporter cette valeur dans `MONGO_URL`.

Variables minimales backend :

```env
MONGO_URL=mongodb+srv://USER:PASSWORD@cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
DB_NAME=readyup_arena
REDIS_URL=rediss://default:UPSTASH_TOKEN@UPSTASH_HOST:6379
JWT_SECRET=generate-a-long-random-secret
ADMIN_EMAILS=admin@example.com
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=ChangeMeNow123!
FRONTEND_URL=https://readyuparena.gg
BACKEND_PUBLIC_URL=https://api.readyuparena.gg
CORS_ORIGINS=https://readyuparena.gg,https://www.readyuparena.gg,http://localhost:3000
MATCHZY_WEBHOOK_SECRET=generate-another-secret
MATCHZY_CONFIG_TOKEN=generate-a-third-secret
RCON_ENC_KEY=generate-a-fernet-key
```

Pour generer `RCON_ENC_KEY` :

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Google Cloud Run

Le backend est prevu pour etre construit depuis [backend/Dockerfile](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/backend/Dockerfile).

### Option A : Cloud Build

Le fichier [cloudbuild.yaml](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/cloudbuild.yaml) deploie automatiquement l'API.

Commande typique :

```bash
gcloud builds submit --config cloudbuild.yaml
```

### Option B : deploiement manuel

```bash
gcloud builds submit --tag europe-west1-docker.pkg.dev/PROJECT_ID/readyup-arena/readyup-arena-api:latest backend
gcloud run deploy readyup-arena-api \
  --image europe-west1-docker.pkg.dev/PROJECT_ID/readyup-arena/readyup-arena-api:latest \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080
```

### Option C : script PowerShell local

Le projet inclut maintenant [scripts/deploy-cloudrun.ps1](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/scripts/deploy-cloudrun.ps1).

1. Completer [backend/cloudrun.env](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/backend/cloudrun.env).
2. Installer le `Google Cloud SDK`.
3. Lancer :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-cloudrun.ps1 -ProjectId YOUR_GCP_PROJECT_ID
```

### Variables a poser dans Cloud Run

- `MONGO_URL`
- `DB_NAME`
- `REDIS_URL`
- `JWT_SECRET`
- `ADMIN_EMAILS`
- `SEED_ADMIN_EMAIL`
- `SEED_ADMIN_PASSWORD`
- `SEED_ADMIN_PSEUDO`
- `FRONTEND_URL`
- `BACKEND_PUBLIC_URL`
- `CORS_ORIGINS`
- `MATCHZY_WEBHOOK_SECRET`
- `MATCHZY_CONFIG_TOKEN`
- `RCON_ENC_KEY`
- `STRIPE_API_KEY` si Stripe est active
- `RESEND_API_KEY` et `SENDER_EMAIL` si reset password par email
- `TWITCH_CHANNEL`

Health checks disponibles :

- `/health/live`
- `/health/ready`

## 2.b MatchZy / FShost / CSTV

Pour un serveur `FShost.me` avec `MatchZy` deja installe :

1. Declarer le serveur dans l'admin ReadyUp avec :
   - host RCON
   - port RCON
   - host public
   - port jeu
   - port HLTV / GOTV si disponible
2. Poser `BACKEND_PUBLIC_URL` sur l'URL publique reelle de l'API.
3. Poser `MATCHZY_CONFIG_TOKEN` dans le backend.
4. Poser `MATCHZY_WEBHOOK_SECRET` dans le backend.
5. Quand le bracket est pret, lancer le match depuis l'admin :
   - ReadyUp genere le JSON MatchZy
   - ReadyUp pousse d'abord au serveur via RCON :
     - `matchzy_remote_log_url`
     - `matchzy_remote_log_auth_key`
     - `matchzy_remote_log_auth_value`
   - le serveur charge ce JSON avec `matchzy_loadmatch_url`
   - les events `series_start`, `map_result`, `series_end` reviennent dans l'API
   - le bracket peut alors etre mis a jour automatiquement sur `series_end`

Avec cette approche, aucun ticket hebergeur n'est necessaire si le RCON fonctionne.

### Cas Fake RCON

`fake_rcon` ne remplace pas le RCON reseau pour une application web.

- `fake_rcon_password` et `fake_rcon <command>` servent a un admin connecte en jeu ;
- le backend ReadyUp ne peut pas taper cette commande comme un joueur ;
- si tu n'exposes plus de `rcon_password` reseau, il faut passer le serveur en `control_mode=bridge`.

Le mode `bridge` utilise un plugin CounterStrikeSharp qui :

- contacte le backend ;
- recupere les commandes en attente ;
- execute localement `Server.ExecuteCommand(...)` ;
- renvoie l'etat d'execution au backend.

### Fallback persistant via FTP

Si tu veux que le webhook survive a un redemarrage meme avant le prochain lancement depuis ReadyUp, ajoute ces cvars dans la config MatchZy du serveur :

```cfg
matchzy_remote_log_url "https://your-api-domain/api/cs2/webhooks/matchzy"
matchzy_remote_log_auth_key "Authorization"
matchzy_remote_log_auth_value "Bearer YOUR_MATCHZY_WEBHOOK_SECRET"
```

Chemins observes sur ton serveur local `E:\p3616` :

- `E:\p3616\cfg\matchzy\config.cfg`
- `E:\p3616\cfg\custom\matchzyload.cfg`
- `E:\p3616\cfg\custom\cstv.cfg`
- `E:\p3616\addons\counterstrikesharp\configs\plugins\CS2-SimpleAdmin\Commands.json`

Etat constate :

- `MatchZy` present et demarre en `matchzy_autostart_mode 1`
- `css_rcon` disponible via `CS2-SimpleAdmin`
- `CSTV` actif via `cfg/custom/cstv.cfg`
- `FSH-CS2GOTV`, `FSH-MatchZy` et `FSH-TVFIX` charges cote serveur

## 3. Vercel

Le frontend utilise [frontend/vercel.json](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/frontend/vercel.json).

### Configuration Vercel

1. Importer le repo GitHub.
2. Definir le `Root Directory` sur `frontend`.
3. Ajouter la variable :

```env
REACT_APP_BACKEND_URL=https://api.readyuparena.gg
```

4. Lancer le deploiement.

Le routeur SPA est gere par la rewrite vers `index.html`.

## 4. Amen

Si `Amen` gere uniquement le domaine, il faut surtout le DNS :

- `A` ou `ALIAS` / `ANAME` pour le frontend selon la cible fournie par Vercel.
- `CNAME` `www` vers la cible Vercel.
- `CNAME` `api` vers le domaine Cloud Run personnalise, ou mapping via load balancer selon ta config GCP.

Exemple cible finale :

- `readyuparena.gg` -> Vercel
- `www.readyuparena.gg` -> Vercel
- `api.readyuparena.gg` -> Cloud Run

## 5. Ce qui manque encore hors code

Je n'ai pas acces ici a :

- ton projet `Google Cloud`
- ton compte `Vercel`
- ton compte `Amen`
- ton projet `MongoDB Atlas`

Donc je ne peux pas poser les variables, creer les DNS ni lancer le deploiement reel depuis cette session.

## 6. Risques a traiter avant prod

- `backend/server.py` reste trop gros et devrait etre decoupe.
- Une partie de la logique produit reste partiellement mockee.
- Les webhooks, Steam, Twitch et Stripe doivent etre valides avec les vraies cles.
- Il faut une vraie offre Redis managée pour la resilience du temps reel et des jobs.
