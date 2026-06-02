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
            var modelName = report.Model ?? "torchvision.maskrcnn_resnet50_fpn.COCO_V1";
            var reportDir = Path.GetDirectoryName(Path.GetFullPath(path));
            var reportSourceImage = NormaliseSourceImagePath(report.SourceImage, reportDir);

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
                    Source = DefectSource.Model,
                    ModelName = modelName,
                    ModelLabel = d.Label,
                    ModelScore = d.Score,
                    Bbox = d.Bbox,
                    SourceImage = NormaliseSourceImagePath(d.SourceImage, reportDir) ?? reportSourceImage,
                })
                .ToList();
        }
        catch (Exception)
        {
            return Array.Empty<Defect>();
        }
    }

    // The CLI writes source_image as either an absolute path or one relative
    // to the report. The API exposes the ml/ directory under /ml/, so we
    // convert to a web path the browser can load.
    private static string? NormaliseSourceImagePath(string? raw, string? reportDir)
    {
        if (string.IsNullOrWhiteSpace(raw)) return null;
        var trimmed = raw.Replace('\\', '/').TrimStart('/');
        if (Path.IsPathRooted(raw) && reportDir is not null)
        {
            var rel = Path.GetRelativePath(reportDir, raw).Replace('\\', '/');
            return $"/ml/{rel}";
        }
        return $"/ml/{trimmed}";
    }

    private static DefectType MapLabel(string label) => label switch
    {
        // COCO Mask R-CNN (legacy / sample run)
        "stop sign" => DefectType.Sign,
        "traffic light" => DefectType.TrafficLight,
        "fire hydrant" => DefectType.Hydrant,
        // RDD2022 YOLO11m baseline
        "D00" => DefectType.LongitudinalCrack,
        "D10" => DefectType.TransverseCrack,
        "D20" => DefectType.AlligatorCrack,
        "D40" => DefectType.Pothole,
        _ => DefectType.Damage,
    };

    // Bucketing raw scores into severity is a presentation choice (these scores
    // aren't calibrated probabilities). Thresholds chosen so the top-confidence
    // detections in the RDD2022 YOLO baseline land as "high".
    private static Severity SeverityFromScore(double score) => score switch
    {
        >= 0.70 => Severity.High,
        >= 0.50 => Severity.Medium,
        _ => Severity.Low,
    };

    private sealed record MlReport(
        [property: JsonPropertyName("source_image")] string? SourceImage,
        [property: JsonPropertyName("model")] string? Model,
        [property: JsonPropertyName("generated_at")] DateTime? GeneratedAt,
        [property: JsonPropertyName("detections")] List<MlDetection> Detections);

    private sealed record MlDetection(
        [property: JsonPropertyName("label")] string Label,
        [property: JsonPropertyName("score")] double Score,
        [property: JsonPropertyName("bbox")] double[]? Bbox,
        [property: JsonPropertyName("status")] string Status,
        [property: JsonPropertyName("latitude")] double? Latitude,
        [property: JsonPropertyName("longitude")] double? Longitude,
        [property: JsonPropertyName("source_image")] string? SourceImage = null);
}
