using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

using Rhino;

namespace RhMcp;

internal sealed class McpServer : IDisposable
{
    private static readonly string DebugLogPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "RhinoMCP",
        "server-debug.log");

    private WebApplication? _app;
    private CancellationTokenSource? _cts;

    public bool HasStarted => _app is not null;

    private static void LogDebug(string message)
    {
        try
        {
            var directory = Path.GetDirectoryName(DebugLogPath);
            if (!string.IsNullOrEmpty(directory))
                Directory.CreateDirectory(directory);

            File.AppendAllText(DebugLogPath, $"[{DateTime.Now:O}] {message}{Environment.NewLine}");
        }
        catch
        {
            // Avoid letting debug logging break plugin startup.
        }
    }

    public bool Start()
    {
        if (HasStarted) return true;
        try
        {
            LogDebug($"Start() invoked on port {RhMcpHost.Port}.");
            var builder = WebApplication.CreateSlimBuilder();
            builder.Logging.ClearProviders();
            builder.Services.Configure<KestrelServerOptions>(o => o.ListenLocalhost(RhMcpHost.Port));

            builder.Services
                .AddMcpServer(o =>
                {
                    o.ServerInfo = new() { Name = "rhino-mcp", Version = "0.1.0" };
                })
                .WithHttpTransport(o => o.Stateless = true)
                .WithToolsFromAssembly(typeof(McpServer).Assembly);

            _app = builder.Build();
            _app.MapMcp();

            _cts = new CancellationTokenSource();
            _ = _app.RunAsync(_cts.Token);

            LogDebug($"RunAsync scheduled successfully on port {RhMcpHost.Port}.");
            RhinoApp.WriteLine($"[Rhino MCP] MCP server currently running on http://localhost:{RhMcpHost.Port}/");
            return true;
        }
        catch (Exception ex)
        {
            LogDebug($"Start() failed: {ex}");
            RhinoApp.WriteLine($"[Rhino MCP] Failed to start: {ex.Message}");
            _app = null;
            return false;
        }
    }

    public void Stop()
    {
        try { _cts?.Cancel(); } catch { }
        try { _app?.StopAsync().GetAwaiter().GetResult(); } catch { }
        _app = null;
    }

    public void Dispose() => Stop();
}
