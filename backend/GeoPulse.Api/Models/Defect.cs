namespace GeoPulse.Api.Models;

public enum DefectType
{
    LongitudinalCrack,
    TransverseCrack,
    AlligatorCrack,
    Pothole,
    Crack,
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

public enum DefectSource
{
    Seed,
    Model
}

public enum MatchStatus
{
    Unknown,            // no ground-truth label available (production case)
    TruePositive,       // model prediction matched a labelled box at IoU ≥ 0.5
    FalsePositive,      // model prediction with no matching label
    FalseNegative       // labelled box the model failed to propose
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
    public DefectSource Source { get; init; } = DefectSource.Seed;

    // ML metadata — populated when Source = Model. Raw Mask R-CNN output,
    // reported verbatim so the reviewer sees the model's claim (not a
    // bucketed severity). Scores are uncalibrated softmax, not probabilities.
    public string? ModelName { get; init; }
    public string? ModelLabel { get; init; }
    public double? ModelScore { get; init; }
    public double? CalibratedScore { get; init; }
    public double[]? Bbox { get; init; }
    public string? SourceImage { get; init; }
    public MatchStatus MatchStatus { get; init; } = MatchStatus.Unknown;
}
