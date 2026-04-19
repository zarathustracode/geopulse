// Shapes mirror the backend's Defect model. Regenerate via `npm run generate-api`
// once the backend is running to replace this file with openapi-ts output.

export type DefectType =
  | 'crack'
  | 'pothole'
  | 'damage'
  | 'sign'
  | 'trafficLight'
  | 'hydrant';

export const DEFECT_TYPE_LABELS: Record<DefectType, string> = {
  crack: 'Crack',
  pothole: 'Pothole',
  damage: 'Damage',
  sign: 'Sign',
  trafficLight: 'Traffic light',
  hydrant: 'Hydrant',
};
export type Severity = 'low' | 'medium' | 'high';
export type DefectStatus = 'new' | 'confirmed' | 'rejected';
export type DefectSource = 'seed' | 'model';

export interface Defect {
  id: string;
  type: DefectType;
  confidence: number;
  severity: Severity;
  status: DefectStatus;
  latitude: number;
  longitude: number;
  timestamp: string;
  source: DefectSource;
  modelName?: string;
  modelLabel?: string;
  modelScore?: number;
  bbox?: [number, number, number, number];
  sourceImage?: string;
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
