# ReadyUp Arena

ReadyUp Arena est une plateforme web de tournois CS2 avec frontend React, backend FastAPI, MongoDB, Redis et des integrations externes optionnelles comme Steam OpenID, Twitch et Stripe.

## Stack actuelle

- `frontend/` : React 19 + CRACO + Tailwind.
- `backend/` : FastAPI + Motor + Redis.
- `MongoDB Atlas` : base de donnees recommandee pour la production.
- `Google Cloud Run` : cible recommandee pour l'API.
- `Vercel` : cible recommandee pour le frontend.
- `Amen` : registrar / DNS / domaine personnalise.

## Option 100% gratuite pour la beta

Si tu veux eviter toute facturation Google Cloud :

- frontend sur `Vercel Hobby` ;
- backend sur `Render Free` ;
- base sur `MongoDB Atlas Free` ;
- Redis sur `Upstash Free`.

Le backend Render est preconfigure dans [render.yaml](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/render.yaml).

Compromis principaux :

- le backend Render gratuit se met en veille apres inactivite et peut mettre environ une minute a repartir ;
- Atlas Free et Upstash Free ont des quotas ;
- c'est adapte a une beta ou a un projet hobby, pas a une vraie prod chargee.

## Demarrage local

1. Copier `backend/.env.example` vers `backend/.env`.
2. Copier `frontend/.env.example` vers `frontend/.env`.
3. Completer au minimum `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAILS` et `REACT_APP_BACKEND_URL`.
4. Lancer l'infra locale avec `docker compose up -d mongo redis`.
5. Backend :
   `cd backend && pip install -r requirements.txt && uvicorn server:app --reload --port 8000`
6. Frontend :
   `cd frontend && yarn install && yarn start`

## Points de production deja traites

- suppression des identifiants admin codes en dur ;
- variables d'environnement d'exemple ajoutees ;
- endpoints de sante `/health`, `/health/live`, `/health/ready` ;
- Dockerfile backend pour Cloud Run ;
- configuration Vercel pour le frontend ;
- documentation de deploiement pour `MongoDB Atlas`, `Cloud Run`, `Vercel` et `Amen`.

## Documentation

- Procedure complete : [DEPLOYMENT.md](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/DEPLOYMENT.md)
- Variables backend : [backend/.env.example](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/backend/.env.example)
- Variables frontend : [frontend/.env.example](C:/Users/logan/Desktop/READYUPARENA/ReadyUp-Arena-main-corrige/ReadyUp-Arena-main/frontend/.env.example)

## Limites fonctionnelles restantes

Le projet n'est pas encore une implementation complete du cahier des charges long fourni dans les `.md`. Plusieurs blocs restent partiels ou mocketes, notamment :

- statut Twitch encore simule ;
- une partie du produit reste monolithique dans `backend/server.py` ;
- le parcours MatchZy / CS2 / arbitrage n'est pas encore complet bout en bout ;
- la mise en ligne necessite toujours les vraies valeurs d'acces Cloud / Mongo / DNS.
