import { useEffect, useState } from 'react';
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
  const isModel = defect.source === 'model';

  return (
    <aside className="w-96 shrink-0 border-l border-slate-200 bg-white flex flex-col shadow-lg">
      <div className="px-6 py-5 border-b border-slate-200 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Defect
            </p>
            {isModel ? (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-sky-600 text-white px-1.5 py-0.5 rounded">
                ML
              </span>
            ) : (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded">
                Seed
              </span>
            )}
          </div>
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

        {isModel && <ModelSection defect={defect} />}

        <div className="rounded-lg bg-slate-50 p-4 text-xs text-slate-600">
          {isModel
            ? 'Automatic detection from Mask R-CNN. Confirm to keep; reject to mark as false positive. Scores are raw softmax, not calibrated probabilities.'
            : 'Review this automated detection. Confirming flags it for maintenance; rejecting marks it as a false positive.'}
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

function ModelSection({ defect }: { defect: Defect }) {
  return (
    <section className="border border-sky-200 bg-sky-50/60 rounded-lg overflow-hidden">
      <header className="px-4 py-2 border-b border-sky-200 bg-sky-100/60">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-sky-800">
          Model output
        </p>
      </header>
      <div className="p-4 space-y-3 text-xs">
        {defect.modelName && (
          <div>
            <p className="font-semibold text-slate-500 uppercase tracking-wide text-[10px]">
              Detector
            </p>
            <p className="font-mono text-slate-700 break-all">{defect.modelName}</p>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          {defect.modelLabel && (
            <div>
              <p className="font-semibold text-slate-500 uppercase tracking-wide text-[10px]">
                COCO label
              </p>
              <p className="font-mono text-slate-800">{defect.modelLabel}</p>
            </div>
          )}
          {defect.modelScore !== undefined && (
            <div>
              <p className="font-semibold text-slate-500 uppercase tracking-wide text-[10px]">
                Raw score
              </p>
              <p className="font-mono text-slate-800 tabular-nums">
                {defect.modelScore.toFixed(3)}
              </p>
            </div>
          )}
        </div>
        {defect.bbox && (
          <div>
            <p className="font-semibold text-slate-500 uppercase tracking-wide text-[10px]">
              Bounding box (px)
            </p>
            <p className="font-mono text-slate-700">
              [{defect.bbox.map((n) => n.toFixed(1)).join(', ')}]
            </p>
          </div>
        )}
        {defect.sourceImage && defect.bbox && (
          <div>
            <p className="font-semibold text-slate-500 uppercase tracking-wide text-[10px] mb-1">
              Source image
            </p>
            <SourceImagePreview src={defect.sourceImage} bbox={defect.bbox} label={defect.modelLabel} />
          </div>
        )}
      </div>
    </section>
  );
}

function SourceImagePreview({
  src,
  bbox,
  label,
}: {
  src: string;
  bbox: [number, number, number, number];
  label?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="group relative block w-full border border-slate-300 rounded overflow-hidden bg-slate-900 cursor-zoom-in"
        aria-label="Expand source frame"
      >
        <AnnotatedFrame src={src} bbox={bbox} label={label} className="block w-full h-auto" />
        <span className="absolute top-1.5 right-1.5 bg-slate-900/70 text-white text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded opacity-80 group-hover:opacity-100">
          ⤢ Expand
        </span>
      </button>
      {expanded && <SourceImageLightbox src={src} bbox={bbox} label={label} onClose={() => setExpanded(false)} />}
    </>
  );
}

function AnnotatedFrame({
  src,
  bbox,
  label,
  className,
}: {
  src: string;
  bbox: [number, number, number, number];
  label?: string;
  className?: string;
}) {
  const [x1, y1, x2, y2] = bbox;
  return (
    <figure className="relative">
      <img
        src={src}
        alt="Source frame with detection overlay"
        className={className}
        onLoad={(e) => {
          const img = e.currentTarget;
          const overlay = img.parentElement?.querySelector<SVGSVGElement>('svg');
          if (!overlay) return;
          overlay.setAttribute('viewBox', `0 0 ${img.naturalWidth} ${img.naturalHeight}`);
        }}
      />
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="absolute inset-0 w-full h-full pointer-events-none"
        preserveAspectRatio="none"
      >
        <rect
          x={x1}
          y={y1}
          width={x2 - x1}
          height={y2 - y1}
          fill="none"
          stroke="#f43f5e"
          strokeWidth={4}
          vectorEffect="non-scaling-stroke"
        />
        {label && (
          <text
            x={x1}
            y={Math.max(y1 - 8, 14)}
            fill="#f43f5e"
            fontSize={18}
            fontWeight={700}
            fontFamily="sans-serif"
          >
            {label}
          </text>
        )}
      </svg>
    </figure>
  );
}

function SourceImageLightbox({
  src,
  bbox,
  label,
  onClose,
}: {
  src: string;
  bbox: [number, number, number, number];
  label?: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-8"
      onClick={onClose}
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute top-4 right-6 text-white/80 hover:text-white text-3xl leading-none"
      >
        ×
      </button>
      <div className="max-w-[92vw] max-h-[92vh]" onClick={(e) => e.stopPropagation()}>
        <AnnotatedFrame
          src={src}
          bbox={bbox}
          label={label}
          className="block max-w-[92vw] max-h-[92vh] w-auto h-auto rounded shadow-2xl"
        />
      </div>
    </div>
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
