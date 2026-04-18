using System.Collections.Concurrent;
using GeoPulse.Api.Models;

namespace GeoPulse.Api.Repositories;

public sealed class InMemoryDefectRepository : IDefectRepository
{
    private readonly ConcurrentDictionary<Guid, Defect> _store;

    public InMemoryDefectRepository(IEnumerable<Defect> seed)
    {
        _store = new ConcurrentDictionary<Guid, Defect>(
            seed.Select(d => new KeyValuePair<Guid, Defect>(d.Id, d)));
    }

    public Task<IReadOnlyList<Defect>> QueryAsync(DefectQuery query, CancellationToken cancellationToken = default)
    {
        IEnumerable<Defect> results = _store.Values;

        if (query.Type is { } type)
            results = results.Where(d => d.Type == type);

        if (query.Status is { } status)
            results = results.Where(d => d.Status == status);

        if (query.MinConfidence is { } min)
            results = results.Where(d => d.Confidence >= min);

        if (query.HasBoundingBox)
        {
            results = results.Where(d =>
                d.Longitude >= query.MinLongitude &&
                d.Longitude <= query.MaxLongitude &&
                d.Latitude >= query.MinLatitude &&
                d.Latitude <= query.MaxLatitude);
        }

        return Task.FromResult<IReadOnlyList<Defect>>(
            results.OrderByDescending(d => d.Timestamp).ToList());
    }

    public Task<Defect?> GetAsync(Guid id, CancellationToken cancellationToken = default)
    {
        _store.TryGetValue(id, out var defect);
        return Task.FromResult(defect);
    }

    public Task<Defect?> UpdateStatusAsync(Guid id, DefectStatus status, CancellationToken cancellationToken = default)
    {
        if (!_store.TryGetValue(id, out var existing))
            return Task.FromResult<Defect?>(null);

        existing.Status = status;
        return Task.FromResult<Defect?>(existing);
    }
}
