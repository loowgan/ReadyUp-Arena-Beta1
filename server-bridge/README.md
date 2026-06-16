# ReadyUp Arena Bridge

Ce dossier contient un plugin CounterStrikeSharp pour piloter un serveur CS2 depuis ReadyUp Arena sans RCON reseau.

## Principe

Le plugin :

- envoie un heartbeat au backend ;
- recupere les commandes en attente ;
- execute localement `Server.ExecuteCommand(...)` ;
- retourne l'etat `completed` ou `failed` au backend ;
- intercepte `!report` dans le chat joueur et remonte le signalement au site.

Ce mode est adapte aux serveurs qui utilisent `fake_rcon` cote jeu et ne veulent plus exposer de `rcon_password` reseau.

## Fichiers

- `ReadyUpArenaBridge/ReadyUpArenaBridge.csproj`
- `ReadyUpArenaBridge/ReadyUpArenaBridgePlugin.cs`
- `ReadyUpArenaBridge/ReadyUpArenaBridgeConfig.cs`

## Build

Depuis ce dossier :

```powershell
dotnet build .\ReadyUpArenaBridge\ReadyUpArenaBridge.csproj -c Release
```

DLL attendue :

```text
server-bridge/ReadyUpArenaBridge/bin/Release/net8.0/ReadyUpArenaBridge.dll
```

## Installation FTP

Creer un dossier :

```text
addons/counterstrikesharp/plugins/ReadyUpArenaBridge
```

Y copier :

- `ReadyUpArenaBridge.dll`
- le fichier de config `ReadyUpArenaBridge.json`

## Exemple de config

```json
{
  "BackendBaseUrl": "https://readyup-arena-api.onrender.com",
  "BridgeToken": "replace-with-bridge-token",
  "PollIntervalSeconds": 5,
  "VerboseLogging": false,
  "EnableChatReports": true
}
```

Le plugin cree automatiquement un fichier exemple au premier chargement s'il est absent.

## Signalements en jeu

Commande joueur :

```text
!report pseudo_du_joueur raison
```

Exemples :

```text
!report weedzaman toxicite vocale
!report 76561197983604306 ghosting
```

Comportement :

- le message n'est pas publie dans le chat public ;
- le backend dedoublonne les signalements d'un meme joueur contre la meme cible ;
- apres 3 signalements distincts sur la meme cible pendant le meme match, un carton jaune automatique est emis.
