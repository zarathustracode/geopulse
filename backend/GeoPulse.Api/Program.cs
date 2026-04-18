using System.Text.Json.Serialization;
using GeoPulse.Api.Data;
using GeoPulse.Api.Repositories;

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
builder.Services.AddSingleton<IDefectRepository>(_ =>
    new InMemoryDefectRepository(SeedData.Generate()));

const string DevCorsPolicy = "DevCors";
builder.Services.AddCors(options =>
{
    options.AddPolicy(DevCorsPolicy, policy => policy
        .WithOrigins(
            "http://localhost:5173",
            "http://localhost:3000")
        .AllowAnyHeader()
        .AllowAnyMethod());
});

var app = builder.Build();

app.UseCors(DevCorsPolicy);

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
