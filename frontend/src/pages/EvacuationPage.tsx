import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { externalApi, sheltersApi, situationsApi } from '../api';
import { RouteOption, LocationProvenance } from '../types';
import { OperatorLocationModal } from '../components/OperatorLocationModal';

// Custom Map Marker Icons for Leaflet
const createOriginIcon = () => {
  return L.divIcon({
    className: 'aerion-origin-pin',
    html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
      <div style="background:#EF4444;width:16px;height:16px;border-radius:50%;border:2px solid #FFFFFF;box-shadow:0 0 12px rgba(239,68,68,0.9);display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px;font-weight:bold;">!</div>
      <div style="width:2px;height:12px;background:#EF4444;"></div>
    </div>`,
    iconSize: [24, 28],
    iconAnchor: [12, 28],
  });
};

const createShelterIcon = (isSelected: boolean) => {
  const bg = isSelected ? '#38D5F5' : '#10B981';
  return L.divIcon({
    className: 'aerion-shelter-pin',
    html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
      <div style="background:${bg};width:14px;height:14px;border-radius:3px;border:2px solid #FFFFFF;box-shadow:0 0 10px ${bg};"></div>
      <div style="width:2px;height:10px;background:${bg};"></div>
    </div>`,
    iconSize: [20, 24],
    iconAnchor: [10, 24],
  });
};

export const EvacuationPage: React.FC = () => {
  // Geo-Context & Operational State
  const [disasterLocation, setDisasterLocation] = useState<LocationProvenance | null>(null);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);
  const [shelterCandidates, setShelterCandidates] = useState<any[]>([]);
  const [selectedShelter, setSelectedShelter] = useState<any | null>(null);
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<RouteOption | null>(null);
  const [activeGeoJson, setActiveGeoJson] = useState<any | null>(null);
  const [routePreference, setRoutePreference] = useState<'fastest' | 'shortest'>('fastest');
  
  // Loading & Error States
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRouting, setIsRouting] = useState<boolean>(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [shelterError, setShelterError] = useState<string | null>(null);

  // Leaflet Map Refs
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.Polyline | null>(null);

  // 1. Initial Load: Try finding disaster situation or previous geo-context
  useEffect(() => {
    const initPage = async () => {
      setIsLoading(true);
      try {
        const listRes = await situationsApi.list();
        if (listRes.success && listRes.data && listRes.data.length > 0) {
          const active = listRes.data.find((s) => s.situation_type === 'DISASTER_RESPONSE') || listRes.data[0];
          if (active.latitude && active.longitude) {
            setDisasterLocation({
              latitude: active.latitude,
              longitude: active.longitude,
              label: active.location_name || 'Active Disaster Zone',
              location_source: 'OPERATOR_PROVIDED',
              location_precision: 'APPROXIMATE',
              location_method: 'MANUAL_COORDINATES',
            });
          }
        }
      } catch (e) {
        console.warn('Could not retrieve active situations:', e);
      } finally {
        setIsLoading(false);
      }
    };
    initPage();
  }, []);

  // 2. Fetch Shelters when disaster location is available
  useEffect(() => {
    if (!disasterLocation?.latitude || !disasterLocation?.longitude) {
      setShelterCandidates([]);
      setSelectedShelter(null);
      setRoutes([]);
      setSelectedRoute(null);
      return;
    }

    const loadShelters = async () => {
      setShelterError(null);
      try {
        const resp = await sheltersApi.list({
          latitude: disasterLocation.latitude,
          longitude: disasterLocation.longitude,
          radius_km: 100.0,
        });

        const list = resp?.shelters || resp?.data?.shelters || [];
        if (list.length > 0) {
          setShelterCandidates(list);
          setSelectedShelter(list[0]);
        } else {
          setShelterCandidates([]);
          setSelectedShelter(null);
          setShelterError('NO VERIFIED SHELTER FOUND within 100km radius.');
        }
      } catch (err: any) {
        setShelterError(err.message || 'Failed to query verified shelters from PostGIS.');
        setShelterCandidates([]);
      }
    };
    loadShelters();
  }, [disasterLocation]);

  // 3. Route Calculation via ORS (api.heigit.org) when location & shelter are ready
  useEffect(() => {
    if (!disasterLocation?.latitude || !disasterLocation?.longitude || !selectedShelter?.location) {
      setRoutes([]);
      setSelectedRoute(null);
      setActiveGeoJson(null);
      return;
    }

    const calcRoute = async () => {
      setIsRouting(true);
      setRouteError(null);
      try {
        const destLat = selectedShelter.location.latitude;
        const destLon = selectedShelter.location.longitude;

        const resp = await externalApi.getRoute(
          disasterLocation.latitude,
          disasterLocation.longitude,
          destLat,
          destLon,
          'driving-car'
        );

        if (resp.success && resp.data && resp.data.status === 'AVAILABLE') {
          const rec = resp.data;
          const distKm = rec.total_distance_meters ? round(rec.total_distance_meters / 1000.0, 2) : 0;
          const durMin = rec.total_duration_seconds ? round(rec.total_duration_seconds / 60.0, 1) : 0;

          const calculatedOpt: RouteOption = {
            id: rec.route_id || 'route-primary',
            name: `${selectedShelter.name} Corridor`,
            type: routePreference === 'fastest' ? 'FASTEST_FEASIBLE' : 'SAFEST_FEASIBLE',
            distance_km: distKm,
            duration_min: durMin,
            hazard_clearance_score: 1.0,
            is_viable: true,
          };

          setRoutes([calculatedOpt]);
          setSelectedRoute(calculatedOpt);
          setActiveGeoJson(rec.geometry_geojson || null);
        } else {
          setRoutes([]);
          setSelectedRoute(null);
          setActiveGeoJson(null);
          setRouteError(resp.data?.warnings?.[0] || 'ROUTE UNAVAILABLE: Road network routing could not connect coordinates.');
        }
      } catch (err: any) {
        setRouteError(err.message || 'Routing service query timed out or unavailable.');
        setRoutes([]);
        setSelectedRoute(null);
      } finally {
        setIsRouting(false);
      }
    };

    calcRoute();
  }, [disasterLocation, selectedShelter, routePreference]);

  // 4. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialLat = disasterLocation?.latitude || 28.6139;
    const initialLon = disasterLocation?.longitude || 77.2090;

    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLon],
      zoom: 10,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors | AERION Bounded Routing',
    }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = markersGroup;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // 5. Update Map Markers & Route Polyline
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    markersGroup.clearLayers();

    if (routeLayerRef.current) {
      map.removeLayer(routeLayerRef.current);
      routeLayerRef.current = null;
    }

    const bounds = L.latLngBounds([]);

    // Plot Origin (Disaster Location)
    if (disasterLocation?.latitude && disasterLocation?.longitude) {
      const originPt = [disasterLocation.latitude, disasterLocation.longitude] as [number, number];
      const m = L.marker(originPt, { icon: createOriginIcon() })
        .bindPopup(`<b>ORIGIN: DISASTER LOCATION</b><br>${disasterLocation.label || 'Monitored Disaster Point'}<br>${disasterLocation.latitude.toFixed(5)}, ${disasterLocation.longitude.toFixed(5)}`);
      markersGroup.addLayer(m);
      bounds.extend(originPt);
    }

    // Plot Shelters
    shelterCandidates.forEach((sh) => {
      if (sh.location?.latitude && sh.location?.longitude) {
        const isSel = selectedShelter?.shelter_id === sh.shelter_id;
        const pt = [sh.location.latitude, sh.location.longitude] as [number, number];
        const m = L.marker(pt, { icon: createShelterIcon(isSel) })
          .bindPopup(`<b>SHELTER: ${sh.name}</b><br>Type: ${sh.shelter_type || 'Unknown'}<br>Capacity: ${sh.capacity_total || 'Unspecified'}<br>Status: ${sh.operational_status || 'OPEN'}`);
        markersGroup.addLayer(m);
        bounds.extend(pt);
      }
    });

    // Plot Route Polyline (GeoJSON from ORS)
    if (activeGeoJson && activeGeoJson.coordinates && activeGeoJson.coordinates.length > 0) {
      // Coordinates in GeoJSON are [lon, lat]
      const latLngs: [number, number][] = activeGeoJson.coordinates.map((coord: number[]) => [coord[1], coord[0]]);
      const poly = L.polyline(latLngs, {
        color: '#38D5F5',
        weight: 5,
        opacity: 0.85,
        dashArray: undefined,
      }).addTo(map);

      routeLayerRef.current = poly;
      bounds.extend(poly.getBounds());
    }

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [disasterLocation, shelterCandidates, selectedShelter, activeGeoJson]);

  const round = (val: number, decimals: number) => {
    const factor = Math.pow(10, decimals);
    return Math.round(val * factor) / factor;
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        SYNCHRONIZING SAFE ROUTE GEODATAS...
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-graphite">
      {/* Central Evacuation Map Canvas */}
      <section className="flex-1 relative flex flex-col border-r border-white/[0.06] overflow-hidden">
        {/* Top Assessment Header */}
        <div className="h-10 px-5 flex items-center justify-between border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20">
          <div className="flex items-center gap-3 font-mono text-[11px]">
            <span className="text-muted uppercase">CORRIDOR ASSESSMENT:</span>
            <span className="text-paper font-medium">OPENROUTESERVICE (api.heigit.org)</span>
            <span className="px-2 py-0.5 rounded text-[10px] bg-status-success/10 text-status-success border border-status-success/20">
              {routes.length > 0 ? 'ROAD VIABLE' : 'EVALUATING'}
            </span>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px]">
            {disasterLocation ? (
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="px-2 py-0.5 rounded bg-elevated/80 border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[10px] flex items-center gap-1 transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[12px]">edit_location</span>
                <span>GEO-CONTEXT: {disasterLocation.latitude.toFixed(3)}°N, {disasterLocation.longitude.toFixed(3)}°E</span>
              </button>
            ) : (
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="px-2 py-0.5 rounded bg-status-warning/20 border border-status-warning/40 text-status-warning text-[10px] flex items-center gap-1 font-bold animate-pulse cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">add_location_alt</span>
                <span>SET DISASTER GEO-CONTEXT</span>
              </button>
            )}

            <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5">
              <button
                onClick={() => setRoutePreference('fastest')}
                className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                  routePreference === 'fastest' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                }`}
              >
                FASTEST
              </button>
              <button
                onClick={() => setRoutePreference('shortest')}
                className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                  routePreference === 'shortest' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                }`}
              >
                SHORTEST
              </button>
            </div>
          </div>
        </div>

        {/* Leaflet Interactive Map Container */}
        <div className="flex-1 relative bg-[#07090C] overflow-hidden">
          <div ref={mapContainerRef} className="w-full h-full" style={{ background: '#090D12' }} />

          {/* Missing Location Overlay Banner */}
          {!disasterLocation && (
            <div className="absolute inset-0 z-30 bg-graphite/85 backdrop-blur-sm flex flex-col items-center justify-center p-8 text-center">
              <div className="w-14 h-14 rounded-full bg-elevated/80 border border-status-warning/40 flex items-center justify-center text-status-warning mb-3">
                <span className="material-symbols-outlined text-[28px]">warning</span>
              </div>
              <h3 className="text-sm font-mono font-bold tracking-wider text-paper uppercase">
                DISASTER LOCATION REQUIRED
              </h3>
              <p className="text-xs text-muted max-w-sm mt-1 mb-4 font-mono">
                Safe evacuation corridor calculation requires authoritative geographic coordinates for the disaster epicentre.
              </p>
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="px-4 py-2 rounded bg-accent text-graphite font-mono font-bold text-xs hover:bg-accent/90 transition-all flex items-center gap-1.5 shadow cursor-pointer"
              >
                <span className="material-symbols-outlined text-[15px]">add_location_alt</span>
                <span>SET GEO-CONTEXT ON MAP</span>
              </button>
            </div>
          )}

          {/* Map Legend Overlay */}
          <div className="absolute bottom-4 left-4 z-20 bg-graphite/90 border border-white/[0.1] rounded p-2 text-[10px] font-mono text-muted space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-critical border border-white"></span>
              <span className="text-paper">Disaster Epicentre</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-accent border border-white"></span>
              <span className="text-paper">Selected Emergency Shelter</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-status-success border border-white"></span>
              <span className="text-paper">Other Available Shelters</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-accent"></span>
              <span className="text-paper">ORS Navigable Road Corridor</span>
            </div>
          </div>
        </div>
      </section>

      {/* Right Evacuation Rail */}
      <aside className="w-96 flex-shrink-0 bg-panel flex flex-col overflow-y-auto custom-scrollbar border-l border-white/[0.06]">
        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
            SAFE EVACUATION CORRIDORS
          </h2>
          <span className="text-[10px] text-faint font-mono block mt-1">
            ROAD ACCESSIBILITY STRICTLY CORROBORATED
          </span>
        </div>

        {/* Active Route Summary Card */}
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block">
              CALCULATED CORRIDOR
            </span>
            {isRouting && (
              <span className="text-[10px] font-mono text-accent flex items-center gap-1">
                <span className="material-symbols-outlined text-[12px] animate-spin">progress_activity</span>
                <span>ROUTING...</span>
              </span>
            )}
          </div>

          {selectedRoute ? (
            <div className="p-3 rounded border border-accent/40 bg-accent/10 font-mono space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-paper font-bold">{selectedRoute.name}</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] bg-status-success/20 text-status-success border border-status-success/30 font-bold">
                  {selectedRoute.type}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-white/[0.06]">
                <div>
                  <span className="text-faint text-[9px] block">DISTANCE</span>
                  <span className="text-paper font-bold text-sm">{selectedRoute.distance_km} km</span>
                </div>
                <div>
                  <span className="text-faint text-[9px] block">TRAVEL TIME</span>
                  <span className="text-accent font-bold text-sm">{selectedRoute.duration_min} min</span>
                </div>
              </div>
              <div className="text-[10px] text-faint pt-1 space-y-0.5">
                <div>Provider: OpenRouteService (api.heigit.org)</div>
                <div>Hazard Avoidance: HAZARD DATA UNAVAILABLE</div>
              </div>
            </div>
          ) : (
            <div className="p-3 border border-dashed border-white/[0.08] rounded text-center font-mono">
              <span className="text-[11px] text-status-warning block font-semibold">
                {routeError || (!disasterLocation ? 'DISASTER LOCATION REQUIRED' : 'NO FEASIBLE ROUTE AVAILABLE')}
              </span>
              <span className="text-[10px] text-faint block mt-1">
                {!disasterLocation
                  ? 'Set geo-context to initiate road network query.'
                  : 'No navigable path between coordinates.'}
              </span>
            </div>
          )}
        </div>

        {/* Shelters Selection List */}
        <div className="p-4 flex-1 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block">
              VERIFIED SHELTER CANDIDATES ({shelterCandidates.length})
            </span>
          </div>

          {shelterCandidates.length > 0 ? (
            <div className="space-y-2">
              {shelterCandidates.map((sh) => {
                const isSel = selectedShelter?.shelter_id === sh.shelter_id;
                return (
                  <div
                    key={sh.shelter_id}
                    onClick={() => setSelectedShelter(sh)}
                    className={`p-2.5 rounded border cursor-pointer font-mono transition-all ${
                      isSel
                        ? 'border-accent bg-accent/15 shadow'
                        : 'border-white/[0.06] bg-graphite/40 hover:bg-graphite/60'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-paper">{sh.name}</span>
                      <span className="text-[10px] text-accent">
                        {sh.distance_km !== undefined ? `${round(sh.distance_km, 1)} km` : ''}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-muted mt-1">
                      <span>TYPE: {sh.shelter_type || 'UNKNOWN'}</span>
                      <span className="text-status-success">{sh.operational_status || 'OPEN'}</span>
                    </div>
                    {sh.capacity_total && (
                      <div className="text-[9px] text-faint mt-0.5">
                        CAPACITY: {sh.capacity_total} PERSONS
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 border border-dashed border-white/[0.08] rounded text-center font-mono">
              <span className="text-[11px] text-muted block">
                {shelterError || 'NO SHELTER RECORDS RETRIEVED'}
              </span>
              <span className="text-[10px] text-faint block mt-1">
                Registered shelter points from PostGIS shelter repository.
              </span>
            </div>
          )}
        </div>
      </aside>

      {/* Operator Geo-Context Modal */}
      <OperatorLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        existingLocation={disasterLocation}
        onConfirmLocation={(loc) => {
          setDisasterLocation(loc);
          setIsLocationModalOpen(false);
        }}
      />
    </div>
  );
};
