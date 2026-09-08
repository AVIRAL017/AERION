import React, { useEffect, useState } from 'react';
import { Situation, SituationEvent, WeatherData, DetectionTarget } from '../types';
import { situationsApi } from '../api';

export const BorderPage: React.FC = () => {
  const [situation, setSituation] = useState<Situation | null>(null);
  const [events, setEvents] = useState<SituationEvent[]>([]);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<DetectionTarget | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSituationData = async () => {
      setIsLoading(true);
      try {
        const listRes = await situationsApi.list();
        if (listRes.success && listRes.data && listRes.data.length > 0) {
          const active = listRes.data.find(s => s.situation_type === 'BORDER_SECURITY') || listRes.data[0];
          setSituation(active);

          // Fetch situation details
          const [eventsRes, weatherRes] = await Promise.all([
            situationsApi.getEvents(active.id),
            situationsApi.getWeather(active.id),
          ]);

          if (eventsRes.success && eventsRes.data) {
            setEvents(eventsRes.data);
          }
          if (weatherRes.success && weatherRes.data) {
            setWeather(weatherRes.data);
          }
        }
      } catch (err: any) {
        setError(err.message || 'Error loading border situation');
      } finally {
        setIsLoading(false);
      }
    };

    fetchSituationData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        SYNCHRONIZING OPERATIONAL SECTOR DATA...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-status-critical">
        <span className="material-symbols-outlined mr-2">error</span>
        {error}
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-graphite">
      {/* Upper Main Section: Canvas (Left/Center) + Intelligence Panel (Right) */}
      <div className="flex-1 flex overflow-hidden">
        {/* ============================================================ */}
        {/* CENTRAL SURVEILLANCE CANVAS                                 */}
        {/* ============================================================ */}
        <section className="flex-1 relative flex flex-col border-r border-white/[0.06] overflow-hidden">
          {/* Top Bar with Status and Coordinates */}
          <div className="h-10 px-5 flex items-center justify-between border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20">
            <div className="flex items-center gap-3 font-mono text-[11px]">
              <span className="text-muted uppercase tracking-wider">SECTOR:</span>
              <span className="text-paper font-medium">
                {situation?.location_name || 'SECTOR DELTA-9 (MONITORED)'}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] bg-status-ai/10 text-status-ai border border-status-ai/20">
                RECORDED
              </span>
            </div>

            <div className="flex items-center gap-4 font-mono text-[11px] text-muted">
              <span>LAT: {situation?.latitude ? situation.latitude.toFixed(5) : 'GEOGRAPHIC POSITION UNAVAILABLE'}</span>
              <span>LON: {situation?.longitude ? situation.longitude.toFixed(5) : ''}</span>
            </div>
          </div>

          {/* Surveillance Visual Canvas */}
          <div className="flex-1 relative bg-[#07090C] telemetry-grid flex items-center justify-center overflow-hidden">
            {situation?.detections && situation.detections.length > 0 ? (
              <div className="relative w-full h-full p-8 flex items-center justify-center">
                {/* Visual Canvas with detected targets */}
                <div className="relative border border-white/[0.08] rounded-lg bg-panel/30 w-full h-full overflow-hidden flex items-center justify-center">
                  <div className="absolute top-4 left-4 font-mono text-[11px] text-muted flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-accent animate-ping"></span>
                    <span>ACTIVE TRACKING STREAM</span>
                  </div>

                  {situation.detections.map((target) => (
                    <div
                      key={target.id}
                      onClick={() => setSelectedTarget(target)}
                      className={`absolute cursor-pointer transition-all border p-1 rounded text-[10px] font-mono ${
                        selectedTarget?.id === target.id
                          ? 'border-accent bg-accent/20 text-accent shadow-lg shadow-accent/20'
                          : 'border-status-critical bg-status-critical/10 text-status-critical'
                      }`}
                      style={{
                        top: `${Math.min(Math.max(target.bbox[0] || 30, 10), 80)}%`,
                        left: `${Math.min(Math.max(target.bbox[1] || 40, 10), 80)}%`,
                        width: '120px',
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span>{target.class_name.toUpperCase()}</span>
                        <span>{Math.round(target.confidence * 100)}%</span>
                      </div>
                      <div className="text-[9px] text-muted">
                        ID: {target.track_id || target.id.substring(0, 6)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center max-w-md">
                <div className="w-12 h-12 rounded-full bg-elevated/70 border border-white/[0.08] flex items-center justify-center text-faint mb-3">
                  <span className="material-symbols-outlined text-[24px]">visibility_off</span>
                </div>
                <h3 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
                  NO VERIFIED DETECTIONS
                </h3>
                <p className="text-[11px] text-faint mt-1">
                  Active video/satellite stream is clear or awaiting sensor frame ingest.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* ============================================================ */}
        {/* RIGHT INTELLIGENCE PANEL                                    */}
        {/* ============================================================ */}
        <aside className="w-88 flex-shrink-0 bg-panel flex flex-col overflow-y-auto custom-scrollbar">
          {/* Panel Header */}
          <div className="p-4 border-b border-white/[0.06]">
            <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
              TACTICAL INTELLIGENCE
            </h2>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-paper">
                POTENTIAL UNAUTHORIZED CROSSING INDICATOR
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-status-warning/10 text-status-warning border border-status-warning/20">
                MONITORING
              </span>
            </div>
            <p className="text-[10px] text-faint mt-1">
              Analytical indicator requiring human operator verification.
            </p>
          </div>

          {/* Sector Vulnerability Index */}
          <div className="p-4 border-b border-white/[0.06]">
            <span className="text-[11px] font-mono text-muted uppercase tracking-wider block mb-2">
              SECTOR VULNERABILITY
            </span>
            {situation?.vulnerability_score !== undefined && situation.vulnerability_score !== null ? (
              <div>
                <div className="flex items-baseline justify-between mb-1">
                  <span className="text-2xl font-mono font-bold text-accent">
                    {situation.vulnerability_score.toFixed(1)}
                  </span>
                  <span className="text-xs font-mono text-muted">/ 100</span>
                </div>
                <div className="w-full bg-graphite rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-accent h-full"
                    style={{ width: `${Math.min(situation.vulnerability_score, 100)}%` }}
                  ></div>
                </div>
              </div>
            ) : (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint">
                  INSUFFICIENT EVIDENCE
                </span>
              </div>
            )}
          </div>

          {/* Meteorological Data */}
          <div className="p-4 border-b border-white/[0.06]">
            <span className="text-[11px] font-mono text-muted uppercase tracking-wider block mb-2">
              ENVIRONMENTAL CONDITIONS
            </span>
            {weather && weather.status === 'AVAILABLE' ? (
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                  <span className="text-[10px] text-faint block">TEMPERATURE</span>
                  <span className="text-paper font-medium">
                    {weather.temperature_c !== undefined ? `${weather.temperature_c}°C` : 'N/A'}
                  </span>
                </div>
                <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                  <span className="text-[10px] text-faint block">WIND SPEED</span>
                  <span className="text-paper font-medium">
                    {weather.wind_speed_ms !== undefined ? `${weather.wind_speed_ms} m/s` : 'N/A'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint">
                  WEATHER DATA UNAVAILABLE
                </span>
              </div>
            )}
          </div>

          {/* Selected Target Telemetry */}
          <div className="p-4 flex-1">
            <span className="text-[11px] font-mono text-muted uppercase tracking-wider block mb-2">
              SELECTED TARGET TELEMETRY
            </span>
            {selectedTarget ? (
              <div className="space-y-2 text-xs font-mono bg-graphite/40 p-3 rounded border border-white/[0.04]">
                <div className="flex justify-between">
                  <span className="text-faint">TRACK ID:</span>
                  <span className="text-paper">{selectedTarget.track_id || selectedTarget.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-faint">CLASS:</span>
                  <span className="text-paper uppercase">{selectedTarget.class_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-faint">CONFIDENCE:</span>
                  <span className="text-accent">{Math.round(selectedTarget.confidence * 100)}%</span>
                </div>
                {selectedTarget.velocity && (
                  <div className="flex justify-between">
                    <span className="text-faint">VELOCITY:</span>
                    <span className="text-paper">{selectedTarget.velocity} m/s</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 border border-dashed border-white/[0.06] rounded text-center">
                <span className="text-[11px] font-mono text-faint">
                  SELECT TARGET TO INSPECT
                </span>
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* ============================================================ */}
      {/* BOTTOM EVENT TIMELINE                                       */}
      {/* ============================================================ */}
      <footer className="h-28 bg-[#090C10] border-t border-white/[0.06] p-4 flex flex-col justify-between flex-shrink-0 z-30">
        <div className="flex items-center justify-between font-mono text-[10px] text-muted uppercase tracking-wider mb-2">
          <span>OPERATIONAL EVENT LOG (CHRONOLOGICAL)</span>
          <span>{events.length} EVENTS RECORDED</span>
        </div>

        <div className="flex-1 flex gap-3 overflow-x-auto custom-scrollbar items-center pb-1">
          {events.length > 0 ? (
            events.map((ev) => (
              <div
                key={ev.id}
                className="flex-shrink-0 w-64 p-2 rounded bg-panel border border-white/[0.06] text-xs font-mono flex flex-col justify-between"
              >
                <div className="flex items-center justify-between text-[10px] text-faint">
                  <span>{new Date(ev.created_at).toISOString().substring(11, 19)} UTC</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] ${
                      ev.severity === 'CRITICAL'
                        ? 'bg-status-critical/10 text-status-critical'
                        : 'bg-status-warning/10 text-status-warning'
                    }`}
                  >
                    {ev.severity}
                  </span>
                </div>
                <div className="text-paper text-[11px] font-medium truncate mt-1">
                  {ev.title}
                </div>
              </div>
            ))
          ) : (
            <div className="w-full text-center text-[11px] font-mono text-faint">
              NO SITUATION EVENTS LOGGED
            </div>
          )}
        </div>
      </footer>
    </div>
  );
};
