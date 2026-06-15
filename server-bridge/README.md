# ReadyUp Arena Bridge

Ce dossier contient un plugin CounterStrikeSharp pour piloter un serveur CS2 depuis ReadyUp Arena sans RCON reseau.

## Principe

Le plugin :

- envoie un heartbeat au backend ;
- recupere les commandes en attente ;
- execute localement `Server.ExecuteCommand(...)` ;
- retourne l'etat `completed` ou `failed` au backend.

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
  "VerboseLogging": false
}
```

Le plugin cree automatiquement un fichier exemple au premier chargement s'il est absent.
