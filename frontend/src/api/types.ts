// Shapes mirror the backend's Defect model. Regenerate via `npm run generate-api`
// once the backend is running to replace this file with openapi-ts output.

export type DefectType =
  | 'longitudinalCrack'
  | 'transverseCrack'
  | 'alligatorCrack'
  | 'pothole'
  | 'crack'
  | 'damage'
  | 'sign'
  | 'trafficLight'
  | 'hydrant';

export const DEFECT_TYPE_LABELS: Record<DefectType, string> = {
  longitudinalCrack: 'Longitudinal crack (D00)',
  transverseCrack: 'Transverse crack (D10)',
  alligatorCrack: 'Alligator crack (D20)',
  pothole: 'Pothole (D40)',
  crack: 'Crack',
  damage: 'Damage',
  sign: 'Sign',
  trafficLight: 'Traffic light',
  hydrant: 'Hydrant',
};
export type Severity = 'low' | 'medium' | 'high';
export type DefectStatus = 'new' | 'confirmed' | 'rejected';
export type DefectSource = 'seed' | 'model';
export type MatchStatus =
  | 'unknown'           // no ground truth available
  | 'truePositive'      // matched a labelled box at IoU ≥ 0.5
  | 'falsePositive'     // model proposed; nothing to match
  | 'falseNegative';    // labelled; model missed it

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
  matchStatus?: MatchStatus;
  calibratedScore?: number;
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
