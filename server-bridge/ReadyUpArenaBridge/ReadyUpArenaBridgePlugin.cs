using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Commands;
using CounterStrikeSharp.API.Modules.Timers;
using Microsoft.Extensions.Logging;

namespace ReadyUpArenaBridge;

public sealed class ReadyUpArenaBridgePlugin : BasePlugin
{
    private readonly HttpClient _httpClient = new();
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    private ReadyUpArenaBridgeConfig _config = new();
    private int _pollInFlight;
    private string _currentMap = "";

    public override string ModuleName => "ReadyUp Arena Bridge";
    public override string ModuleVersion => "0.1.0";
    public override string ModuleAuthor => "OpenAI";
    public override string ModuleDescription => "Bridge plugin between ReadyUp Arena and a CS2 server without network RCON.";

    public override void Load(bool hotReload)
    {
        LoadConfig();
        ConfigureHttpClient();

        RegisterListener<Listeners.OnMapStart>(mapName =>
        {
            _currentMap = mapName;
            if (_config.VerboseLogging)
            {
                Logger.LogInformation("ReadyUp bridge map start: {MapName}", mapName);
            }
        });
        AddCommandListener("say", HandleSayCommand, HookMode.Pre);
        AddCommandListener("say_team", HandleSayCommand, HookMode.Pre);

        AddTimer(Math.Max(2, _config.PollIntervalSeconds), PollTimer, TimerFlags.REPEAT);
        Server.NextWorldUpdate(() =>
        {
            var heartbeat = BuildHeartbeatRequest("online");
            _ = Task.Run(() => SendHeartbeatAsync(heartbeat));
        });
    }

    public override void Unload(bool hotReload)
    {
        _httpClient.Dispose();
    }

    private void LoadConfig()
    {
        Directory.CreateDirectory(ModuleDirectory);
        var configPath = Path.Combine(ModuleDirectory, "ReadyUpArenaBridge.json");
        if (!File.Exists(configPath))
        {
            var sample = new ReadyUpArenaBridgeConfig
            {
                BackendBaseUrl = "https://readyup-arena-api.onrender.com",
                BridgeToken = "replace-with-bridge-token",
                PollIntervalSeconds = 5,
                VerboseLogging = false,
            };
            File.WriteAllText(configPath, JsonSerializer.Serialize(sample, _jsonOptions), Encoding.UTF8);
            Logger.LogWarning("ReadyUp bridge config created at {ConfigPath}. Complete it before using the plugin.", configPath);
            _config = sample;
            return;
        }

        var raw = File.ReadAllText(configPath, Encoding.UTF8);
        _config = JsonSerializer.Deserialize<ReadyUpArenaBridgeConfig>(raw, _jsonOptions) ?? new ReadyUpArenaBridgeConfig();
    }

    private void ConfigureHttpClient()
    {
        _httpClient.Timeout = TimeSpan.FromSeconds(10);
        _httpClient.DefaultRequestHeaders.Clear();
        _httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("ReadyUpArenaBridge/0.1.0");

        var baseUrl = (_config.BackendBaseUrl ?? "").Trim().TrimEnd('/');
        if (!string.IsNullOrWhiteSpace(baseUrl))
        {
            _httpClient.BaseAddress = new Uri(baseUrl);
        }

        var token = (_config.BridgeToken ?? "").Trim();
        if (!string.IsNullOrWhiteSpace(token))
        {
            _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }
    }

    private bool HasBridgeConfiguration()
    {
        return _httpClient.BaseAddress != null
            && !string.IsNullOrWhiteSpace(_config.BridgeToken)
            && !_config.BridgeToken.Contains("replace-with-bridge-token", StringComparison.OrdinalIgnoreCase);
    }

    private bool IsConfigured()
    {
        if (_httpClient.BaseAddress == null)
        {
            Logger.LogWarning("ReadyUp bridge disabled: BackendBaseUrl manquant");
            return false;
        }

        if (string.IsNullOrWhiteSpace(_config.BridgeToken) || _config.BridgeToken.Contains("replace-with-bridge-token", StringComparison.OrdinalIgnoreCase))
        {
            Logger.LogWarning("ReadyUp bridge disabled: BridgeToken manquant");
            return false;
        }

        return true;
    }

    private HookResult HandleSayCommand(CCSPlayerController? player, CommandInfo commandInfo)
    {
        if (!_config.EnableChatReports || !HasBridgeConfiguration())
        {
            return HookResult.Continue;
        }

        if (player is not { IsValid: true } || player.IsBot)
        {
            return HookResult.Continue;
        }

        var text = (commandInfo.ArgString ?? string.Empty).Trim().Trim('"');
        if (string.IsNullOrWhiteSpace(text) && commandInfo.ArgCount > 1)
        {
            text = string.Join(" ", Enumerable.Range(1, commandInfo.ArgCount - 1).Select(commandInfo.GetArg)).Trim().Trim('"');
        }

        if (!text.StartsWith("!report", StringComparison.OrdinalIgnoreCase))
        {
            return HookResult.Continue;
        }

        var remainder = text.Length > 7 ? text[7..].Trim() : string.Empty;
        if (string.IsNullOrWhiteSpace(remainder))
        {
            commandInfo.ReplyToCommand("Usage: !report <pseudo ou steamid> <raison>");
            return HookResult.Handled;
        }

        var resolved = TryResolveReportTarget(player, remainder);
        if (resolved == null)
        {
            commandInfo.ReplyToCommand("Joueur introuvable. Usage: !report <pseudo ou steamid> <raison>");
            return HookResult.Handled;
        }

        var (target, reason) = resolved.Value;
        var reporterSteamId = TryGetSteamId64(player);
        var targetSteamId = TryGetSteamId64(target);
        if (string.IsNullOrWhiteSpace(reporterSteamId) || string.IsNullOrWhiteSpace(targetSteamId))
        {
            commandInfo.ReplyToCommand("Steam indisponible, signalement refuse.");
            return HookResult.Handled;
        }

        if (reporterSteamId == targetSteamId)
        {
            commandInfo.ReplyToCommand("Impossible de te signaler toi-meme.");
            return HookResult.Handled;
        }

        var payload = new BridgePlayerReportRequest
        {
            ReporterPseudo = (player.PlayerName ?? "Joueur").Trim(),
            ReporterSteamId = reporterSteamId,
            TargetPseudo = (target.PlayerName ?? "Joueur").Trim(),
            TargetSteamId = targetSteamId,
            Reason = reason,
            Kind = "behavior",
        };

        if (_config.VerboseLogging)
        {
            Logger.LogInformation(
                "ReadyUp bridge captured !report {Reporter} -> {Target}: {Reason}",
                payload.ReporterPseudo,
                payload.TargetPseudo,
                payload.Reason);
        }

        commandInfo.ReplyToCommand($"Signalement envoye pour {payload.TargetPseudo}.");
        _ = Task.Run(async () =>
        {
            try
            {
                await SubmitPlayerReportAsync(payload);
            }
            catch (Exception ex)
            {
                Logger.LogWarning(ex, "ReadyUp bridge chat report failed");
            }
        });
        return HookResult.Handled;
    }

    private (CCSPlayerController target, string reason)? TryResolveReportTarget(CCSPlayerController reporter, string raw)
    {
        var players = Utilities.GetPlayers()
            .Where(p => p is { IsValid: true, IsBot: false } && p.Slot != reporter.Slot)
            .OrderByDescending(p => (p.PlayerName ?? string.Empty).Trim().Length)
            .ToList();
        if (players.Count == 0)
        {
            return null;
        }

        var remainder = (raw ?? string.Empty).Trim();
        foreach (var candidate in players)
        {
            var name = (candidate.PlayerName ?? string.Empty).Trim();
            if (!string.IsNullOrWhiteSpace(name))
            {
                if (remainder.Equals(name, StringComparison.OrdinalIgnoreCase))
                {
                    return (candidate, "Signalement en jeu");
                }

                if (remainder.StartsWith(name + " ", StringComparison.OrdinalIgnoreCase))
                {
                    var reason = remainder[name.Length..].Trim();
                    return (candidate, string.IsNullOrWhiteSpace(reason) ? "Signalement en jeu" : reason);
                }
            }

            var steamId = TryGetSteamId64(candidate);
            if (string.IsNullOrWhiteSpace(steamId))
            {
                continue;
            }

            if (remainder.Equals(steamId, StringComparison.OrdinalIgnoreCase))
            {
                return (candidate, "Signalement en jeu");
            }

            if (remainder.StartsWith(steamId + " ", StringComparison.OrdinalIgnoreCase))
            {
                var reason = remainder[steamId.Length..].Trim();
                return (candidate, string.IsNullOrWhiteSpace(reason) ? "Signalement en jeu" : reason);
            }
        }

        var firstSpace = remainder.IndexOf(' ');
        if (firstSpace <= 0)
        {
            return null;
        }

        var query = remainder[..firstSpace].Trim();
        var fallbackReason = remainder[(firstSpace + 1)..].Trim();
        var narrowed = players
            .Where(p => !string.IsNullOrWhiteSpace(p.PlayerName) && p.PlayerName.Contains(query, StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (narrowed.Count != 1)
        {
            return null;
        }

        return (narrowed[0], string.IsNullOrWhiteSpace(fallbackReason) ? "Signalement en jeu" : fallbackReason);
    }

    private static string? TryGetSteamId64(CCSPlayerController player)
    {
        try
        {
            return player.AuthorizedSteamID?.SteamId64.ToString();
        }
        catch
        {
            return null;
        }
    }

    private void PollTimer()
    {
        if (!IsConfigured())
        {
            return;
        }

        if (Interlocked.Exchange(ref _pollInFlight, 1) == 1)
        {
            return;
        }

        Server.NextWorldUpdate(() =>
        {
            BridgeHeartbeatRequest heartbeat;
            try
            {
                heartbeat = BuildHeartbeatRequest(null);
            }
            catch (Exception ex)
            {
                Logger.LogWarning(ex, "ReadyUp bridge heartbeat snapshot failed");
                Interlocked.Exchange(ref _pollInFlight, 0);
                return;
            }

            _ = Task.Run(async () =>
            {
                try
                {
                    await SendHeartbeatAsync(heartbeat);
                    var commands = await PullPendingCommandsAsync();
                    foreach (var command in commands)
                    {
                        DispatchCommand(command);
                    }
                }
                catch (Exception ex)
                {
                    Logger.LogWarning(ex, "ReadyUp bridge poll failed");
                }
                finally
                {
                    Interlocked.Exchange(ref _pollInFlight, 0);
                }
            });
        });
    }

    private void DispatchCommand(BridgePendingCommand command)
    {
        if (_config.VerboseLogging)
        {
            Logger.LogInformation("ReadyUp bridge dispatching command {CommandId}: {Command}", command.Id, command.Command);
        }

        Server.NextWorldUpdate(() =>
        {
            try
            {
                Server.ExecuteCommand(command.Command);
                _ = Task.Run(() => ReportResultAsync(command.Id, "completed", "Command executed locally by ReadyUp bridge"));
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "ReadyUp bridge command failed: {CommandId}", command.Id);
                _ = Task.Run(() => ReportResultAsync(command.Id, "failed", ex.Message));
            }
        });
    }

    private BridgeHeartbeatRequest BuildHeartbeatRequest(string? status)
    {
        return new BridgeHeartbeatRequest
        {
            Status = status,
            CurrentMap = string.IsNullOrWhiteSpace(_currentMap) ? Server.MapName : _currentMap,
            PlayerCount = Utilities.GetPlayers().Count(p => p is { IsValid: true, IsBot: false }),
            PluginVersion = ModuleVersion,
        };
    }

    private async Task SendHeartbeatAsync(BridgeHeartbeatRequest request)
    {
        await PostJsonAsync("/api/cs2/bridge/heartbeat", request);
    }

    private async Task SubmitPlayerReportAsync(BridgePlayerReportRequest request)
    {
        await PostJsonAsync("/api/matches/bridge/report", request);
    }

    private async Task<List<BridgePendingCommand>> PullPendingCommandsAsync()
    {
        var response = await _httpClient.GetAsync("/api/cs2/bridge/pending?limit=10");
        response.EnsureSuccessStatusCode();
        var stream = await response.Content.ReadAsStreamAsync();
        return await JsonSerializer.DeserializeAsync<List<BridgePendingCommand>>(stream, _jsonOptions) ?? new List<BridgePendingCommand>();
    }

    private async Task ReportResultAsync(string commandId, string status, string? output)
    {
        await PostJsonAsync($"/api/cs2/bridge/commands/{commandId}/result", new BridgeCommandResultRequest
        {
            Status = status,
            Output = output,
        });
    }

    private async Task PostJsonAsync(string path, object payload)
    {
        var body = JsonSerializer.Serialize(payload, _jsonOptions);
        using var response = await _httpClient.PostAsync(
            path,
            new StringContent(body, Encoding.UTF8, "application/json"));
        response.EnsureSuccessStatusCode();
    }
}
