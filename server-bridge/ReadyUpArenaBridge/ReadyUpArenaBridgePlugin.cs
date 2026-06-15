using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
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

        AddTimer(Math.Max(2, _config.PollIntervalSeconds), PollTimer, TimerFlags.REPEAT);
        _ = Task.Run(() => SendHeartbeatAsync("online"));
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

        _ = Task.Run(async () =>
        {
            try
            {
                await SendHeartbeatAsync(null);
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

    private async Task SendHeartbeatAsync(string? status)
    {
        var request = new BridgeHeartbeatRequest
        {
            Status = status,
            CurrentMap = string.IsNullOrWhiteSpace(_currentMap) ? Server.MapName : _currentMap,
            PlayerCount = Utilities.GetPlayers().Count(p => p is { IsValid: true, IsBot: false }),
            PluginVersion = ModuleVersion,
        };
        await PostJsonAsync("/api/cs2/bridge/heartbeat", request);
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
