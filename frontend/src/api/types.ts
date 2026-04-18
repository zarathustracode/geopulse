// Shapes mirror the backend's Defect model. Regenerate via `npm run generate-api`
// once the backend is running to replace this file with openapi-ts output.

export type DefectType = 'crack' | 'pothole' | 'damage';
export type Severity = 'low' | 'medium' | 'high';
export type DefectStatus = 'new' | 'confirmed' | 'rejected';

export interface Defect {
  id: string;
  type: DefectType;
  confidence: number;
  severity: Severity;
  status: DefectStatus;
  latitude: number;
  longitude: number;
  timestamp: string;
}

export interface BoundingBox {
  minLongitude: number;
  minLatitude: number;
  maxLongitude: number;
  maxLatitude: number;
}

export interface DefectFilters {
  type?: DefectType;
  status?: DefectStatus;
  minConfidence?: number;
  bbox?: BoundingBox;
}
