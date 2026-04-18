import { useMemo, useState } from 'react';
import { DefectMap } from './components/DefectMap';
import { DefectDetails } from './components/DefectDetails';
import { FilterPanel } from './components/FilterPanel';
import { useDefects } from './hooks/useDefects';
import type { BoundingBox, DefectFilters } from './api/types';

export default function App() {
  const [filters, setFilters] = useState<DefectFilters>({});
  const [viewport, setViewport] = useState<BoundingBox | null>(null);
  const [useBbox, setUseBbox] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // When bbox filtering is off we return `filters` by reference so viewport
  // changes don't trigger refetches.
  const effectiveFilters = useMemo<DefectFilters>(
    () => (useBbox && viewport ? { ...filters, bbox: viewport } : filters),
    [filters, useBbox, viewport],
  );

  const { defects, loading, error, updateStatus } = useDefects(effectiveFilters);
  const selected = defects.find((d) => d.id === selectedId) ?? null;

  return (
    <div className="h-full w-full flex overflow-hidden">
      <FilterPanel
        filters={filters}
        onChange={setFilters}
        totalCount={defects.length}
        loading={loading}
        useBbox={useBbox}
        onToggleBbox={setUseBbox}
      />

      <main className="flex-1 relative flex">
        <DefectMap
          defects={defects}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onViewportChange={setViewport}
        />

        {error && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-rose-600 text-white px-4 py-2 rounded-md shadow-lg text-sm">
            {error}
          </div>
        )}

        {selected && (
          <DefectDetails
            defect={selected}
            onClose={() => setSelectedId(null)}
            onUpdateStatus={async (id, status) => {
              await updateStatus(id, status);
            }}
          />
        )}
      </main>
    </div>
  );
}
