import { DEFECT_TYPE_LABELS, type Defect, type DefectStatus } from '../api/types';

interface DefectDetailsProps {
  defect: Defect;
  onClose: () => void;
  onUpdateStatus: (id: string, status: DefectStatus) => Promise<void>;
}

const SEVERITY_COLORS: Record<Defect['severity'], string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-rose-100 text-rose-700',
};

const STATUS_COLORS: Record<DefectStatus, string> = {
  new: 'bg-slate-100 text-slate-700',
  confirmed: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-rose-100 text-rose-700',
};

export function DefectDetails({ defect, onClose, onUpdateStatus }: DefectDetailsProps) {
  return (
    <aside className="w-96 shrink-0 border-l border-slate-200 bg-white flex flex-col shadow-lg">
      <div className="px-6 py-5 border-b border-slate-200 flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Defect
          </p>
          <h2 className="text-lg font-semibold mt-1">{DEFECT_TYPE_LABELS[defect.type]}</h2>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">{defect.id.slice(0, 8)}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="text-slate-400 hover:text-slate-700 text-xl leading-none"
        >
          ×
        </button>
      </div>

      <div className="px-6 py-5 space-y-5 flex-1 overflow-y-auto">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <Field label="Severity">
            <span className={`${SEVERITY_COLORS[defect.severity]} px-2 py-0.5 rounded text-xs font-medium capitalize`}>
              {defect.severity}
            </span>
          </Field>
          <Field label="Status">
            <span className={`${STATUS_COLORS[defect.status]} px-2 py-0.5 rounded text-xs font-medium capitalize`}>
              {defect.status}
            </span>
          </Field>
          <Field label="Confidence">
            <span className="font-medium tabular-nums">
              {(defect.confidence * 100).toFixed(0)}%
            </span>
          </Field>
          <Field label="Detected">
            <span className="text-slate-700">
              {new Date(defect.timestamp).toLocaleString()}
            </span>
          </Field>
          <Field label="Latitude">
            <span className="font-mono text-xs">{defect.latitude.toFixed(6)}</span>
          </Field>
          <Field label="Longitude">
            <span className="font-mono text-xs">{defect.longitude.toFixed(6)}</span>
          </Field>
        </dl>

        <div className="rounded-lg bg-slate-50 p-4 text-xs text-slate-600">
          Review this automated detection. Confirming flags it for maintenance;
          rejecting marks it as a false positive.
        </div>
      </div>

      <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex gap-2">
        <button
          type="button"
          onClick={() => onUpdateStatus(defect.id, 'confirmed')}
          disabled={defect.status === 'confirmed'}
          className="flex-1 bg-emerald-600 text-white rounded-md py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Confirm
        </button>
        <button
          type="button"
          onClick={() => onUpdateStatus(defect.id, 'rejected')}
          disabled={defect.status === 'rejected'}
          className="flex-1 bg-rose-600 text-white rounded-md py-2 text-sm font-medium hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Reject
        </button>
      </div>
    </aside>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}
