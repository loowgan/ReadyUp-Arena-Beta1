# CS2 Server FShost Setup

Ce document formalise le raccordement de ReadyUp Arena a un serveur CS2 `FShost.me` deja equipe de `MatchZy`, `CS2-SimpleAdmin`, `fake_rcon` et `CSTV`.

## Etat verifie sur le serveur

Chemins constates sur l'instance locale `E:\p3616` :

- `E:\p3616\cfg\matchzy\config.cfg`
- `E:\p3616\cfg\custom\matchzyload.cfg`
- `E:\p3616\cfg\custom\cstv.cfg`
- `E:\p3616\addons\counterstrikesharp\configs\plugins\CS2-SimpleAdmin\Commands.json`
- `E:\p3616\addons\counterstrikesharp\plugins\FSH-MatchZy`
- `E:\p3616\addons\counterstrikesharp\plugins\FSH-CS2GOTV`
- `E:\p3616\addons\counterstrikesharp\plugins\FSH-TVFIX`

Constats utiles :

- `matchzy_autostart_mode 1` est deja actif.
- `matchzy_loadmatch_url` est supporte.
- `css_rcon` est disponible via `CS2-SimpleAdmin`.
- `CSTV` est deja configure avec `tv_record_immediate 1`.
- `FSH-MatchZy` expose les cvars `matchzy_remote_log_url`, `matchzy_remote_log_auth_key` et `matchzy_remote_log_auth_value`.

## Mode recommande

Le mode recommande ne depend pas de l'hebergeur :

1. ReadyUp enregistre le serveur avec son host RCON, port RCON, host public, port jeu et port GOTV.
2. Au lancement d'un match de bracket, ReadyUp pousse automatiquement au serveur :
   - `matchzy_remote_log_url`
   - `matchzy_remote_log_auth_key`
   - `matchzy_remote_log_auth_value`
3. ReadyUp envoie ensuite `matchzy_loadmatch_url` avec le header de recuperation de config.
4. MatchZy renvoie les events `series_start`, `map_result` et `series_end` a l'API.
5. `series_end` cloture automatiquement le match de bracket et libere le serveur.

Prerequis backend :

- `BACKEND_PUBLIC_URL`
- `MATCHZY_WEBHOOK_SECRET`
- `MATCHZY_CONFIG_TOKEN`
- `RCON_ENC_KEY`

## Important sur Fake RCON

`fake_rcon` est une commande locale cote joueur/admin connecte, pas une API distante pour le backend.

Consequence :

- si tu gardes un vrai `rcon_password` reseau, ReadyUp peut piloter directement en mode `rcon` ;
- si tu abandonnes le `rcon_password` reseau, ReadyUp doit piloter en mode `bridge` ;
- le mode `bridge` est celui a utiliser avec ton serveur actuel si tu veux sortir du RCON reseau.

## Persistance via FTP

Si tu veux une configuration persistante cote serveur, ajoute ces lignes dans `cfg/matchzy/config.cfg` :

```cfg
matchzy_remote_log_url "https://your-api-domain/api/cs2/webhooks/matchzy"
matchzy_remote_log_auth_key "Authorization"
matchzy_remote_log_auth_value "Bearer YOUR_MATCHZY_WEBHOOK_SECRET"
```

Tu peux aussi les mettre dans un fichier dedie, par exemple `cfg/custom/readyup_matchzy_remote.cfg`, puis l'executer depuis ton flux de demarrage MatchZy.

Exemple :

```cfg
exec custom/readyup_matchzy_remote.cfg
exec custom/matchzyload.cfg
```

## Commandes utiles

Verification RCON :

```text
status
```

Application manuelle du webhook MatchZy :

```text
matchzy_remote_log_url "https://your-api-domain/api/cs2/webhooks/matchzy"
matchzy_remote_log_auth_key "Authorization"
matchzy_remote_log_auth_value "Bearer YOUR_MATCHZY_WEBHOOK_SECRET"
```

Chargement d'un match distant :

```text
matchzy_loadmatch_url "https://your-api-domain/api/cs2/tournaments/TOURNOI_ID/bracket-matches/MATCH_ID/matchzy-config" "Authorization" "Bearer YOUR_MATCHZY_CONFIG_TOKEN"
```

## Securite

Les fichiers serveur inspectes contiennent deja des secrets reels cote RCON et Discord. Ils doivent etre consideres comme compromis si ce dossier a circule hors de ta machine.

Actions recommande es :

- changer le mot de passe RCON ;
- regenerer le webhook Discord CSTV si tu l'utilises encore ;
- ne jamais versionner ces valeurs dans Git.
