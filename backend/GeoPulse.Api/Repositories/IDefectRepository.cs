using GeoPulse.Api.Models;

namespace GeoPulse.Api.Repositories;

public interface IDefectRepository
{
    Task<IReadOnlyList<Defect>> QueryAsync(DefectQuery query, CancellationToken cancellationToken = default);
    Task<Defect?> GetAsync(Guid id, CancellationToken cancellationToken = default);
    Task<Defect?> UpdateStatusAsync(Guid id, DefectStatus status, CancellationToken cancellationToken = default);
}
