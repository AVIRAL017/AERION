import React, { useEffect, useState } from 'react';
import { situationsApi } from '../api';
import { RouteOption, ShelterData } from '../types';

export const EvacuationPage: React.FC = () => {
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [shelters, setShelters] = useState<ShelterData[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<RouteOption | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchEvacuationData = async () => {
      setIsLoading(true);
      try {
        const listRes = await situationsApi.list();
        if (listRes.success && listRes.data && listRes.data.length > 0) {
          const active = listRes.data.find(s => s.situation_type === 'DISASTER_RESPONSE') || listRes.data[0];
          const routesRes = await situationsApi.getRoutes(active.id);
          if (routesRes.success && routesRes.data) {
            setRoutes(routesRes.data);
            if (routesRes.data.length > 0) {
              setSelectedRoute(routesRes.data[0]);
            }
          }
          if (active.shelters) {
            setShelters(active.shelters);
          }
        }
      } catch {
        // Fallback
      } finally {
        setIsLoading(false);
      }
    };
    fetchEvacuationData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        SYNCHRONIZING EVACUATION CORRIDORS & SHELTERS...
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-graphite">
      {/* Central Evacuation Map Canvas */}
      <section className="flex-1 relative flex flex-col border-r border-white/[0.06] overflow-hidden">
        <div className="h-10 px-5 flex items-center justify-between border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20">
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span className="text-muted uppercase">CORRIDOR ASSESSMENT:</span>
            <span className="text-paper font-medium">OPENROUTESERVICE FEASIBILITY</span>
            <span className="px-2 py-0.5 rounded text-[10px] bg-status-success/10 text-status-success border border-status-success/20">
              BOUNDED
            </span>
          </div>
          <span className="font-mono text-[11px] text-muted">
            {routes.length} FEASIBLE CANDIDATES
          </span>
        </div>

        <div className="flex-1 relative bg-[#07090C] telemetry-grid flex items-center justify-center p-8">
          {routes.length > 0 ? (
            <div className="w-full h-full border border-white/[0.08] rounded-lg bg-panel/30 flex flex-col items-center justify-center p-6 text-center">
              <span className="material-symbols-outlined text-accent text-[32px] mb-2">map</span>
              <span className="text-xs font-mono text-paper font-medium uppercase">
                GEOSPATIAL EVACUATION CORRIDOR
              </span>
              <span className="text-[11px] font-mono text-faint mt-1 max-w-md">
                WGS84 route waypoints mapped with hazard proximity clearance.
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-center p-8">
              <div className="w-12 h-12 rounded-full bg-elevated/70 border border-white/[0.08] flex items-center justify-center text-faint mb-3">
                <span className="material-symbols-outlined text-[24px]">alt_route</span>
              </div>
              <h3 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
                NO FEASIBLE ROUTE AVAILABLE
              </h3>
              <p className="text-[11px] text-faint mt-1 max-w-xs">
                Corridors are either uncalculated or fully obstructed by active hazard zones.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Right Evacuation Rail */}
      <aside className="w-88 flex-shrink-0 bg-panel flex flex-col overflow-y-auto custom-scrollbar">
        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
            EVACUATION CORRIDORS
          </h2>
          <span className="text-[10px] text-faint font-mono block mt-1">
            ROAD ACCESSIBILITY STRICTLY CORROBORATED
          </span>
        </div>

        {/* Route Cards */}
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <span className="text-[10px] font-mono text-muted uppercase tracking-wider block">
            CALCULATED ROUTES
          </span>
          {routes.length > 0 ? (
            routes.map((rt) => (
              <div
                key={rt.id}
                onClick={() => setSelectedRoute(rt)}
                className={`p-3 rounded border cursor-pointer transition-all ${
                  selectedRoute?.id === rt.id
                    ? 'border-accent bg-accent/10'
                    : 'border-white/[0.06] bg-graphite/40 hover:bg-graphite/60'
                }`}
              >
                <div className="flex items-center justify-between text-xs font-mono mb-1">
                  <span className="text-paper font-medium">{rt.name}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] ${
                      rt.type === 'SAFEST_FEASIBLE'
                        ? 'bg-status-success/10 text-status-success'
                        : 'bg-status-warning/10 text-status-warning'
                    }`}
                  >
                    {rt.type}
                  </span>
                </div>
                <div className="flex justify-between text-[11px] font-mono text-muted">
                  <span>{rt.distance_km.toFixed(1)} km</span>
                  <span>{Math.round(rt.duration_min)} min</span>
                </div>
              </div>
            ))
          ) : (
            <div className="p-4 border border-dashed border-white/[0.06] rounded text-center">
              <span className="text-[11px] font-mono text-faint">
                NO FEASIBLE ROUTE AVAILABLE
              </span>
            </div>
          )}
        </div>

        {/* Shelters */}
        <div className="p-4 flex-1">
          <span className="text-[10px] font-mono text-muted uppercase tracking-wider block mb-2">
            ASSIGNED SHELTERS
          </span>
          {shelters.length > 0 ? (
            <div className="space-y-2">
              {shelters.map((sh) => (
                <div key={sh.id} className="p-2 bg-graphite/40 border border-white/[0.04] rounded text-xs font-mono">
                  <div className="flex justify-between font-medium text-paper">
                    <span>{sh.name}</span>
                    <span className="text-[10px] text-accent">{sh.status}</span>
                  </div>
                  <div className="text-[10px] text-faint mt-1">
                    OCCUPANCY: {sh.current_occupancy} / {sh.capacity}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 border border-dashed border-white/[0.06] rounded text-center">
              <span className="text-[11px] font-mono text-faint">
                NO SHELTER RECORDS RETRIEVED
              </span>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
};
