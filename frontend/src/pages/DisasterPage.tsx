import React, { useEffect, useState, useRef } from 'react';
import { situationsApi } from '../api';
import { DamageSummary } from '../types';

export const DisasterPage: React.FC = () => {
  const [sliderPosition, setSliderPosition] = useState<number>(50);
  const [damage, setDamage] = useState<DamageSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchDisasterData = async () => {
      setIsLoading(true);
      try {
        const listRes = await situationsApi.list();
        if (listRes.success && listRes.data && listRes.data.length > 0) {
          const active = listRes.data.find(s => s.situation_type === 'DISASTER_RESPONSE') || listRes.data[0];
          if (active.damage) {
            setDamage(active.damage);
          }
        }
      } catch {
        // Fallback state
      } finally {
        setIsLoading(false);
      }
    };
    fetchDisasterData();
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    setSliderPosition((x / rect.width) * 100);
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        SYNCHRONIZING BI-TEMPORAL DISASTER WORKSPACE...
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-graphite">
      {/* ============================================================ */}
      {/* CENTRAL BI-TEMPORAL SPLIT-CURTAIN WORKSPACE                  */}
      {/* ============================================================ */}
      <section className="flex-1 relative flex flex-col border-r border-white/[0.06] overflow-hidden">
        {/* Workspace Toolbar */}
        <div className="h-10 px-5 flex items-center justify-between border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20">
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span className="text-muted uppercase">ANALYSIS MODE:</span>
            <span className="text-paper font-medium">BI-TEMPORAL DAMAGE WORKSPACE</span>
            <span className="px-2 py-0.5 rounded text-[10px] bg-accent/10 text-accent border border-accent/20">
              SIAMESE FUSED
            </span>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px] text-muted">
            <span>CURTAIN SPLIT: {Math.round(sliderPosition)}%</span>
          </div>
        </div>

        {/* Bi-Temporal Split View Canvas */}
        <div
          ref={containerRef}
          onMouseMove={handleMouseMove}
          className="flex-1 relative bg-[#07090C] telemetry-grid overflow-hidden cursor-ew-resize select-none"
        >
          {damage?.pre_image_url && damage?.post_image_url ? (
            <div className="relative w-full h-full">
              {/* Post-Disaster Layer (Underneath / Right side) */}
              <img
                src={damage.post_image_url}
                alt="Post-Disaster Observation"
                className="absolute inset-0 w-full h-full object-cover pointer-events-none"
              />

              {/* Pre-Disaster Layer (Clipped curtain / Left side) */}
              <div
                className="slider-curtain"
                style={{ width: `${sliderPosition}%` }}
              >
                <img
                  src={damage.pre_image_url}
                  alt="Pre-Disaster Baseline"
                  className="slider-inner object-cover"
                />
              </div>

              {/* Slider Handle Divider Line */}
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-accent z-30 pointer-events-none shadow-[0_0_10px_#38D5F5]"
                style={{ left: `${sliderPosition}%` }}
              >
                <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-graphite border-2 border-accent flex items-center justify-center text-accent text-[10px] font-mono">
                  ⇆
                </div>
              </div>
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-elevated/70 border border-white/[0.08] flex items-center justify-center text-faint mb-3">
                <span className="material-symbols-outlined text-[24px]">satellite_alt</span>
              </div>
              <h3 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
                DAMAGE ANALYSIS UNAVAILABLE
              </h3>
              <p className="text-[11px] text-faint mt-1 max-w-sm">
                Awaiting bi-temporal satellite pair (pre-disaster baseline + post-disaster scene).
              </p>
            </div>
          )}

          {/* Left/Right Overlays */}
          <div className="absolute bottom-4 left-4 z-20 pointer-events-none">
            <span className="px-2 py-1 rounded bg-graphite/80 border border-white/[0.08] text-[10px] font-mono text-muted">
              PRE-DISASTER BASELINE
            </span>
          </div>
          <div className="absolute bottom-4 right-4 z-20 pointer-events-none">
            <span className="px-2 py-1 rounded bg-graphite/80 border border-white/[0.08] text-[10px] font-mono text-accent">
              POST-DISASTER OBSERVATION
            </span>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* RIGHT INTELLIGENCE PANEL                                    */}
      {/* ============================================================ */}
      <aside className="w-88 flex-shrink-0 bg-panel flex flex-col overflow-y-auto custom-scrollbar">
        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
            DAMAGE CLASSIFICATION
          </h2>
          <div className="mt-2">
            <span className="text-sm font-semibold text-paper block">
              INFRASTRUCTURE DAMAGE ASSESSMENT
            </span>
            <span className="text-[10px] text-faint font-mono">
              FROZEN SIAMESE DAMAGE RUNTIME (THRESHOLD 0.50)
            </span>
          </div>
        </div>

        {/* Damage Metrics */}
        <div className="p-4 border-b border-white/[0.06] space-y-4">
          <div>
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block mb-1">
              AGGREGATE DAMAGE LEVEL
            </span>
            {damage ? (
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-mono font-bold text-status-critical">
                  {damage.damage_percentage.toFixed(1)}%
                </span>
                <span className="text-xs font-mono text-muted uppercase">
                  {damage.classification}
                </span>
              </div>
            ) : (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint">
                  DAMAGE ANALYSIS UNAVAILABLE
                </span>
              </div>
            )}
          </div>

          {damage && (
            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint">DAMAGED PIXELS:</span>
                <span className="text-paper">{damage.damaged_pixels.toLocaleString()}</span>
              </div>
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint">MEAN PROBABILITY:</span>
                <span className="text-accent">
                  {(damage.mean_damage_probability * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          )}
        </div>

        {/* AI Advisory Grounding */}
        <div className="p-4 flex-1">
          <span className="text-[10px] font-mono text-muted uppercase tracking-wider block mb-2">
            AERION INTELLIGENCE // ADVISORY
          </span>
          <div className="p-3 bg-graphite/50 border border-white/[0.06] rounded">
            <div className="flex items-center gap-1.5 text-status-ai text-[11px] font-mono mb-2">
              <span className="material-symbols-outlined text-[16px]">psychology</span>
              <span>ADVISORY ONLY</span>
            </div>
            <p className="text-[11px] text-muted leading-relaxed">
              Operator verification is required before field dispatch. Siamese damage masks reflect spatial change probability and must be corroborated by ground teams.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
};
