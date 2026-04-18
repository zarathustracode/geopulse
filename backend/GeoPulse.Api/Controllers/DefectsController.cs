using GeoPulse.Api.Models;
using GeoPulse.Api.Repositories;
using Microsoft.AspNetCore.Mvc;

namespace GeoPulse.Api.Controllers;

[ApiController]
[Route("api/defects")]
[Produces("application/json")]
public sealed class DefectsController : ControllerBase
{
    private readonly IDefectRepository _repository;

    public DefectsController(IDefectRepository repository) => _repository = repository;

    /// <summary>List defects, optionally filtered by type, status, confidence, or bounding box.</summary>
    [HttpGet]
    [EndpointSummary("List defects")]
    [ProducesResponseType(typeof(IReadOnlyList<Defect>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IReadOnlyList<Defect>>> List(
        [FromQuery] DefectType? type,
        [FromQuery] DefectStatus? status,
        [FromQuery] double? minConfidence,
        [FromQuery] double? minLongitude,
        [FromQuery] double? minLatitude,
        [FromQuery] double? maxLongitude,
        [FromQuery] double? maxLatitude,
        CancellationToken cancellationToken)
    {
        var query = new DefectQuery(type, status, minConfidence,
            minLongitude, minLatitude, maxLongitude, maxLatitude);
        var defects = await _repository.QueryAsync(query, cancellationToken);
        return Ok(defects);
    }

    /// <summary>Get a defect by id.</summary>
    [HttpGet("{id:guid}")]
    [EndpointSummary("Get defect")]
    [ProducesResponseType(typeof(Defect), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<Defect>> Get(Guid id, CancellationToken cancellationToken)
    {
        var defect = await _repository.GetAsync(id, cancellationToken);
        return defect is null ? NotFound() : Ok(defect);
    }

    /// <summary>Update the review status (confirm / reject) of a defect.</summary>
    [HttpPatch("{id:guid}/status")]
    [EndpointSummary("Update defect status")]
    [ProducesResponseType(typeof(Defect), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<Defect>> UpdateStatus(
        Guid id,
        [FromBody] UpdateStatusRequest request,
        CancellationToken cancellationToken)
    {
        var updated = await _repository.UpdateStatusAsync(id, request.Status, cancellationToken);
        return updated is null ? NotFound() : Ok(updated);
    }
}
