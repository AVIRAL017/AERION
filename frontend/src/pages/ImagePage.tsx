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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Presentation Controls
  const [densityMode, setDensityMode] = useState<'normal' | 'dense'>('normal');
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  const [showDetectionIds, setShowDetectionIds] = useState<boolean>(false);
  const [showConfidence, setShowConfidence] = useState<boolean>(true);
  const [zoomScale, setZoomScale] = useState<number>(1.0);
  const [selectedDet, setSelectedDet] = useState<any | null>(null);
  const [mobileTab, setMobileTab] = useState<'canvas' | 'intelligence'>('canvas');

  // Restore analysis if analysis_id query parameter is present
  useEffect(() => {
    const analysisIdParam = searchParams.get('analysis_id');
    if (!analysisIdParam) return;

    const restoreAnalysis = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const resp = await analysisApi.getById(analysisIdParam);
        if (resp.success && resp.data) {
          setActiveResult(resp.data);
          setViewMode('annotated');
        } else {
          setErrorMessage('Unable to load requested image analysis.');
        }
      } catch (err: any) {
        console.warn(`Could not restore image analysis ${analysisIdParam}:`, err);
        setErrorMessage(err.message || 'Error loading analysis.');
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
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-canvas text-content">
      {/* Top Telemetry Header */}
      <header className="min-h-[52px] border-b border-border bg-surface flex items-center justify-between px-4 sm:px-6 py-2 flex-shrink-0 z-10 gap-3 overflow-x-auto shadow-sm">
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-sky-100 flex items-center justify-center text-accent">
              <span className="material-symbols-outlined text-lg">image_search</span>
            </div>
            <div>
              <span className="font-mono text-xs font-bold text-slate-800 uppercase tracking-wider block">
                AERION // STANDALONE IMAGE PERCEPTION
              </span>
              <span className="text-[10px] font-mono text-slate-500 block">
                FROZEN MODEL RUNTIME &bull; ZERO FABRICATION
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {activeResult && (
            <Link
              to={`/situations/00000000-0000-0000-0000-000000000001/report?analysis_id=${encodeURIComponent(activeResult.analysis_id)}`}
              className="h-8 px-3 rounded-lg bg-white border border-border text-slate-700 hover:text-accent hover:border-accent text-xs font-mono font-medium flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
              title="View deterministic operational situation report"
            >
              <span className="material-symbols-outlined text-[15px]">description</span>
              <span>OPERATIONAL REPORT</span>
            </Link>
          )}

          <button
            onClick={() => setIsHistoryOpen(true)}
            className="h-8 px-3 rounded-lg bg-white border border-border text-slate-700 hover:text-accent hover:border-accent text-xs font-mono font-medium flex items-center gap-1.5 transition-all shadow-sm cursor-pointer active:scale-95"
            title="View past analysis history"
          >
            <span className="material-symbols-outlined text-[15px]">history</span>
            <span>HISTORY</span>
          </button>

          <button
            onClick={() => { setUploadSourceType('drone_image'); setIsUploadOpen(true); }}
            className="h-8 px-3.5 rounded-lg bg-accent text-white font-mono font-bold text-xs hover:bg-accent-hover transition-all flex items-center gap-1.5 cursor-pointer shadow-sm active:scale-95"
          >
            <span className="material-symbols-outlined text-[16px]">flight</span>
            <span>INGEST DRONE IMAGE</span>
          </button>

          <button
            onClick={() => { setUploadSourceType('satellite_image'); setIsUploadOpen(true); }}
            className="h-8 px-3.5 rounded-lg bg-white border border-slate-300 text-slate-700 hover:border-accent hover:text-accent font-mono font-medium text-xs transition-all flex items-center gap-1.5 cursor-pointer shadow-sm active:scale-95"
          >
            <span className="material-symbols-outlined text-[16px]">satellite_alt</span>
            <span>INGEST SATELLITE IMAGE</span>
          </button>
        </div>
      </header>

      {/* Mobile / Tablet Responsive Tab Switcher (<lg) */}
      <div className="lg:hidden flex items-center justify-between border-b border-border bg-surface px-4 py-2 shrink-0 z-20 shadow-sm">
        <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200">
          <button
            onClick={() => setMobileTab('canvas')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all ${
              mobileTab === 'canvas' ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            IMAGE CANVAS
          </button>
          <button
            onClick={() => setMobileTab('intelligence')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all ${
              mobileTab === 'intelligence' ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            PERCEPTION INTELLIGENCE ({detections.length})
          </button>
        </div>
      </div>

      {/* Error Alert Banner */}
      {errorMessage && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 py-2.5 flex items-center justify-between text-xs font-mono text-rose-800">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-rose-600">error</span>
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-rose-600 hover:text-rose-900 font-bold underline"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left / Center: Image Canvas & Viewport */}
        <div className={`${mobileTab === 'canvas' ? 'flex' : 'hidden lg:flex'} flex-1 flex-col bg-slate-100 overflow-hidden relative spatial-grid`}>
          {/* Canvas Subheader Controls */}
          <div className="h-auto min-h-[44px] py-1.5 border-b border-slate-200/80 bg-white/90 backdrop-blur flex flex-wrap items-center justify-between px-4 gap-2 flex-shrink-0 shadow-sm z-10">
            <div className="flex items-center gap-3 font-mono text-xs">
              <span className="text-slate-500 font-semibold">SOURCE:</span>
              <span className="text-slate-800 font-bold uppercase">{activeResult?.source_type || 'AERIAL IMAGE'}</span>
              {activeResult?.analysis_id && (
                <>
                  <span className="text-slate-300">|</span>
                  <span className="text-slate-500">ID:</span>
                  <span className="text-accent font-semibold">{activeResult.analysis_id.substring(0, 8)}...</span>
                </>
              )}
            </div>

            {activeResult && (
              <div className="flex items-center gap-2">
                {/* Density Mode Switcher */}
                <div className="flex items-center rounded-lg bg-slate-100 border border-slate-200 p-0.5">
                  <button
                    onClick={() => setDensityMode('normal')}
                    className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      densityMode === 'normal' ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
                    }`}
                    title="Normal presentation: bounding boxes with labels"
                  >
                    NORMAL
                  </button>
                  <button
                    onClick={() => setDensityMode('dense')}
                    className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      densityMode === 'dense' ? 'bg-white text-amber-600 font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
                    }`}
                    title="Dense scene mode: clean boxes to avoid overlapping clutter"
                  >
                    DENSE
                  </button>
                </div>

                {/* Layer Toggles */}
                <div className="flex items-center rounded-lg bg-slate-100 border border-slate-200 p-0.5 gap-0.5">
                  <button
                    onClick={() => setShowBoxes(!showBoxes)}
                    className={`px-2 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      showBoxes ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-400 hover:text-slate-700'
                    }`}
                  >
                    BOXES: {showBoxes ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowLabels(!showLabels)}
                    className={`px-2 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      showLabels ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-400 hover:text-slate-700'
                    }`}
                  >
                    LABELS: {showLabels ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowConfidence(!showConfidence)}
                    className={`px-2 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      showConfidence ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-400 hover:text-slate-700'
                    }`}
                  >
                    CONF: {showConfidence ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowDetectionIds(!showDetectionIds)}
                    className={`px-2 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      showDetectionIds ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-400 hover:text-slate-700'
                    }`}
                  >
                    IDS: {showDetectionIds ? 'ON' : 'OFF'}
                  </button>
                </div>

                {/* Zoom Controls */}
                <div className="flex items-center rounded-lg bg-slate-100 border border-slate-200 p-0.5">
                  <button
                    onClick={() => setZoomScale((z) => Math.max(0.5, z - 0.25))}
                    className="w-6 h-6 flex items-center justify-center text-xs font-mono text-slate-600 hover:text-slate-900 cursor-pointer"
                    title="Zoom Out"
                  >
                    -
                  </button>
                  <span className="px-1 text-[10px] font-mono text-slate-700 font-semibold">{Math.round(zoomScale * 100)}%</span>
                  <button
                    onClick={() => setZoomScale((z) => Math.min(3.0, z + 0.25))}
                    className="w-6 h-6 flex items-center justify-center text-xs font-mono text-slate-600 hover:text-slate-900 cursor-pointer"
                    title="Zoom In"
                  >
                    +
                  </button>
                  <button
                    onClick={() => setZoomScale(1.0)}
                    className="px-2 text-[10px] font-mono text-accent hover:underline cursor-pointer font-bold"
                    title="Reset Zoom"
                  >
                    RESET
                  </button>
                </div>

                {/* View Mode Switcher */}
                <div className="flex items-center rounded-lg bg-slate-100 border border-slate-200 p-0.5">
                  <button
                    onClick={() => setViewMode('annotated')}
                    className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      viewMode === 'annotated'
                        ? 'bg-white text-accent font-bold shadow-sm'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    ANNOTATED
                  </button>
                  <button
                    onClick={() => setViewMode('raw')}
                    className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition-all cursor-pointer ${
                      viewMode === 'raw'
                        ? 'bg-white text-accent font-bold shadow-sm'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    RAW
                  </button>
                </div>

                {/* Download Actions */}
                {activeResult.annotated_artifact && (
                  <button
                    onClick={handleDownloadAnnotated}
                    disabled={isDownloading}
                    className="h-7 px-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover text-[10px] font-mono font-bold flex items-center gap-1 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                    title="Download high-resolution annotated image"
                  >
                    <span className="material-symbols-outlined text-[14px]">download</span>
                    <span>{isDownloading ? 'DOWNLOADING...' : 'DOWNLOAD ANNOTATED'}</span>
                  </button>
                )}

                <button
                  onClick={handleDownloadOriginal}
                  disabled={isDownloading || (!rawImageUrl && !activeResult.source_artifact?.artifact_key)}
                  className="h-7 px-2.5 rounded-lg bg-white border border-slate-300 text-slate-700 hover:text-accent hover:border-accent text-[10px] font-mono font-medium flex items-center gap-1 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                  title="Download unmodified original source image"
                >
                  <span className="material-symbols-outlined text-[14px]">photo</span>
                  <span>DOWNLOAD ORIGINAL</span>
                </button>
              </div>
            )}
          </div>

          {/* Canvas Area */}
          <div className="flex-1 relative flex items-center justify-center p-4 overflow-hidden">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center font-mono text-xs text-slate-500">
                <span className="material-symbols-outlined text-accent animate-spin text-3xl mb-2">progress_activity</span>
                <span>LOADING ANALYSIS RESULT...</span>
              </div>
            ) : activeResult ? (
              <div className="relative max-w-full max-h-full flex items-center justify-center border border-slate-300/80 rounded-xl shadow-card-hover overflow-hidden bg-slate-900 card-3d">
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
                                  fill={isSelected ? 'rgba(2, 132, 199, 0.25)' : 'none'}
                                  stroke={isSelected ? '#0284C7' : '#38BDF8'}
                                  strokeWidth={Math.max(1.8, (activeResult.image_width || 1000) / 550)}
                                />
                                {showLabels && (densityMode === 'normal' || isSelected || bw >= 45) && (
                                  <>
                                    <rect
                                      x={bx}
                                      y={badgeY}
                                      width={badgeW}
                                      height={16}
                                      fill={isSelected ? '#0284C7' : 'rgba(15, 23, 42, 0.88)'}
                                      stroke={isSelected ? '#0284C7' : '#38BDF8'}
                                      strokeWidth={1}
                                      rx={3}
                                    />
                                    <text
                                      x={bx + 3}
                                      y={textY}
                                      fill={isSelected ? '#FFFFFF' : '#38BDF8'}
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
                <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
                  <span className="px-2.5 py-1 rounded-md bg-white/90 backdrop-blur border border-slate-200 text-[10px] font-mono font-bold text-slate-800 shadow-sm">
                    {viewMode === 'annotated' ? 'AUTHORITATIVE ANNOTATED ARTIFACT' : 'RAW AERIAL INPUT'}
                  </span>
                  <span className="px-2.5 py-1 rounded-md bg-sky-500 text-white text-[10px] font-mono font-bold shadow-sm">
                    COUNT: {detections.length}
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center max-w-md card-3d-interactive bg-white border border-border rounded-2xl shadow-card">
                <div className="w-16 h-16 rounded-2xl bg-sky-50 border border-sky-200 flex items-center justify-center text-accent mb-4 shadow-sm">
                  <span className="material-symbols-outlined text-[32px]">image</span>
                </div>
                <h3 className="text-base font-bold font-mono text-slate-800 mb-1.5">
                  NO ACTIVE IMAGE LOADED
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed mb-6 font-mono">
                  Ingest an aerial drone or satellite image to run deterministic object perception inference without requiring external geocontext or location services.
                </p>
                <div className="flex flex-col sm:flex-row items-center gap-3 w-full">
                  <button
                    onClick={() => { setUploadSourceType('drone_image'); setIsUploadOpen(true); }}
                    className="w-full sm:w-auto flex-1 h-10 px-4 rounded-lg bg-accent text-white font-mono font-bold text-xs hover:bg-accent-hover transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer active:scale-95"
                  >
                    <span className="material-symbols-outlined text-[18px]">flight</span>
                    <span>INGEST DRONE IMAGE</span>
                  </button>
                  <button
                    onClick={() => { setUploadSourceType('satellite_image'); setIsUploadOpen(true); }}
                    className="w-full sm:w-auto flex-1 h-10 px-4 rounded-lg bg-white border border-slate-300 text-slate-700 font-mono font-medium text-xs hover:border-accent hover:text-accent transition-all flex items-center justify-center gap-2 cursor-pointer shadow-sm active:scale-95"
                  >
                    <span className="material-symbols-outlined text-[18px]">satellite_alt</span>
                    <span>INGEST SATELLITE IMAGE</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Perception Intelligence Panel */}
        <aside className={`${mobileTab === 'intelligence' ? 'flex' : 'hidden lg:flex'} w-full lg:w-80 flex-shrink-0 bg-surface border-l border-border flex-col overflow-y-auto custom-scrollbar shadow-sm`}>
          <div className="p-5 border-b border-border bg-slate-50/50">
            <h2 className="text-xs font-mono font-bold tracking-wider text-slate-500 uppercase mb-2">
              PERCEPTION SUMMARY
            </h2>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-mono font-bold text-accent">
                {detections.length}
              </span>
              <span className="text-xs font-mono text-slate-500 uppercase font-semibold">
                TOTAL DETECTIONS
              </span>
            </div>
            <p className="text-[10px] font-mono text-slate-400 mt-1">
              FROZEN YOLOV8 PERCEPTION RUNTIME (CONFIDENCE &ge; 0.25)
            </p>
          </div>

          {/* Detections by Category */}
          <div className="p-5 border-b border-border space-y-3">
            <h3 className="text-[10px] font-mono text-slate-500 uppercase tracking-wider font-bold">
              DETECTIONS BY CATEGORY
            </h3>

            {Object.keys(classCounts).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(classCounts).map(([cls, count]) => (
                  <div
                    key={cls}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono"
                  >
                    <span className="text-slate-800 font-medium capitalize">{cls}</span>
                    <span className="px-2.5 py-0.5 rounded-md bg-sky-100 text-accent font-bold">
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-center">
                <span className="text-xs font-mono text-slate-400">
                  {activeResult ? 'NO DETECTIONS FOUND (COUNT = 0)' : 'AWAITING IMAGE INGEST'}
                </span>
              </div>
            )}
          </div>

          {/* Detections List */}
          <div className="p-5 flex-1 flex flex-col space-y-3 overflow-y-auto custom-scrollbar">
            <div className="flex items-center justify-between">
              <h3 className="text-[10px] font-mono text-slate-500 uppercase tracking-wider font-bold">
                CONFIRMED DETECTIONS ({detections.length})
              </h3>
            </div>

            {detections.length > 0 ? (
              <div className="space-y-1.5">
                {detections.map((d, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-white border border-slate-200 hover:border-accent text-xs font-mono flex items-center justify-between transition-colors shadow-2xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400 text-[10px]">#{idx + 1}</span>
                      <span className="text-slate-800 font-semibold capitalize">{d.class_name}</span>
                    </div>
                    <span className="text-accent font-bold text-[11px]">
                      {(d.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 font-mono text-xs text-slate-400">
                {activeResult ? 'ZERO DETECTIONS RECORDED' : 'NO DATA AVAILABLE'}
              </div>
            )}
          </div>

          {/* Footer Note */}
          <div className="p-4 border-t border-border bg-slate-50">
            <div className="flex items-center gap-1.5 text-accent text-[11px] font-mono font-bold mb-1">
              <span className="material-symbols-outlined text-[16px]">verified</span>
              <span>AUDIT-GRADE TRACEABILITY</span>
            </div>
            <p className="text-[10px] text-slate-500 leading-relaxed font-mono">
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
        onError={(err) => setErrorMessage(err)}
        onAnalysisSuccess={(res, meta) => {
          setActiveResult(res);
          setErrorMessage(null);
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
