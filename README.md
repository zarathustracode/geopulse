# GeoPulse

A minimal full-stack GIS prototype for reviewing infrastructure defects on an
interactive map. Simulates a GeoAI workflow where automated detections
(potholes, cracks, surface damage) are visualised and triaged by a human
reviewer.

## Stack

| Layer    | Tech                                                      |
|----------|-----------------------------------------------------------|
| Backend  | ASP.NET Core (.NET 10), C#, built-in OpenAPI, Swagger UI  |
| Frontend | React + TypeScript, Vite, Tailwind CSS, MapLibre GL JS    |
| Storage  | In-memory repository (swap-in PostGIS ready)              |
| Infra    | Docker Compose: `db` (PostGIS) + `api` + `web`            |

## Project layout

```
GeoPulse/
├─ backend/
│  ├─ GeoPulse.Api/
│  │  ├─ Controllers/         REST endpoints
│  │  ├─ Models/              Defect, enums, DTOs
│  │  ├─ Repositories/        IDefectRepository + in-memory impl
│  │  ├─ Data/SeedData.cs     30 reproducible defects around Burgdorf
│  │  └─ Program.cs           DI, OpenAPI, Swagger UI, CORS
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ api/                 Typed HTTP client + openapi-ts regen target
│  │  ├─ components/          DefectMap, FilterPanel, DefectDetails
│  │  ├─ hooks/useDefects.ts  fetch + mutate
│  │  └─ App.tsx              3-pane layout
│  ├─ Dockerfile + nginx.conf
│  └─ vite.config.ts          proxies /api → :5080
└─ docker-compose.yml
```

## Run locally

### 1. Backend (http://localhost:5080)

```bash
cd backend/GeoPulse.Api
dotnet run
```

- Swagger UI: <http://localhost:5080/swagger>
- OpenAPI spec: <http://localhost:5080/openapi/v1.json>

### 2. Frontend (http://localhost:5173)

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to the backend, so no extra config is needed.

### 3. (Optional) regenerate the typed API client

While the backend is running:

```bash
cd frontend
npm run generate-api
```

This writes a fetch-based client into `src/api/generated/` via
[`@hey-api/openapi-ts`](https://heyapi.dev). The hand-written
`src/api/client.ts` exists so the app works out of the box — wire the
generated client in once you prefer to drive types from the spec.

### 4. (Optional) run everything with Docker

```bash
docker compose up --build
```

- Web: <http://localhost:8080>
- API: <http://localhost:5080/swagger>
- PostGIS: `localhost:5432` (user/pass/db = `geopulse`)

The API currently ignores Postgres — the connection string is pre-wired for
when you swap `InMemoryDefectRepository` for a PostGIS-backed one.

## API

| Method | Path                           | Description                               |
|--------|--------------------------------|-------------------------------------------|
| GET    | `/api/defects`                 | List defects (filters below)              |
| GET    | `/api/defects/{id}`            | Fetch one defect                          |
| PATCH  | `/api/defects/{id}/status`     | `{ "status": "confirmed" \| "rejected" }` |

**Query parameters on `GET /api/defects`:**

- `type` — `crack` \| `pothole` \| `damage`
- `status` — `new` \| `confirmed` \| `rejected`
- `minConfidence` — `0.0`–`1.0`
- `minLongitude`, `minLatitude`, `maxLongitude`, `maxLatitude` — viewport bbox

## Architecture notes

**Backend — kept intentionally thin.** Controllers depend on
`IDefectRepository`; the current implementation wraps a
`ConcurrentDictionary<Guid, Defect>`. Moving to PostGIS is a one-file change:

1. Add `Npgsql.EntityFrameworkCore.PostgreSQL` + `NetTopologySuite` packages.
2. Write `PostgresDefectRepository : IDefectRepository` storing defects with a
   `Point` geography column; the bounding-box filter becomes a
   `ST_Within(location, ST_MakeEnvelope(...))` predicate.
3. Swap the DI registration in `Program.cs` — the controllers, DTOs, and the
   entire frontend stay untouched.

The `Defect` model uses latitude/longitude primitives rather than a geo type
so the in-memory path stays dependency-free; the PostGIS impl is free to map
those to a NetTopologySuite `Point` on the way in and out.

**Frontend — three-pane dashboard.** `App.tsx` owns filter state; a single
`useDefects(filters)` hook turns filter changes into a refetch and exposes a
`updateStatus` mutation that patches state optimistically. `DefectMap`
renders defects as a clustered GeoJSON source on an OSM raster style — no
API key required. The right-hand `DefectDetails` panel is driven purely by
the selected id, so keyboard / deep-link selection is straightforward to add.

**Bounding-box filter.** The map emits its viewport on every `moveend`; when
the "Filter to map viewport" checkbox is on, those bounds flow into the
filters and the server returns only defects inside the box. Clustering is
handled client-side by MapLibre's GeoJSON cluster options.

## What's intentionally left out

- **Auth** — this is a single-tenant demo.
- **Persistence** — in-memory by design; see the PostGIS notes above.
- **Pagination** — 30 seed points don't need it; add `?skip`/`?take` on the
  server and infinite scroll on the client when the data grows.
- **Tests** — the MVP ships without them; the repository split and the thin
  controllers make both unit and integration tests easy to bolt on later.
