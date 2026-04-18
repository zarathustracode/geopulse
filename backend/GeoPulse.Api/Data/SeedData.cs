using GeoPulse.Api.Models;

namespace GeoPulse.Api.Data;

/// <summary>
/// Reproducible seed data centred on Belgrade (44.8125, 20.4612).
/// Replace this with a DbContext-backed source once PostGIS is wired in.
/// </summary>
public static class SeedData
{
    public static List<Defect> Generate()
    {
        var random = new Random(42);
        var types = new[] { DefectType.Crack, DefectType.Pothole, DefectType.Damage };
        var severities = new[] { Severity.Low, Severity.Medium, Severity.High };
        var statuses = new[] { DefectStatus.New, DefectStatus.New, DefectStatus.New,
                               DefectStatus.Confirmed, DefectStatus.Rejected };

        const double centerLat = 44.8125;
        const double centerLng = 20.4612;
        var now = DateTime.UtcNow;

        var defects = new List<Defect>(capacity: 30);
        for (var i = 0; i < 30; i++)
        {
            defects.Add(new Defect
            {
                Id = Guid.NewGuid(),
                Type = types[random.Next(types.Length)],
                Confidence = Math.Round(0.55 + random.NextDouble() * 0.45, 2),
                Severity = severities[random.Next(severities.Length)],
                Status = statuses[random.Next(statuses.Length)],
                Latitude = Math.Round(centerLat + (random.NextDouble() - 0.5) * 0.10, 6),
                Longitude = Math.Round(centerLng + (random.NextDouble() - 0.5) * 0.15, 6),
                Timestamp = now.AddHours(-random.Next(0, 24 * 30))
            });
        }

        return defects;
    }
}
