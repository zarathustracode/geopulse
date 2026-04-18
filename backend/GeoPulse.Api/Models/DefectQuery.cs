namespace GeoPulse.Api.Models;

public sealed record DefectQuery(
    DefectType? Type,
    DefectStatus? Status,
    double? MinConfidence,
    double? MinLongitude,
    double? MinLatitude,
    double? MaxLongitude,
    double? MaxLatitude)
{
    public bool HasBoundingBox =>
        MinLongitude.HasValue && MinLatitude.HasValue &&
        MaxLongitude.HasValue && MaxLatitude.HasValue;
}
