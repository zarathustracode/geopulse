using System.Text.Json.Serialization;
using GeoPulse.Api.Data;
using GeoPulse.Api.Repositories;
using Microsoft.Extensions.FileProviders;

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddControllers()
    .AddJsonOptions(options =>
    {
        options.JsonSerializerOptions.Converters.Add(
            new JsonStringEnumConverter(System.Text.Json.JsonNamingPolicy.CamelCase));
        options.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
    });

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((document, _, _) =>
    {
        document.Info.Title = "GeoPulse API";
        document.Info.Version = "v1";
        document.Info.Description = "REST API for visualizing and reviewing infrastructure defects.";
        return Task.CompletedTask;
    });
});

// Repository is registered as a singleton so the in-memory store survives across requests.
// Swap this registration for a PostGIS-backed implementation when moving off in-memory storage.
// On startup we also splice in any detections emitted by the geopulse-ml Python pipeline,
// which is how the PyTorch side feeds real inference output into the reviewer UI.
var mlReportPath = builder.Configuration["MlReportPath"]
    ?? Path.Combine(builder.Environment.ContentRootPath, "..", "..", "ml", "report.json");

builder.Services.AddSingleton<IDefectRepository>(sp =>
{
    var mlDetections = MlReportLoader.LoadOrEmpty(mlReportPath);
    sp.GetRequiredService<ILoggerFactory>()
        .CreateLogger("MlReport")
        .LogInformation("Loaded {Count} detections from {Path}", mlDetections.Count, mlReportPath);
    return new InMemoryDefectRepository(mlDetections.ToList());
});

const string DevCorsPolicy = "DevCors";
builder.Services.AddCors(options =>
{
    options.AddPolicy(DevCorsPolicy, policy => policy
        .WithOrigins(
            "http://localhost:5173",
            "http://localhost:3000",
            "https://geopulse.igaspar.com")
        .AllowAnyHeader()
        .AllowAnyMethod());
});

var app = builder.Build();

app.UseCors(DevCorsPolicy);

// Serve the ml/ directory (source images, annotated previews) so the
// reviewer UI can display what the model actually saw. Mounted under /ml/.
var mlDirectory = Path.GetFullPath(Path.Combine(builder.Environment.ContentRootPath, "..", "..", "ml"));
if (Directory.Exists(mlDirectory))
{
    app.UseStaticFiles(new StaticFileOptions
    {
        FileProvider = new PhysicalFileProvider(mlDirectory),
        RequestPath = "/ml",
    });
}

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/openapi/v1.json", "GeoPulse API v1");
        options.RoutePrefix = "swagger";
    });
}

app.MapControllers();
app.MapGet("/", () => Results.Redirect("/swagger"));

app.Run();
