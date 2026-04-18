import { useCallback, useEffect, useState } from 'react';
import { defectsApi } from '../api/client';
import type { Defect, DefectFilters, DefectStatus } from '../api/types';

export interface UseDefectsResult {
  defects: Defect[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updateStatus: (id: string, status: DefectStatus) => Promise<void>;
}

export function useDefects(filters: DefectFilters): UseDefectsResult {
  const [defects, setDefects] = useState<Defect[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDefects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await defectsApi.list(filters);
      setDefects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load defects');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void fetchDefects();
  }, [fetchDefects]);

  const updateStatus = useCallback(async (id: string, status: DefectStatus) => {
    const updated = await defectsApi.updateStatus(id, status);
    setDefects((prev) => prev.map((d) => (d.id === id ? updated : d)));
  }, []);

  return { defects, loading, error, refresh: fetchDefects, updateStatus };
}
