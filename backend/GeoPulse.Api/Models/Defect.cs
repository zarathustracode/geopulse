namespace GeoPulse.Api.Models;

public enum DefectType
{
    Crack,
    Pothole,
    Damage,
    Sign,
    TrafficLight,
    Hydrant
}

public enum Severity
{
    Low,
    Medium,
    High
}

public enum DefectStatus
{
    New,
    Confirmed,
    Rejected
}

public sealed class Defect
{
    public required Guid Id { get; init; }
    public required DefectType Type { get; init; }
    public required double Confidence { get; init; }
    public required Severity Severity { get; init; }
    public required DefectStatus Status { get; set; }
    public required double Latitude { get; init; }
    public required double Longitude { get; init; }
    public required DateTime Timestamp { get; init; }
}
