namespace ReadyUpArenaBridge;

public sealed class ReadyUpArenaBridgeConfig
{
    public string BackendBaseUrl { get; set; } = "";
    public string BridgeToken { get; set; } = "";
    public int PollIntervalSeconds { get; set; } = 5;
    public bool VerboseLogging { get; set; } = false;
}

internal sealed class BridgeHeartbeatRequest
{
    public string? Status { get; set; }
    public string? CurrentMap { get; set; }
    public int? PlayerCount { get; set; }
    public string? PluginVersion { get; set; }
}

internal sealed class BridgePendingCommand
{
    public string Id { get; set; } = "";
    public string Kind { get; set; } = "";
    public string Command { get; set; } = "";
    public Dictionary<string, object>? Metadata { get; set; }
    public string CreatedAt { get; set; } = "";
}

internal sealed class BridgeCommandResultRequest
{
    public string Status { get; set; } = "completed";
    public string? Output { get; set; }
}
