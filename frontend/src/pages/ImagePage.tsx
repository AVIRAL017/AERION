import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { analysisApi } from '../api';
import { AERIONAnalysisResultData } from '../types';
import { UploadModal } from '../components/UploadModal';
import { AnalysisHistoryModal } from '../components/AnalysisHistoryModal';
import { downloadAuthenticatedArtifact } from '../utils/download';
import { API_BASE } from '../api/client';

export const ImagePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeResult, setActiveResult] = useState<AERIONAnalysisResultData | null>(null);
  const [rawImageUrl, setRawImageUrl] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'annotated' | 'raw'>('annotated');
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [uploadSourceType, setUploadSourceType] = useState<'drone_image' | 'satellite_image'>('drone_image');
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // BUG E & G: Presentation Controls
  const [densityMode, setDensityMode] = useState<'normal' | 'dense'>('normal');
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  const [showDetectionIds, setShowDetectionIds] = useState<boolean>(false);
  const [showConfidence, setShowConfidence] = useState<boolean>(true);
  const [zoomScale, setZoomScale] = useState<number>(1.0);
  const [selectedDet, setSelectedDet] = useState<any | null>(null);

  // Restore analysis if analysis_id query parameter is present
  useEffect(() => {
    const analysisIdParam = searchParams.get('analysis_id');
    if (!analysisIdParam) return;

    const restoreAnalysis = async () => {
      setIsLoading(true);
      try {
        const resp = await analysisApi.getById(analysisIdParam);
        if (resp.success && resp.data) {
          setActiveResult(resp.data);
          setViewMode('annotated');
        }
      } catch (err) {
        console.warn(`Could not restore image analysis ${analysisIdParam}:`, err);
      } finally {
        setIsLoading(false);
      }
    };

    restoreAnalysis();
  }, [searchParams]);

  // Compute class counts
  const detections = activeResult?.detections || [];
  const classCounts = detections.reduce<Record<string, number>>((acc, d) => {
    const cname = d.class_name || 'unknown';
    acc[cname] = (acc[cname] || 0) + 1;
    return acc;
  }, {});

  const handleDownloadAnnotated = async () => {
    if (!activeResult) return;
    const artKey = activeResult.annotated_artifact?.artifact_key;
    if (!artKey) return;
    setIsDownloading(true);
    try {
      await downloadAuthenticatedArtifact(
        `${API_BASE}/evidence/${encodeURIComponent(artKey)}`,
        `AERION_PERCEPTION_${activeResult.analysis_id.substring(0, 8)}_annotated.jpg`
      );
    } catch (e: any) {
      alert(e.message || 'Download failed');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDownloadOriginal = async () => {
    if (!activeResult) return;
    if (rawImageUrl) {
      const a = document.createElement('a');
      a.href = rawImageUrl;
      a.download = `AERION_ORIGINAL_${activeResult.analysis_id.substring(0, 8)}.jpg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      return;
    }
    const srcKey = activeResult.source_artifact?.artifact_key;
    if (srcKey) {
      setIsDownloading(true);
      try {
        await downloadAuthenticatedArtifact(
          `${API_BASE}/evidence/${encodeURIComponent(srcKey)}`,
          `AERION_ORIGINAL_${activeResult.analysis_id.substring(0, 8)}.jpg`
        );
      } catch (e: any) {
        alert(e.message || 'Original image download failed');
      } finally {
        setIsDownloading(false);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-graphite">
      {/* Top Telemetry Header */}
      <header className="min-h-[48px] border-b border-white/[0.06] bg-panel flex items-center justify-between px-4 sm:px-6 py-1.5 flex-shrink-0 z-10 gap-3 overflow-x-auto custom-scrollbar">
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-accent text-lg">image_search</span>
            <span className="font-mono text-xs font-bold text-paper uppercase tracking-wider">
              AERION // STANDALONE IMAGE PERCEPTION
            </span>
          </div>
          <span className="px-2 py-0.5 rounded bg-elevated border border-white/[0.08] text-[10px] font-mono text-muted">
            ZERO-DEPENDENCY PERCEPTION PIPELINE
          </span>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {activeResult && (
            <Link
              to={`/situations/00000000-0000-0000-0000-000000000001/report?analysis_id=${encodeURIComponent(activeResult.analysis_id)}`}
              className="px-2.5 py-1 rounded bg-elevated border border-white/[0.08] text-muted hover:text-accent hover:border-accent/40 text-[10px] font-mono flex items-center gap-1 transition-all"
              title="View deterministic operational situation report"
            >
              <span className="material-symbols-outlined text-[13px]">description</span>
              <span>OPERATIONAL REPORT</span>
            </Link>
          )}

          <button
            onClick={() => setIsHistoryOpen(true)}
            className="px-2.5 py-1 rounded bg-elevated/80 border border-white/[0.1] text-muted hover:text-accent hover:border-accent/40 text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer"
            title="View past analysis history"
          >
            <span className="material-symbols-outlined text-[13px]">history</span>
            <span>HISTORY</span>
          </button>

          <button
            onClick={() => { setUploadSourceType('drone_image'); setIsUploadOpen(true); }}
            className="px-3 py-1 rounded bg-accent text-graphite font-bold text-[10px] font-mono hover:bg-accent/90 transition-all flex items-center gap-1.5 cursor-pointer shadow"
          >
            <span className="material-symbols-outlined text-[14px]">flight</span>
            <span>INGEST DRONE IMAGE</span>
          </button>

          <button
            onClick={() => { setUploadSourceType('satellite_image'); setIsUploadOpen(true); }}
            className="px-3 py-1 rounded bg-elevated border border-white/[0.1] text-paper hover:border-accent hover:text-accent font-mono text-[10px] transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <span className="material-symbols-outlined text-[14px]">satellite_alt</span>
            <span>INGEST SATELLITE IMAGE</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left / Center: Image Canvas & Viewport */}
        <div className="flex-1 flex flex-col bg-[#07090C] overflow-hidden relative">
          {/* Canvas Subheader */}
          <div className="h-10 border-b border-white/[0.06] bg-graphite/60 flex items-center justify-between px-4 flex-shrink-0">
            <div className="flex items-center gap-3 font-mono text-[11px]">
              <span className="text-muted">SOURCE:</span>
              <span className="text-paper uppercase">{activeResult?.source_type || 'AERIAL IMAGE'}</span>
              {activeResult?.analysis_id && (
                <>
                  <span className="text-faint">|</span>
                  <span className="text-muted">ID:</span>
                  <span className="text-accent">{activeResult.analysis_id.substring(0, 8)}...</span>
                </>
              )}
            </div>

            {activeResult && (
              <div className="flex items-center gap-2">
                {/* Density Mode Switcher */}
                <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5">
                  <button
                    onClick={() => setDensityMode('normal')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer ${
                      densityMode === 'normal' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                    }`}
                    title="Normal presentation: bounding boxes with labels"
                  >
                    NORMAL
                  </button>
                  <button
                    onClick={() => setDensityMode('dense')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer ${
                      densityMode === 'dense' ? 'bg-status-warning text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                    }`}
                    title="Dense scene mode: clean boxes to avoid overlapping clutter"
                  >
                    DENSE
                  </button>
                </div>

                {/* Layer Toggles */}
                <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5 gap-0.5">
                  <button
                    onClick={() => setShowBoxes(!showBoxes)}
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-all cursor-pointer ${
                      showBoxes ? 'text-accent font-bold' : 'text-faint'
                    }`}
                  >
                    BOXES: {showBoxes ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowLabels(!showLabels)}
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-all cursor-pointer ${
                      showLabels ? 'text-accent font-bold' : 'text-faint'
                    }`}
                  >
                    LABELS: {showLabels ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowConfidence(!showConfidence)}
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-all cursor-pointer ${
                      showConfidence ? 'text-accent font-bold' : 'text-faint'
                    }`}
                  >
                    CONF: {showConfidence ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowDetectionIds(!showDetectionIds)}
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-all cursor-pointer ${
                      showDetectionIds ? 'text-accent font-bold' : 'text-faint'
                    }`}
                  >
                    IDS: {showDetectionIds ? 'ON' : 'OFF'}
                  </button>
                </div>

                {/* Zoom Controls */}
                <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5">
                  <button
                    onClick={() => setZoomScale((z) => Math.max(0.5, z - 0.25))}
                    className="px-1.5 py-0.5 text-[11px] font-mono text-muted hover:text-paper cursor-pointer"
                    title="Zoom Out"
                  >
                    -
                  </button>
                  <span className="px-1 text-[9px] font-mono text-muted">{Math.round(zoomScale * 100)}%</span>
                  <button
                    onClick={() => setZoomScale((z) => Math.min(3.0, z + 0.25))}
                    className="px-1.5 py-0.5 text-[11px] font-mono text-muted hover:text-paper cursor-pointer"
                    title="Zoom In"
                  >
                    +
                  </button>
                  <button
                    onClick={() => setZoomScale(1.0)}
                    className="px-1 text-[9px] font-mono text-accent hover:underline cursor-pointer"
                    title="Reset Zoom"
                  >
                    RESET
                  </button>
                </div>

                {/* View Mode Switcher */}
                <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5">
                  <button
                    onClick={() => setViewMode('annotated')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer ${
                      viewMode === 'annotated'
                        ? 'bg-accent text-graphite font-bold shadow'
                        : 'text-muted hover:text-paper'
                    }`}
                  >
                    ANNOTATED
                  </button>
                  <button
                    onClick={() => setViewMode('raw')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer ${
                      viewMode === 'raw'
                        ? 'bg-accent text-graphite font-bold shadow'
                        : 'text-muted hover:text-paper'
                    }`}
                  >
                    RAW
                  </button>
                </div>

                {/* PRIMARY: Download Annotated Image */}
                {activeResult.annotated_artifact ? (
                  <button
                    onClick={handleDownloadAnnotated}
                    disabled={isDownloading}
                    className="px-2.5 py-1 rounded bg-accent text-graphite hover:bg-accent/90 text-[10px] font-mono font-bold flex items-center gap-1.5 shadow transition-all cursor-pointer disabled:opacity-50"
                    title="Download high-resolution annotated image with verified model detections"
                  >
                    <span className="material-symbols-outlined text-[13px]">download</span>
                    <span>{isDownloading ? 'DOWNLOADING...' : 'DOWNLOAD ANNOTATED IMAGE'}</span>
                  </button>
                ) : (
                  <button
                    disabled
                    className="px-2.5 py-1 rounded bg-elevated/40 border border-white/[0.06] text-muted/60 text-[10px] font-mono font-medium flex items-center gap-1.5 cursor-not-allowed opacity-60"
                    title="Annotated visual artifact is unavailable for this analysis"
                  >
                    <span className="material-symbols-outlined text-[13px]">block</span>
                    <span>ANNOTATED ARTIFACT UNAVAILABLE</span>
                  </button>
                )}

                {/* SECONDARY: Download Original Image */}
                <button
                  onClick={handleDownloadOriginal}
                  disabled={isDownloading || (!rawImageUrl && !activeResult.source_artifact?.artifact_key)}
                  className="px-2.5 py-1 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[10px] font-mono flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Download unmodified original source image"
                >
                  <span className="material-symbols-outlined text-[13px]">photo</span>
                  <span>DOWNLOAD ORIGINAL IMAGE</span>
                </button>
              </div>
            )}
          </div>

          {/* Canvas Area */}
          <div className="flex-1 relative flex items-center justify-center p-4 overflow-hidden telemetry-grid">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center font-mono text-xs text-muted">
                <span className="material-symbols-outlined text-accent animate-spin text-3xl mb-2">progress_activity</span>
                <span>LOADING ANALYSIS RESULT...</span>
              </div>
            ) : activeResult ? (
              <div className="relative max-w-full max-h-full flex items-center justify-center border border-white/[0.08] rounded shadow-2xl overflow-hidden bg-black">
                <div
                  className="transition-transform duration-150 ease-out flex items-center justify-center max-w-full max-h-full"
                  style={{ transform: `scale(${zoomScale})` }}
                >
                  {viewMode === 'annotated' && activeResult.annotated_image_base64 && densityMode === 'normal' ? (
                    <img
                      src={`data:image/jpeg;base64,${activeResult.annotated_image_base64}`}
                      alt="Authoritative Annotated Perception"
                      className="max-w-full max-h-[75vh] object-contain select-none"
                    />
                  ) : (
                    <div className="relative max-w-full max-h-full flex items-center justify-center">
                      <img
                        src={rawImageUrl || (activeResult.annotated_image_base64 ? `data:image/jpeg;base64,${activeResult.annotated_image_base64}` : '')}
                        alt="Aerial Ingest"
                        className="max-w-full max-h-[75vh] object-contain select-none"
                      />
                      {/* Density Mode / Toggleable SVG Overlay Layer */}
                      {showBoxes && activeResult.image_width && activeResult.image_height && (
                        <svg
                          className="absolute inset-0 w-full h-full pointer-events-auto"
                          viewBox={`0 0 ${activeResult.image_width} ${activeResult.image_height}`}
                          preserveAspectRatio="xMidYMid meet"
                        >
                          {detections.map((det: any, idx: number) => {
                            if (!det.bbox) return null;
                            const bx = det.bbox.x1;
                            const by = det.bbox.y1;
                            const bw = det.bbox.x2 - det.bbox.x1;
                            const bh = det.bbox.y2 - det.bbox.y1;
                            const isSelected = selectedDet === det;
                            const shortClass = det.class_name.toUpperCase().replace(/_/g, ' ');
                            const confStr = showConfidence ? ` ${Math.round(det.confidence * 100)}%` : '';
                            const idStr = showDetectionIds ? ` #${idx + 1}` : '';
                            const labelText = `${shortClass}${confStr}${idStr}`;
                            const badgeW = Math.max(50, labelText.length * 7.5 + 10);
                            const isNearTop = by < 22;
                            const badgeY = isNearTop ? by + 2 : by - 18;
                            const textY = isNearTop ? by + 14 : by - 5;

                            return (
                              <g
                                key={`det-${idx}`}
                                onClick={() => setSelectedDet(det)}
                                className="cursor-pointer"
                              >
                                <rect
                                  x={bx}
                                  y={by}
                                  width={bw}
                                  height={bh}
                                  fill={isSelected ? 'rgba(56, 213, 245, 0.25)' : 'none'}
                                  stroke="#38D5F5"
                                  strokeWidth={Math.max(1.5, (activeResult.image_width || 1000) / 600)}
                                />
                                {showLabels && (densityMode === 'normal' || isSelected || bw >= 45) && (
                                  <>
                                    <rect
                                      x={bx}
                                      y={badgeY}
                                      width={badgeW}
                                      height={16}
                                      fill={isSelected ? '#38D5F5' : 'rgba(7, 9, 12, 0.85)'}
                                      stroke="#38D5F5"
                                      strokeWidth={1}
                                      rx={2}
                                    />
                                    <text
                                      x={bx + 3}
                                      y={textY}
                                      fill={isSelected ? '#07090C' : '#38D5F5'}
                                      fontSize={Math.max(9, (activeResult.image_width || 1000) / 105)}
                                      fontFamily="monospace"
                                      fontWeight="bold"
                                    >
                                      {labelText}
                                    </text>
                                  </>
                                )}
                              </g>
                            );
                          })}
                        </svg>
                      )}
                    </div>
                  )}
                </div>

                {/* Overlays / Labels */}
                <div className="absolute top-2 left-2 flex items-center gap-1.5 pointer-events-none">
                  <span className="px-2 py-0.5 rounded bg-graphite/90 border border-white/[0.15] text-[9px] font-mono text-paper">
                    {viewMode === 'annotated' ? 'AUTHORITATIVE ANNOTATED ARTIFACT' : 'RAW AERIAL INPUT'}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-graphite/90 border border-accent/40 text-[9px] font-mono text-accent">
                    COUNT: {detections.length}
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center max-w-md">
                <div className="w-14 h-14 rounded-full bg-elevated/70 border border-white/[0.08] flex items-center justify-center text-muted mb-4">
                  <span className="material-symbols-outlined text-[28px]">image</span>
                </div>
                <h3 className="text-sm font-semibold font-mono text-paper mb-1">
                  NO ACTIVE IMAGE LOADED
                </h3>
                <p className="text-xs text-muted leading-relaxed mb-6 font-mono">
                  Ingest an aerial drone or satellite image to run deterministic object perception inference without requiring external geocontext or location services.
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => { setUploadSourceType('drone_image'); setIsUploadOpen(true); }}
                    className="px-4 py-2 rounded bg-accent text-graphite font-mono font-bold text-xs hover:bg-accent/90 transition-all flex items-center gap-1.5 shadow cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px]">flight</span>
                    <span>INGEST DRONE IMAGE</span>
                  </button>
                  <button
                    onClick={() => { setUploadSourceType('satellite_image'); setIsUploadOpen(true); }}
                    className="px-4 py-2 rounded bg-elevated border border-white/[0.1] text-paper font-mono text-xs hover:border-accent hover:text-accent transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px]">satellite_alt</span>
                    <span>INGEST SATELLITE IMAGE</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Perception Intelligence Panel */}
        <aside className="w-80 flex-shrink-0 bg-panel border-l border-white/[0.06] flex flex-col overflow-y-auto custom-scrollbar">
          <div className="p-4 border-b border-white/[0.06]">
            <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase mb-2">
              PERCEPTION SUMMARY
            </h2>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-mono font-bold text-accent">
                {detections.length}
              </span>
              <span className="text-xs font-mono text-muted uppercase">
                TOTAL DETECTIONS
              </span>
            </div>
            <p className="text-[11px] font-mono text-faint mt-1">
              FROZEN YOLOV8 PERCEPTION RUNTIME (CONFIDENCE &ge; 0.25)
            </p>
          </div>

          {/* Detections by Category */}
          <div className="p-4 border-b border-white/[0.06] space-y-3">
            <h3 className="text-[10px] font-mono text-muted uppercase tracking-wider">
              DETECTIONS BY CATEGORY
            </h3>

            {Object.keys(classCounts).length > 0 ? (
              <div className="space-y-1.5">
                {Object.entries(classCounts).map(([cls, count]) => (
                  <div
                    key={cls}
                    className="flex items-center justify-between p-2 rounded bg-graphite/40 border border-white/[0.04] text-xs font-mono"
                  >
                    <span className="text-paper capitalize">{cls}</span>
                    <span className="px-2 py-0.5 rounded bg-accent/15 border border-accent/30 text-accent font-bold">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-3 bg-graphite/40 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint">
                  {activeResult ? 'NO DETECTIONS FOUND (COUNT = 0)' : 'AWAITING IMAGE INGEST'}
                </span>
              </div>
            )}
          </div>

          {/* Detections List */}
          <div className="p-4 flex-1 flex flex-col space-y-3 overflow-y-auto custom-scrollbar">
            <div className="flex items-center justify-between">
              <h3 className="text-[10px] font-mono text-muted uppercase tracking-wider">
                CONFIRMED DETECTIONS ({detections.length})
              </h3>
            </div>

            {detections.length > 0 ? (
              <div className="space-y-1.5">
                {detections.map((d, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded bg-graphite/30 border border-white/[0.04] text-[11px] font-mono flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-faint text-[9px]">#{idx + 1}</span>
                      <span className="text-paper font-semibold capitalize">{d.class_name}</span>
                    </div>
                    <span className="text-accent text-[10px]">
                      {(d.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 font-mono text-xs text-faint">
                {activeResult ? 'ZERO DETECTIONS RECORDED' : 'NO DATA AVAILABLE'}
              </div>
            )}
          </div>

          {/* Footer Note */}
          <div className="p-4 border-t border-white/[0.06] bg-graphite/30">
            <div className="flex items-center gap-1.5 text-accent text-[10px] font-mono mb-1">
              <span className="material-symbols-outlined text-[13px]">verified</span>
              <span>AUDIT-GRADE TRACEABILITY</span>
            </div>
            <p className="text-[10px] text-faint leading-relaxed font-mono">
              Inference runs strictly on frozen perception models. No hallucinations, no heuristic fallbacks.
            </p>
          </div>
        </aside>
      </div>

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        defaultMode={uploadSourceType}
        onAnalysisSuccess={(res, meta) => {
          setActiveResult(res);
          if (meta?.imageUrl) setRawImageUrl(meta.imageUrl);
          setViewMode('annotated');
          if (res.analysis_id) {
            setSearchParams({ analysis_id: res.analysis_id });
          }
        }}
      />

      {/* Analysis History Modal */}
      <AnalysisHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        currentMode="border"
        onSelectAnalysis={async (item) => {
          const targetId = item.analysis_id || item.job_id;
          if (targetId) {
            setSearchParams({ analysis_id: targetId });
            try {
              const resp = await analysisApi.getById(targetId);
              if (resp.success && resp.data) {
                setActiveResult(resp.data);
                setViewMode('annotated');
              }
            } catch (err) {
              console.warn('Could not reopen image analysis:', err);
            }
          }
        }}
      />
    </div>
  );
};
