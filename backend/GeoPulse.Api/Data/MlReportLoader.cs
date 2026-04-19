using System.Text.Json;
using System.Text.Json.Serialization;
using GeoPulse.Api.Models;

namespace GeoPulse.Api.Data;

/// <summary>
/// Reads <c>report.json</c> emitted by <c>geopulse-ml</c> and converts accepted
/// detections into in-memory defects. The report is the demo's bridge from
/// PyTorch inference to the reviewer UI — a real pipeline would instead
/// project each bounding box through camera pose + GNSS/IMU to recover lat/lng.
/// </summary>
public static class MlReportLoader
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    public static IReadOnlyList<Defect> LoadOrEmpty(string path)
    {
        if (!File.Exists(path)) return Array.Empty<Defect>();

        try
        {
            var report = JsonSerializer.Deserialize<MlReport>(File.ReadAllText(path), Options);
            if (report?.Detections is null) return Array.Empty<Defect>();

            var timestamp = report.GeneratedAt ?? DateTime.UtcNow;
            return report.Detections
                .Where(d => d.Status is "accepted" or "needs_review")
                .Where(d => d.Latitude.HasValue && d.Longitude.HasValue)
                .Select(d => new Defect
                {
                    Id = Guid.NewGuid(),
                    Type = MapLabel(d.Label),
                    Confidence = Math.Round(d.Score, 3),
                    Severity = SeverityFromScore(d.Score),
                    Status = d.Status == "needs_review" ? DefectStatus.New : DefectStatus.Confirmed,
                    Latitude = d.Latitude!.Value,
                    Longitude = d.Longitude!.Value,
                    Timestamp = timestamp,
                })
                .ToList();
        }
        catch (Exception)
        {
            return Array.Empty<Defect>();
        }
    }

    private static DefectType MapLabel(string label) => label switch
    {
        "stop sign" => DefectType.Sign,
        "traffic light" => DefectType.TrafficLight,
        "fire hydrant" => DefectType.Hydrant,
        _ => DefectType.Damage,
    };

    // Pretrained Mask R-CNN scores are not probability-calibrated; bucketing
    // them as severity is a presentation choice, not a claim about risk.
    private static Severity SeverityFromScore(double score) => score switch
    {
        >= 0.85 => Severity.High,
        >= 0.65 => Severity.Medium,
        _ => Severity.Low,
    };

    private sealed record MlReport(
        [property: JsonPropertyName("generated_at")] DateTime? GeneratedAt,
        [property: JsonPropertyName("detections")] List<MlDetection> Detections);

    private sealed record MlDetection(
        [property: JsonPropertyName("label")] string Label,
        [property: JsonPropertyName("score")] double Score,
        [property: JsonPropertyName("status")] string Status,
        [property: JsonPropertyName("latitude")] double? Latitude,
        [property: JsonPropertyName("longitude")] double? Longitude);
}
