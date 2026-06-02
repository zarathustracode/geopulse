import type { DefectFilters, DefectStatus, DefectType } from '../api/types';

// Only show types the RDD2022 YOLO baseline actually produces.
const ACTIVE_TYPES: DefectType[] = [
  'longitudinalCrack',
  'transverseCrack',
  'alligatorCrack',
  'pothole',
];
const TYPE_SHORT_LABELS: Record<DefectType, string> = {
  longitudinalCrack: 'D00',
  transverseCrack: 'D10',
  alligatorCrack: 'D20',
  pothole: 'D40',
  crack: 'Crack',
  damage: 'Damage',
  sign: 'Sign',
  trafficLight: 'Traffic light',
  hydrant: 'Hydrant',
};
const TYPES: Array<{ value: DefectType; label: string }> = ACTIVE_TYPES.map(
  (value) => ({ value, label: TYPE_SHORT_LABELS[value] }),
);

const STATUSES: Array<{ value: DefectStatus; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
];

interface FilterPanelProps {
  filters: DefectFilters;
  onChange: (filters: DefectFilters) => void;
  totalCount: number;
  modelCount: number;
  loading: boolean;
  useBbox: boolean;
  onToggleBbox: (next: boolean) => void;
}

export function FilterPanel({
  filters,
  onChange,
  totalCount,
  modelCount,
  loading,
  useBbox,
  onToggleBbox,
}: FilterPanelProps) {
  const confidence = filters.minConfidence ?? 0;

  return (
    <aside className="w-80 shrink-0 border-r border-slate-200 bg-white flex flex-col">
      <div className="px-6 py-5 border-b border-slate-200">
        <h1 className="text-xl font-semibold tracking-tight">GeoPulse</h1>
        <p className="text-sm text-slate-500 mt-1">Defect review console</p>
      </div>

      <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Object detection
        </p>
        <p className="text-sm font-medium text-slate-800 mt-1 font-mono">
          YOLO11m · RDD2022 baseline
        </p>
        <p className="text-xs text-slate-500 mt-1">
          4-class · cracks (D00/D10/D20) + pothole (D40)
        </p>
        <p className="text-xs text-slate-500 mt-1">
          mAP@0.5 = 0.636 · 11.3 ms / image (A10G)
        </p>
        <p className="text-xs text-slate-400 mt-2 italic leading-snug">
          Per-country range 0.89 (China) → 0.38 (India). Scores are raw — uncalibrated.
        </p>
      </div>

      <div className="px-6 py-5 space-y-6 flex-1 overflow-y-auto">
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Type
          </h2>
          <div className="flex flex-wrap gap-2">
            <FilterChip
              active={!filters.type}
              onClick={() => onChange({ ...filters, type: undefined })}
            >
              All
            </FilterChip>
            {TYPES.map((t) => (
              <FilterChip
                key={t.value}
                active={filters.type === t.value}
                onClick={() => onChange({ ...filters, type: t.value })}
              >
                {t.label}
              </FilterChip>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Status
          </h2>
          <div className="flex flex-wrap gap-2">
            <FilterChip
              active={!filters.status}
              onClick={() => onChange({ ...filters, status: undefined })}
            >
              All
            </FilterChip>
            {STATUSES.map((s) => (
              <FilterChip
                key={s.value}
                active={filters.status === s.value}
                onClick={() => onChange({ ...filters, status: s.value })}
              >
                {s.label}
              </FilterChip>
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Min confidence
            </h2>
            <span className="text-sm font-medium text-slate-700 tabular-nums">
              {confidence.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={confidence}
            onChange={(e) =>
              onChange({
                ...filters,
                minConfidence: Number(e.target.value) || undefined,
              })
            }
            className="w-full accent-brand-600"
          />
        </section>

        <section>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={useBbox}
              onChange={(e) => onToggleBbox(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 accent-brand-600"
            />
            Filter to map viewport
          </label>
        </section>
      </div>

      <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 text-sm text-slate-600 flex items-center justify-between">
        <span>{loading ? 'Loading…' : `${totalCount} defects`}</span>
        {modelCount > 0 && (
          <span className="text-xs font-medium text-sky-700 bg-sky-100 px-2 py-0.5 rounded">
            {modelCount} from model
          </span>
        )}
      </div>
    </aside>
  );
}

function FilterChip({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? 'px-3 py-1.5 rounded-full text-sm font-medium bg-brand-600 text-white'
          : 'px-3 py-1.5 rounded-full text-sm font-medium bg-slate-100 text-slate-700 hover:bg-slate-200'
      }
    >
      {children}
    </button>
  );
}
