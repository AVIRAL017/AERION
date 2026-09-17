import React, { useEffect, useState, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { situationsApi, analysisApi, externalApi } from '../api';
import { DamageSummary, AERIONAnalysisResultData, Situation, LocationProvenance, RouteOption, ShelterData } from '../types';
import { UploadModal } from '../components/UploadModal';
import { OperatorLocationModal } from '../components/OperatorLocationModal';
import { AnalysisHistoryModal } from '../components/AnalysisHistoryModal';
import { downloadAuthenticatedArtifact } from '../utils/download';
import { API_BASE } from '../api/client';

export const DisasterPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sliderPosition, setSliderPosition] = useState<number>(50);
  const [situation, setSituation] = useState<Situation | null>(null);
  const [damage, setDamage] = useState<DamageSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);
  const [operatorLocation, setOperatorLocation] = useState<LocationProvenance | null>(null);
  const [weatherData, setWeatherData] = useState<any | null>(null);
  const [weatherLoading, setWeatherLoading] = useState<boolean>(false);
  const [activeAnalysisResult, setActiveAnalysisResult] = useState<AERIONAnalysisResultData | null>(null);
  const [customPreUrl, setCustomPreUrl] = useState<string | null>(null);
  const [customPostUrl, setCustomPostUrl] = useState<string | null>(null);
  const [showDamageOverlay, setShowDamageOverlay] = useState<boolean>(true);
  const [displayMode, setDisplayMode] = useState<'split' | 'side-by-side' | 'pre' | 'post' | 'damage'>('split');
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [shelters, setShelters] = useState<ShelterData[]>([]);
  const [routesLoading, setRoutesLoading] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchDisasterData = async () => {
      setIsLoading(true);
      try {
        const listRes = await situationsApi.list();
        if (listRes.success && listRes.data && listRes.data.length > 0) {
          const active = listRes.data.find(s => s.situation_type === 'DISASTER_RESPONSE') || listRes.data[0];
          setSituation(active);
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

  // Restore analysis from URL search parameter (e.g. ?analysis_id=UUID)
  useEffect(() => {
    const analysisIdParam = searchParams.get('analysis_id');
    if (!analysisIdParam) return;

    const restoreAnalysis = async () => {
      try {
        const resp = await analysisApi.getById(analysisIdParam);
        if (resp.success && resp.data) {
          const data = resp.data;
          setActiveAnalysisResult(data);
          if (data.damage_analysis) {
            const dmg = data.damage_analysis;
            const percentage = dmg.damage_percentage || (dmg.damage_ratio ? dmg.damage_ratio * 100 : 0);
            let classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC' = 'NO_DAMAGE';
            if (percentage >= 50) classification = 'CATASTROPHIC';
            else if (percentage >= 25) classification = 'SEVERE';
            else if (percentage >= 10) classification = 'MODERATE';
            else if (percentage > 0) classification = 'MINOR';

            setDamage({
              damage_percentage: percentage,
              damaged_pixels: dmg.damage_pixels || 0,
              total_pixels: dmg.total_pixels || 0,
              mean_damage_probability: dmg.probability_mean || 0,
              classification,
            });
          }
        }
      } catch (err) {
        console.warn(`Could not restore disaster analysis ${analysisIdParam}:`, err);
      }
    };

    restoreAnalysis();
  }, [searchParams]);

  // Fetch live weather when valid operator location is provided
  useEffect(() => {
    if (!operatorLocation || typeof operatorLocation.latitude !== 'number' || typeof operatorLocation.longitude !== 'number') {
      setWeatherData(null);
      return;
    }

    const fetchWeather = async () => {
      setWeatherLoading(true);
      try {
        const resp = await externalApi.getWeather(operatorLocation.latitude, operatorLocation.longitude);
        if (resp.success && resp.data) {
          setWeatherData(resp.data);
        } else {
          setWeatherData({ status: 'UNAVAILABLE' });
        }
      } catch {
        setWeatherData({ status: 'UNAVAILABLE' });
      } finally {
        setWeatherLoading(false);
      }
    };

    fetchWeather();
  }, [operatorLocation]);

  // Fetch verified routes and shelters when disaster situation is available
  useEffect(() => {
    if (!situation?.id) return;
    const fetchEvacData = async () => {
      setRoutesLoading(true);
      try {
        const routesRes = await situationsApi.getRoutes(situation.id);
        if (routesRes.success && routesRes.data) {
          setRoutes(routesRes.data);
        }
        if (situation.shelters) {
          setShelters(situation.shelters);
        }
      } catch (err) {
        console.warn('Could not fetch disaster routes/shelters:', err);
      } finally {
        setRoutesLoading(false);
      }
    };
    fetchEvacData();
  }, [situation]);

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

  // Determine current pre/post image display
  const preImgUrl = customPreUrl || damage?.pre_image_url;
  const postImgUrl = customPostUrl || damage?.post_image_url;

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-graphite">
      {/* ============================================================ */}
      {/* CENTRAL BI-TEMPORAL SPLIT-CURTAIN WORKSPACE                  */}
      {/* ============================================================ */}
      <section className="flex-1 relative flex flex-col border-r border-white/[0.06] overflow-hidden">
        {/* Workspace Toolbar */}
        <div className="h-11 px-5 flex items-center justify-between border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20">
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span className="text-muted uppercase">ANALYSIS MODE:</span>
            <span className="text-paper font-medium">BI-TEMPORAL DAMAGE WORKSPACE</span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${
              activeAnalysisResult
                ? 'bg-status-critical/15 text-status-critical border border-status-critical/30'
                : 'bg-accent/10 text-accent border border-accent/20'
            }`}>
              {activeAnalysisResult ? 'SIAMESE INFERENCE VERIFIED' : 'SIAMESE FUSED'}
            </span>

            {/* Location Provenance Badge / Trigger */}
            {operatorLocation ? (
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="px-2 py-0.5 rounded bg-status-ai/15 border border-status-ai/30 text-status-ai text-[10px] flex items-center gap-1 hover:bg-status-ai/25 transition-all"
                title="Operator-provided approximate location active"
              >
                <span className="material-symbols-outlined text-[13px]">pin_drop</span>
                <span className="font-bold">
                  {operatorLocation.label || `[${operatorLocation.latitude.toFixed(2)}, ${operatorLocation.longitude.toFixed(2)}]`}
                </span>
                <span className="text-[9px] bg-status-ai/20 px-1 rounded text-paper">APPROXIMATE</span>
              </button>
            ) : (
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="px-2 py-0.5 rounded bg-elevated/80 border border-white/[0.1] text-muted hover:text-accent hover:border-accent/40 text-[10px] flex items-center gap-1 transition-all"
                title="No embedded GPS in damage pair. Click to provide approximate coordinates."
              >
                <span className="material-symbols-outlined text-[13px]">add_location_alt</span>
                <span>GEO-CONTEXT: UNAVAILABLE</span>
              </button>
            )}

            {/* Operational Situation Report Navigation */}
            <Link
              to={`/situations/${situation?.id || '00000000-0000-0000-0000-000000000002'}/report${activeAnalysisResult?.analysis_id ? `?analysis_id=${activeAnalysisResult.analysis_id}` : ''}`}
              className="px-2.5 py-1 rounded bg-status-ai/20 border border-status-ai/40 text-status-ai hover:bg-status-ai/30 transition-all flex items-center gap-1 text-[10px] font-mono font-semibold"
              title="View Deterministic Situation Report & Mistral AI Advisory"
            >
              <span className="material-symbols-outlined text-[13px]">description</span>
              <span>OPERATIONAL REPORT</span>
            </Link>

            {/* History Drawer Trigger */}
            <button
              onClick={() => setIsHistoryOpen(true)}
              className="px-2.5 py-1 rounded bg-elevated/80 border border-white/[0.1] text-muted hover:text-accent hover:border-accent/40 text-[10px] font-mono flex items-center gap-1 transition-all"
              title="View past analysis history and reopen analyses"
            >
              <span className="material-symbols-outlined text-[13px]">history</span>
              <span>HISTORY</span>
            </button>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px]">
            {/* View Mode Switcher */}
            {preImgUrl && postImgUrl && (
              <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5">
                <button
                  onClick={() => setDisplayMode('split')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'split' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  SPLIT SLIDER
                </button>
                <button
                  onClick={() => setDisplayMode('side-by-side')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'side-by-side' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  SIDE-BY-SIDE
                </button>
                <button
                  onClick={() => setDisplayMode('pre')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'pre' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  PRE (T0)
                </button>
                <button
                  onClick={() => setDisplayMode('post')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'post' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  POST (T1)
                </button>
                {activeAnalysisResult?.damage_mask_base64 && (
                  <button
                    onClick={() => setDisplayMode('damage')}
                    className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                      displayMode === 'damage' ? 'bg-status-critical text-white font-bold shadow' : 'text-muted hover:text-paper'
                    }`}
                  >
                    DAMAGE MASK
                  </button>
                )}
              </div>
            )}

            {activeAnalysisResult?.damage_mask_base64 && (displayMode === 'split' || displayMode === 'side-by-side' || displayMode === 'post') && (
              <button
                onClick={() => setShowDamageOverlay(!showDamageOverlay)}
                className={`px-2.5 py-1 rounded border text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer ${
                  showDamageOverlay
                    ? 'bg-status-critical/20 border-status-critical text-status-critical'
                    : 'bg-elevated border-white/[0.1] text-muted hover:text-paper'
                }`}
              >
                <span className="material-symbols-outlined text-[13px]">layers</span>
                <span>OVERLAY: {showDamageOverlay ? 'ON' : 'OFF'}</span>
              </button>
            )}
            {displayMode === 'split' && (
              <span className="text-muted mr-2">SPLIT: {Math.round(sliderPosition)}%</span>
            )}
            <button
              onClick={() => setIsUploadOpen(true)}
              className="px-3 py-1 rounded bg-accent text-graphite font-bold text-[10px] hover:bg-accent/90 transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[14px]">compare</span>
              <span>INGEST DAMAGE PAIR</span>
            </button>
          </div>
        </div>

        {/* Bi-Temporal Split View Canvas */}
        <div
          ref={containerRef}
          onMouseMove={displayMode === 'split' ? handleMouseMove : undefined}
          className={`flex-1 relative bg-[#07090C] telemetry-grid overflow-hidden select-none ${displayMode === 'split' ? 'cursor-ew-resize' : ''}`}
        >
          {preImgUrl && postImgUrl ? (
            <div className="relative w-full h-full">
              {displayMode === 'pre' && (
                <img
                  src={preImgUrl}
                  alt="Pre-Disaster Baseline"
                  className="w-full h-full object-cover"
                />
              )}

              {displayMode === 'post' && (
                <div className="relative w-full h-full">
                  <img
                    src={postImgUrl}
                    alt="Post-Disaster Observation"
                    className="w-full h-full object-cover"
                  />
                  {showDamageOverlay && activeAnalysisResult?.damage_mask_base64 && (
                    <img
                      src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                      alt="Translucent Damage Overlay"
                      className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-75 pointer-events-none"
                    />
                  )}
                </div>
              )}

              {displayMode === 'damage' && activeAnalysisResult?.damage_mask_base64 && (
                <img
                  src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                  alt="Siamese Damage Mask"
                  className="w-full h-full object-cover"
                />
              )}

              {displayMode === 'side-by-side' && (
                <div className="w-full h-full grid grid-cols-2 gap-2 p-2">
                  {/* Left: Pre-Disaster */}
                  <div className="relative w-full h-full border border-white/[0.08] rounded overflow-hidden flex flex-col">
                    <div className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded bg-graphite/80 border border-white/[0.1] text-[9px] font-mono text-muted">
                      PRE-DISASTER (T0)
                    </div>
                    <img
                      src={preImgUrl}
                      alt="Pre-Disaster Baseline"
                      className="w-full h-full object-cover"
                    />
                  </div>
                  {/* Right: Post-Disaster with optional overlay */}
                  <div className="relative w-full h-full border border-white/[0.08] rounded overflow-hidden flex flex-col">
                    <div className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded bg-graphite/80 border border-white/[0.1] text-[9px] font-mono text-accent">
                      POST-DISASTER (T1) {showDamageOverlay && activeAnalysisResult?.damage_mask_base64 ? '+ OVERLAY' : ''}
                    </div>
                    <img
                      src={postImgUrl}
                      alt="Post-Disaster Observation"
                      className="w-full h-full object-cover"
                    />
                    {showDamageOverlay && activeAnalysisResult?.damage_mask_base64 && (
                      <img
                        src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                        alt="Translucent Damage Overlay"
                        className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-75 pointer-events-none"
                      />
                    )}
                  </div>
                </div>
              )}

              {displayMode === 'split' && (
                <>
                  {/* Post-Disaster Layer (Underneath / Right side) */}
                  <div className="absolute inset-0 w-full h-full">
                    <img
                      src={postImgUrl}
                      alt="Post-Disaster Observation"
                      className="w-full h-full object-cover pointer-events-none"
                    />
                    {showDamageOverlay && activeAnalysisResult?.damage_mask_base64 && (
                      <img
                        src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                        alt="Translucent Damage Overlay"
                        className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-75 pointer-events-none"
                      />
                    )}
                  </div>

                  {/* Pre-Disaster Layer (Clipped curtain / Left side) */}
                  <div
                    className="slider-curtain"
                    style={{ width: `${sliderPosition}%` }}
                  >
                    <img
                      src={preImgUrl}
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
                </>
              )}
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
              <button
                onClick={() => setIsUploadOpen(true)}
                className="mt-4 px-3 py-1.5 rounded bg-accent/15 border border-accent/40 text-accent text-xs font-mono hover:bg-accent/25 transition-all flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-[15px]">compare</span>
                <span>INGEST DAMAGE PAIR</span>
              </button>
            </div>
          )}

          {/* Left/Right Overlays & Evidence Download */}
          <div className="absolute bottom-4 left-4 z-20 pointer-events-none">
            <span className="px-2 py-1 rounded bg-graphite/80 border border-white/[0.08] text-[10px] font-mono text-muted">
              PRE-DISASTER BASELINE (T0)
            </span>
          </div>
          <div className="absolute bottom-4 right-4 z-20 flex items-center gap-2">
            <span className="px-2 py-1 rounded bg-graphite/80 border border-white/[0.08] text-[10px] font-mono text-accent">
              {showDamageOverlay && activeAnalysisResult?.damage_mask_base64
                ? 'POST-DISASTER WITH DAMAGE OVERLAY (T1)'
                : 'POST-DISASTER OBSERVATION (T1)'}
            </span>
            {activeAnalysisResult?.damage_artifact && (
              <button
                disabled={isDownloading}
                onClick={async () => {
                  const artKey = activeAnalysisResult.damage_artifact?.artifact_key;
                  if (!artKey) return;
                  setIsDownloading(true);
                  try {
                    await downloadAuthenticatedArtifact(
                      `${API_BASE}/evidence/${artKey}`,
                      `AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_damage_mask.jpg`
                    );
                  } catch (e: any) {
                    alert(e.message || 'Download failed');
                  } finally {
                    setIsDownloading(false);
                  }
                }}
                className="px-2 py-1 rounded bg-accent text-graphite hover:bg-accent/90 disabled:opacity-50 text-[10px] font-mono font-bold flex items-center gap-1 shadow transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">download</span>
                <span>{isDownloading ? 'DOWNLOADING...' : 'DOWNLOAD DAMAGE MASK'}</span>
              </button>
            )}
            {postImgUrl && (
              <a
                href={postImgUrl}
                download={`AERION_${activeAnalysisResult?.analysis_id?.substring(0, 8) || 'disaster'}_post_original.jpg`}
                className="px-2 py-1 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[10px] font-mono flex items-center gap-1 shadow transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[12px]">download</span>
                <span>DOWNLOAD POST IMAGE</span>
              </a>
            )}
            {preImgUrl && (
              <a
                href={preImgUrl}
                download={`AERION_${activeAnalysisResult?.analysis_id?.substring(0, 8) || 'disaster'}_pre_original.jpg`}
                className="px-2 py-1 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[10px] font-mono flex items-center gap-1 shadow transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[12px]">download</span>
                <span>DOWNLOAD PRE IMAGE</span>
              </a>
            )}
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
            {activeAnalysisResult?.damage_analysis ? (
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-mono font-bold text-status-critical">
                  {activeAnalysisResult.damage_analysis.damage_percentage.toFixed(1)}%
                </span>
                <span className="text-xs font-mono text-accent uppercase">
                  {activeAnalysisResult.damage_analysis.damage_percentage > 50
                    ? 'SEVERE'
                    : activeAnalysisResult.damage_analysis.damage_percentage > 20
                    ? 'MODERATE'
                    : activeAnalysisResult.damage_analysis.damage_percentage > 0
                    ? 'MINOR'
                    : 'NO_DAMAGE'}
                </span>
              </div>
            ) : damage ? (
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

          {activeAnalysisResult?.damage_analysis ? (
            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint" title="Damaged pixels identified by Siamese model at threshold 0.50">DAMAGED PIXELS:</span>
                <span className="text-paper">{activeAnalysisResult.damage_analysis.damage_pixels.toLocaleString()}</span>
              </div>
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint" title="Total processed pixel area (e.g. 512x512 = 262,144)">TOTAL PIXELS:</span>
                <span className="text-paper">{activeAnalysisResult.damage_analysis.total_pixels.toLocaleString()}</span>
              </div>
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint" title="Scene-wide mean sigmoid activation across all 262,144 pixels">SCENE-WIDE MEAN PROB:</span>
                <span className="text-accent">
                  {(activeAnalysisResult.damage_analysis.probability_mean * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint" title="Damaged pixels / Total pixels (733 / 262,144 = 0.0028)">DAMAGE RATIO:</span>
                <span className="text-paper">
                  {activeAnalysisResult.damage_analysis.damage_ratio.toFixed(4)}
                </span>
              </div>
              <div className="p-2 bg-panel/60 rounded border border-white/[0.04] text-[10px] text-faint leading-tight">
                * Note: Mean probability is computed across the entire image area. The damage ratio (0.0028 ~ 0.3%) represents thresholded pixels where probability &gt; 0.50.
              </div>
            </div>
          ) : damage && (
            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint">DAMAGED PIXELS:</span>
                <span className="text-paper">{damage.damaged_pixels.toLocaleString()}</span>
              </div>
              <div className="flex justify-between p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint">SCENE-WIDE MEAN PROB:</span>
                <span className="text-accent">
                  {(damage.mean_damage_probability * 100).toFixed(1)}%
                </span>
              </div>
              <div className="p-2 bg-panel/60 rounded border border-white/[0.04] text-[10px] text-faint leading-tight">
                * Note: Mean probability is computed across the entire image area.
              </div>
            </div>
          )}
        </div>

        {/* AI Advisory Grounding */}
        <div className="p-4 flex-1 space-y-4">
          {activeAnalysisResult?.pair_validation && (
            <div>
              <span className="text-[10px] font-mono text-muted uppercase tracking-wider block mb-2">
                PAIR COMPATIBILITY VALIDATION
              </span>
              <div className="p-3 bg-graphite/50 border border-white/[0.06] rounded space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-faint">STATUS:</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    activeAnalysisResult.pair_validation.is_compatible
                      ? 'bg-accent/15 text-accent border border-accent/30'
                      : 'bg-status-critical/15 text-status-critical border border-status-critical/30'
                  }`}>
                    {activeAnalysisResult.pair_validation.status}
                  </span>
                </div>
                {activeAnalysisResult.pair_validation.warnings?.map((w: string, idx: number) => (
                  <p key={idx} className="text-status-warning text-[10px] leading-tight">⚠ {w}</p>
                ))}
                {activeAnalysisResult.pair_validation.limitations?.map((l: string, idx: number) => (
                  <p key={idx} className="text-muted text-[10px] leading-tight">• {l}</p>
                ))}
              </div>
            </div>
          )}

          {/* Operational Weather & Geo-Context Card */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-muted uppercase tracking-wider block">
                METEOROLOGICAL OBSERVATIONS
              </span>
              {operatorLocation && (
                <span className="text-[9px] font-mono text-accent">
                  GEO-GROUNDED
                </span>
              )}
            </div>

            {weatherLoading ? (
              <div className="p-3 bg-graphite/50 border border-white/[0.06] rounded font-mono text-[11px] text-muted flex items-center gap-2">
                <span className="material-symbols-outlined text-accent animate-spin text-[16px]">progress_activity</span>
                <span>QUERYING OPEN-METEO OBSERVATION...</span>
              </div>
            ) : operatorLocation && weatherData && weatherData.status !== 'UNAVAILABLE' ? (
              <div className="p-3 bg-graphite/50 border border-white/[0.06] rounded space-y-2 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-faint">CONDITIONS:</span>
                  <span className="text-paper font-bold">{weatherData.conditions || weatherData.condition_description || 'CLEAR'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-faint">TEMPERATURE:</span>
                  <span className="text-accent">{weatherData.temperature_c ?? weatherData.temperature_celsius ?? '--'} °C</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-faint">WIND SPEED:</span>
                  <span className="text-paper">{weatherData.wind_speed_ms ?? weatherData.wind_speed_mps ?? '--'} m/s</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-faint">FLIGHT SUITABILITY:</span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] ${
                    weatherData.flight_suitability === 'OPTIMAL' ? 'bg-accent/20 text-accent' : 'bg-status-warning/20 text-status-warning'
                  }`}>
                    {weatherData.flight_suitability || 'OPTIMAL'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-3 bg-graphite/30 border border-white/[0.06] rounded text-center font-mono space-y-1">
                <span className="text-status-warning text-[11px] block font-bold">
                  WEATHER: UNAVAILABLE
                </span>
                <p className="text-faint text-[10px] leading-tight">
                  {!operatorLocation
                    ? 'No coordinates provided for disaster asset. Click GEO-CONTEXT above to set approximate location.'
                    : 'Weather provider query unavailable or timed out.'}
                </p>
              </div>
            )}
          </div>

          {/* Safe Route & Safe Shelter Assessment */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-muted uppercase tracking-wider block">
                EVACUATION CORRIDORS & SHELTERS
              </span>
              <span className="text-[9px] font-mono text-accent">
                {routes.length > 0 ? `${routes.length} FEASIBLE` : 'ORS BOUNDED'}
              </span>
            </div>

            <div className="p-3 bg-graphite/50 border border-white/[0.06] rounded space-y-2 font-mono text-[11px]">
              {routesLoading ? (
                <div className="text-muted text-[10px] flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-accent animate-spin text-[14px]">progress_activity</span>
                  <span>EVALUATING ROAD NETWORK CORRIDORS...</span>
                </div>
              ) : routes.length > 0 ? (
                <div className="space-y-1.5">
                  {routes.map((r, idx) => (
                    <div key={idx} className="p-2 bg-graphite/60 rounded border border-white/[0.04]">
                      <div className="flex items-center justify-between text-paper font-semibold">
                        <span>{r.name}</span>
                        <span className="text-accent">{r.distance_km} km</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-faint mt-0.5">
                        <span>EST. DURATION: {r.duration_min} MIN</span>
                        <span className="text-status-success">VIABLE</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[10px] text-muted space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-faint">ROUTE ENGINE:</span>
                    <span className="text-paper">OpenRouteService</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-faint">ROAD BLOCKAGE STATUS:</span>
                    <span className="text-status-warning">NOT ESTABLISHED</span>
                  </div>
                  <p className="text-[9px] text-faint leading-tight pt-1 border-t border-white/[0.04]">
                    Corroborated ground data required before establishing road blockages.
                  </p>
                </div>
              )}

              {shelters.length > 0 && (
                <div className="pt-2 border-t border-white/[0.06] space-y-1">
                  <span className="text-[9px] text-muted block font-semibold">REGISTERED SHELTERS:</span>
                  {shelters.slice(0, 3).map((s, idx) => (
                    <div key={idx} className="flex items-center justify-between text-[10px]">
                      <span className="text-paper truncate max-w-[140px]">{s.name}</span>
                      <span className={`text-[9px] px-1 rounded ${s.status === 'OPEN' ? 'text-status-success bg-status-success/10' : 'text-faint'}`}>
                        {s.status} ({s.current_occupancy}/{s.capacity})
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div>
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
        </div>
      </aside>

      {/* Upload Damage Pair Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        defaultMode="damage_pair"
        onAnalysisSuccess={(res, meta) => {
          setActiveAnalysisResult(res);
          if (meta?.preUrl) setCustomPreUrl(meta.preUrl);
          if (meta?.postUrl) setCustomPostUrl(meta.postUrl);
          if (res.damage_analysis) {
            const dmg = res.damage_analysis;
            const percentage = dmg.damage_percentage !== undefined ? dmg.damage_percentage : (dmg.damage_ratio ? dmg.damage_ratio * 100 : 0);
            let classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC' = 'NO_DAMAGE';
            if (percentage >= 50) classification = 'CATASTROPHIC';
            else if (percentage >= 25) classification = 'SEVERE';
            else if (percentage >= 10) classification = 'MODERATE';
            else if (percentage > 0) classification = 'MINOR';

            setDamage({
              damage_percentage: percentage,
              damaged_pixels: dmg.damage_pixels || 0,
              total_pixels: dmg.total_pixels || 0,
              mean_damage_probability: dmg.probability_mean || 0,
              classification,
            });
          }
          if (res.analysis_id) {
            setSearchParams({ analysis_id: res.analysis_id });
          }
        }}
      />

      {/* Analysis History Modal */}
      <AnalysisHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        currentMode="disaster"
        onSelectAnalysis={async (item) => {
          const targetId = item.analysis_id || item.job_id;
          if (targetId) {
            setSearchParams({ analysis_id: targetId });
            try {
              const resp = await analysisApi.getById(targetId);
              if (resp.success && resp.data) {
                setActiveAnalysisResult(resp.data);
                if (resp.data.damage_analysis) {
                  const dmg = resp.data.damage_analysis;
                  const percentage = dmg.damage_percentage || (dmg.damage_ratio ? dmg.damage_ratio * 100 : 0);
                  let classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC' = 'NO_DAMAGE';
                  if (percentage >= 50) classification = 'CATASTROPHIC';
                  else if (percentage >= 25) classification = 'SEVERE';
                  else if (percentage >= 10) classification = 'MODERATE';
                  else if (percentage > 0) classification = 'MINOR';

                  setDamage({
                    damage_percentage: percentage,
                    damaged_pixels: dmg.damage_pixels || 0,
                    total_pixels: dmg.total_pixels || 0,
                    mean_damage_probability: dmg.probability_mean || 0,
                    classification,
                  });
                }
              }
            } catch (err) {
              console.warn('Could not reopen disaster analysis:', err);
            }
          }
        }}
      />

      {/* Operator Location Modal */}
      <OperatorLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        existingLocation={operatorLocation}
        onConfirmLocation={(loc) => {
          setOperatorLocation(loc);
        }}
      />
    </div>
  );
};
