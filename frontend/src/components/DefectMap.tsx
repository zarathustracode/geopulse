import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, {
  GeoJSONSource,
  Map as MapLibreMap,
  MapGeoJSONFeature,
} from 'maplibre-gl';
import type { BoundingBox, Defect } from '../api/types';

interface DefectMapProps {
  defects: Defect[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onViewportChange?: (bbox: BoundingBox) => void;
}

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
  glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
};

const SOURCE_ID = 'defects';
const CLUSTER_LAYER = 'defect-clusters';
const CLUSTER_COUNT_LAYER = 'defect-cluster-counts';
const POINT_LAYER = 'defect-points';

function addDefectsLayers(
  map: MapLibreMap,
  data: GeoJSON.FeatureCollection,
  onSelect: (id: string) => void,
) {
  map.addSource(SOURCE_ID, {
    type: 'geojson',
    data,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 50,
  });

  map.addLayer({
    id: CLUSTER_LAYER,
    type: 'circle',
    source: SOURCE_ID,
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': '#2563eb',
      'circle-opacity': 0.85,
      'circle-radius': ['step', ['get', 'point_count'], 16, 5, 22, 15, 28],
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  });

  map.addLayer({
    id: CLUSTER_COUNT_LAYER,
    type: 'symbol',
    source: SOURCE_ID,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': ['get', 'point_count_abbreviated'],
      // Must be explicit — openmaptiles.org doesn't serve MapLibre's default
      // fallback (Arial Unicode MS Regular); an HTML 404 body fed into the
      // pbf decoder throws "Unimplemented type: 4" and silently poisons the
      // whole clustered source so no markers render.
      'text-font': ['Open Sans Regular'],
      'text-size': 12,
    },
    paint: { 'text-color': '#ffffff' },
  });

  map.addLayer({
    id: POINT_LAYER,
    type: 'circle',
    source: SOURCE_ID,
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius': 7,
      'circle-color': [
        'match',
        ['get', 'severity'],
        'high', '#e11d48',
        'medium', '#f59e0b',
        'low', '#10b981',
        '#64748b',
      ],
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  });

  map.on('click', POINT_LAYER, (e) => {
    const feature = e.features?.[0] as MapGeoJSONFeature | undefined;
    const id = feature?.properties?.id as string | undefined;
    if (id) onSelect(id);
  });

  map.on('click', CLUSTER_LAYER, (e) => {
    const feature = e.features?.[0];
    const clusterId = feature?.properties?.cluster_id as number | undefined;
    if (clusterId === undefined) return;
    const source = map.getSource(SOURCE_ID) as GeoJSONSource;
    source.getClusterExpansionZoom(clusterId).then((zoom) => {
      const coords = (feature!.geometry as GeoJSON.Point).coordinates as [number, number];
      map.easeTo({ center: coords, zoom });
    });
  });

  const setPointer = () => (map.getCanvas().style.cursor = 'pointer');
  const clearPointer = () => (map.getCanvas().style.cursor = '');
  map.on('mouseenter', POINT_LAYER, setPointer);
  map.on('mouseleave', POINT_LAYER, clearPointer);
  map.on('mouseenter', CLUSTER_LAYER, setPointer);
  map.on('mouseleave', CLUSTER_LAYER, clearPointer);
}

export function DefectMap({ defects, selectedId, onSelect, onViewportChange }: DefectMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const featureCollection = useMemo<GeoJSON.FeatureCollection>(
    () => ({
      type: 'FeatureCollection',
      features: defects.map((d) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [d.longitude, d.latitude] },
        properties: {
          id: d.id,
          status: d.status,
          severity: d.severity,
          type: d.type,
          confidence: d.confidence,
        },
      })),
    }),
    [defects],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [7.6250, 47.0609],
      zoom: 12.5,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');

    const emitViewport = () => {
      if (!onViewportChange) return;
      const b = map.getBounds();
      onViewportChange({
        minLongitude: b.getWest(),
        minLatitude: b.getSouth(),
        maxLongitude: b.getEast(),
        maxLatitude: b.getNorth(),
      });
    };
    map.on('moveend', emitViewport);
    map.on('load', () => {
      emitViewport();
      setMapReady(true);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const existing = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    if (existing) {
      existing.setData(featureCollection);
    } else {
      addDefectsLayers(map, featureCollection, onSelect);
    }
  }, [mapReady, featureCollection, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    if (!map.getLayer(POINT_LAYER)) return;
    map.setPaintProperty(POINT_LAYER, 'circle-radius', [
      'case',
      ['==', ['get', 'id'], ['literal', selectedId ?? '']],
      11,
      7,
    ]);
  }, [selectedId, mapReady, featureCollection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedId) return;
    const target = defects.find((d) => d.id === selectedId);
    if (!target) return;
    map.easeTo({ center: [target.longitude, target.latitude], zoom: Math.max(map.getZoom(), 13) });
  }, [selectedId, defects]);

  return <div ref={containerRef} className="flex-1 h-full" />;
}
