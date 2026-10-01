import React, { useEffect, useState, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Situation, SituationEvent, WeatherData, DetectionTarget, AERIONAnalysisResultData, RuntimeDetection, LocationProvenance } from '../types';
import { situationsApi, geospatialApi, analysisApi, boundariesApi } from '../api';
import { UploadModal, UploadMode } from '../components/UploadModal';
import { OperatorLocationModal } from '../components/OperatorLocationModal';
import { AnalysisHistoryModal } from '../components/AnalysisHistoryModal';
import { downloadAuthenticatedArtifact } from '../utils/download';
import { API_BASE } from '../api/client';

export interface VideoErrorInfo {
  type: 'codec' | 'network' | 'auth' | 'not_found' | 'decode' | 'aborted' | 'unknown';
  title: string;
  message: string;
  canRetry?: boolean;
}

export function classifyVideoError(
  mediaErr: MediaError | null,
  httpStatus?: number,
  codec?: string
): VideoErrorInfo {
  if (mediaErr) {
    if (mediaErr.code === 1) {
      return {
        type: 'aborted',
        title: 'Playback Aborted',
        message: 'The video playback was aborted by the client.',
        canRetry: true,
      };
    }
    if (mediaErr.code === 2) {
      return {
        type: 'network',
        title: 'Network Transfer Error',
        message: 'A network error occurred while downloading the video stream.',
        canRetry: true,
      };
    }
    if (mediaErr.code === 3) {
      return {
        type: 'decode',
        title: 'Video Decode Error',
        message: 'An error occurred while decoding the video stream (corrupted frames or unsupported profile).',
        canRetry: true,
      };
    }
  }

  if (httpStatus === 401 || httpStatus === 403) {
    return {
      type: 'auth',
      title: 'Authentication / Authorization Failure',
      message: httpStatus === 401
        ? 'Session expired or invalid credentials. Please log in again to view this evidence.'
        : 'Access denied: You do not have permission to view this evidence artifact.',
      canRetry: true,
    };
  }
  if (httpStatus === 404) {
    return {
      type: 'not_found',
      title: 'Evidence Artifact Not Found',
      message: 'The requested video artifact does not exist on the storage server.',
      canRetry: false,
    };
  }
  if (httpStatus && httpStatus >= 500) {
    return {
      type: 'network',
      title: 'Server Error',
      message: `The evidence storage server returned HTTP ${httpStatus}.`,
      canRetry: true,
    };
  }

  const reportedCodec = codec || 'unknown';
  return {
    type: 'codec',
    title: 'Unsupported Video Codec',
    message: `Browser playback unavailable for codec (${reportedCodec}). Download the authenticated MP4 artifact or view source footage.`,
    canRetry: false,
  };
}

export const BorderPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [situation, setSituation] = useState<Situation | null>(null);
  const [events, setEvents] = useState<SituationEvent[]>([]);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<DetectionTarget | null>(null);
  const [selectedRuntimeDetection, setSelectedRuntimeDetection] = useState<RuntimeDetection | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Analysis / Upload Modal State
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [uploadMode, setUploadMode] = useState<UploadMode>('drone_image');
  const [activeAnalysisResult, setActiveAnalysisResult] = useState<AERIONAnalysisResultData | null>(null);
  const [analyzedImageUrl, setAnalyzedImageUrl] = useState<string | null>(null);
  const [analyzedVideoUrl, setAnalyzedVideoUrl] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'annotated' | 'raw'>('annotated');

  // Operator-provided approximate location state
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);
  const [operatorLocation, setOperatorLocation] = useState<LocationProvenance | null>(null);
  const [weatherLoading, setWeatherLoading] = useState<boolean>(false);

  // Demo Vulnerability Boundary State
  const [demoBoundaryResult, setDemoBoundaryResult] = useState<any | null>(null);
  const [evaluatingBoundary, setEvaluatingBoundary] = useState<boolean>(false);

  // Display Controls (Issue 5 & Issue 6)
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  const [showDetectionIds, setShowDetectionIds] = useState<boolean>(false);
  const [showConfidence, setShowConfidence] = useState<boolean>(true);
  const [densityMode, setDensityMode] = useState<'normal' | 'dense'>('normal');
  const [videoError, setVideoError] = useState<VideoErrorInfo | null>(null);

  // Mobile / Tablet Responsive Tab State (<lg)
  const [mobileTab, setMobileTab] = useState<'feed' | 'timeline' | 'intelligence'>('feed');
  const [currentVideoTime, setCurrentVideoTime] = useState<number>(0);
  const [activeTimelineIndex, setActiveTimelineIndex] = useState<number | null>(null);
  const videoPlayerRef = useRef<HTMLVideoElement | null>(null);

  // Explicit Border Zone Configuration State (neutral "BORDER CONTEXT NOT SET" unless user configures)
  const [isZoneConfigOpen, setIsZoneConfigOpen] = useState<boolean>(false);
  const [activeConfiguredZone, setActiveConfiguredZone] = useState<Array<[number, number]> | null>(null);
  const [activeSectorName, setActiveSectorName] = useState<string>('');

  // Selected Evidence Frame Modal
  const [selectedEvidenceFrame, setSelectedEvidenceFrame] = useState<any | null>(null);

  const getEvidenceUrl = (key: string, download = false) => {
    const cleanKey = key.split('/').map(encodeURIComponent).join('/');
    const token = localStorage.getItem('aerion_access_token');
    const params = new URLSearchParams();
    params.set('download', download ? 'true' : 'false');
    if (token) params.set('token', token);
    return `${API_BASE}/evidence/${cleanKey}?${params.toString()}`;
  };

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

  // Restore analysis, demo boundary, and location from URL search parameters
  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken) {
      localStorage.setItem('aerion_access_token', urlToken);
    }

    const analysisIdParam = searchParams.get('analysis_id');
    if (analysisIdParam) {
      const restoreAnalysis = async () => {
        try {
          const resp = await analysisApi.getById(analysisIdParam);
          if (resp.success && resp.data) {
            const data = resp.data;
            setActiveAnalysisResult(data);
            setVideoError(null);
            if (data.annotated_image_base64) {
              setAnalyzedImageUrl(`data:image/jpeg;base64,${data.annotated_image_base64}`);
              setViewMode('annotated');
            } else if (data.annotated_video_artifact) {
              setViewMode('annotated');
              if (data.source_artifact?.artifact_key) {
                setAnalyzedVideoUrl(getEvidenceUrl(data.source_artifact.artifact_key, false));
              }
            }
            if (data.location_context) {
              setOperatorLocation(data.location_context);
            }
          }
        } catch (err) {
          console.warn(`Could not restore analysis ${analysisIdParam}:`, err);
        }
      };
      restoreAnalysis();
    }

    if (searchParams.get('demo_aoi') === 'true') {
      const evaluateDemo = async () => {
        try {
          const res = await boundariesApi.evaluate('DEMO_VULNERABILITY_BOUNDARY', {
            evidence_points: [{ latitude: 32.65, longitude: 74.85, weight: 1.0 }],
          });
          if (res.success && res.data) {
            setDemoBoundaryResult(res.data);
          }
        } catch (e) {
          console.warn('Auto demo boundary evaluation error:', e);
        }
      };
      evaluateDemo();
    }

    const latParam = searchParams.get('lat');
    const lonParam = searchParams.get('lon');
    if (latParam && lonParam) {
      const lat = parseFloat(latParam);
      const lon = parseFloat(lonParam);
      const enriched: LocationProvenance = {
        latitude: lat,
        longitude: lon,
        label: searchParams.get('location_label') || `Bangalore Urban Sector [${lat.toFixed(4)}, ${lon.toFixed(4)}]`,
        location_precision: 'APPROXIMATE',
        location_source: 'OPERATOR_PROVIDED',
        country: 'India',
        relevant_border: 'BORDER CONTEXT UNAVAILABLE',
      };
      setOperatorLocation(enriched);
    }
  }, [searchParams]);

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

  const threatTimeline: any[] = activeAnalysisResult?.threat_timeline || activeAnalysisResult?.report?.threat_timeline || [];
  const vehicleSummary: any = activeAnalysisResult?.vehicle_summary || activeAnalysisResult?.report?.vehicle_summary || null;
  const demoZoneActivity: any = activeAnalysisResult?.demo_zone_activity || activeAnalysisResult?.report?.demo_zone_activity || null;
  const threatLevelChanges: any[] = activeAnalysisResult?.threat_level_changes || activeAnalysisResult?.report?.threat_level_changes || [];
  const evidenceFrames: any[] = activeAnalysisResult?.evidence_frames || activeAnalysisResult?.report?.evidence_frames || [];

  const handleVideoTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const t = e.currentTarget.currentTime;
    setCurrentVideoTime(t);
    if (threatTimeline.length > 0) {
      const idx = threatTimeline.findIndex((ev: any, i: number) => {
        const evTime = ev.time_offset_seconds ?? ev.timestamp_seconds ?? (ev.frame_number ? ev.frame_number / 15 : 0);
        const nextEv = threatTimeline[i + 1];
        const nextTime = nextEv ? (nextEv.time_offset_seconds ?? nextEv.timestamp_seconds ?? (nextEv.frame_number ? nextEv.frame_number / 15 : Infinity)) : Infinity;
        return t >= evTime && t < nextTime;
      });
      if (idx !== -1 && idx !== activeTimelineIndex) {
        setActiveTimelineIndex(idx);
      }
    }
  };

  const handleSeekToTimelineEvent = (ev: any, index: number) => {
    const evTime = ev.time_offset_seconds ?? ev.timestamp_seconds ?? (ev.frame_number ? ev.frame_number / 15 : 0);
    if (videoPlayerRef.current) {
      videoPlayerRef.current.currentTime = evTime;
      videoPlayerRef.current.play().catch(() => {});
    }
    setActiveTimelineIndex(index);
  };

  const handleVideoError = async (e: React.SyntheticEvent<HTMLVideoElement, Event>) => {
    const videoEl = e.currentTarget;
    const mediaErr = videoEl.error;
    const src = videoEl.currentSrc || videoEl.src;

    if (mediaErr && (mediaErr.code === 1 || mediaErr.code === 2 || mediaErr.code === 3)) {
      setVideoError(classifyVideoError(mediaErr, undefined, activeAnalysisResult?.annotated_video_artifact?.codec));
      return;
    }

    try {
      const token = localStorage.getItem('aerion_access_token');
      const headers: Record<string, string> = { Range: 'bytes=0-0' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(src, { method: 'GET', headers });
      setVideoError(classifyVideoError(mediaErr, res.status, activeAnalysisResult?.annotated_video_artifact?.codec));
    } catch {
      setVideoError(classifyVideoError(mediaErr, 503, activeAnalysisResult?.annotated_video_artifact?.codec));
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-graphite">
      {/* Mobile / Tablet Responsive Tab Switcher (<lg) */}
      <div className="lg:hidden flex items-center justify-between border-b border-white/[0.08] bg-panel px-3 py-1.5 shrink-0 z-30">
        <div className="flex rounded bg-elevated/80 border border-white/[0.08] p-0.5">
          <button
            onClick={() => setMobileTab('feed')}
            className={`px-2.5 py-1 rounded text-xs font-mono font-medium transition-all ${
              mobileTab === 'feed' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
            }`}
          >
            SURVEILLANCE FEED
          </button>
          <button
            onClick={() => setMobileTab('timeline')}
            className={`px-2.5 py-1 rounded text-xs font-mono font-medium transition-all ${
              mobileTab === 'timeline' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
            }`}
          >
            THREAT TIMELINE {threatTimeline.length > 0 ? `(${threatTimeline.length})` : ''}
          </button>
          <button
            onClick={() => setMobileTab('intelligence')}
            className={`px-2.5 py-1 rounded text-xs font-mono font-medium transition-all ${
              mobileTab === 'intelligence' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
            }`}
          >
            INTELLIGENCE
          </button>
        </div>
        <span className="text-[10px] font-mono text-muted uppercase hidden sm:inline">BORDER RECON</span>
      </div>

      {/* Upper Main Section: Canvas (Left/Center) + Intelligence Panel (Right) */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* ============================================================ */}
        {/* CENTRAL SURVEILLANCE CANVAS & REAL-TIME TIMELINE             */}
        {/* ============================================================ */}
        <section className={`${mobileTab === 'feed' || mobileTab === 'timeline' ? 'flex' : 'hidden lg:flex'} flex-1 relative flex-col border-r border-white/[0.06] overflow-y-auto custom-scrollbar`}>
          {/* Top Bar with Status, Coordinates, and Ingest Triggers */}
          <div className="min-h-11 px-4 py-1.5 flex items-center justify-between gap-3 border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20 overflow-x-auto custom-scrollbar shrink-0">
            <div className="flex items-center gap-2.5 font-mono text-[11px] shrink-0">
              <span className="text-muted uppercase tracking-wider text-[10px]">SECTOR:</span>
              <span className="text-paper font-medium text-[11px]">
                {activeSectorName || (activeConfiguredZone ? 'CUSTOM BORDER ZONE' : 'BORDER CONTEXT NOT SET')}
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                activeConfiguredZone
                  ? 'bg-status-success/15 text-status-success border border-status-success/30 font-bold'
                  : 'bg-elevated text-muted border border-white/[0.08]'
              }`}>
                {activeConfiguredZone ? 'ZONE ACTIVE' : 'NO DEMO ZONE CONFIGURED'}
              </span>

              {/* Zone Configuration Trigger */}
              <button
                onClick={() => setIsZoneConfigOpen(true)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer ${
                  activeConfiguredZone
                    ? 'bg-accent/15 border border-accent/30 text-accent hover:bg-accent/25'
                    : 'bg-elevated/80 border border-white/[0.1] text-muted hover:text-accent hover:border-accent/40'
                }`}
                title="Configure or clear operational border zone boundary"
              >
                <span className="material-symbols-outlined text-[12px]">polyline</span>
                <span>{activeConfiguredZone ? 'EDIT ZONE' : 'CONFIGURE DEMO ZONE'}</span>
              </button>

              {/* Location Provenance Badge */}
              {operatorLocation ? (
                <button
                  onClick={() => setIsLocationModalOpen(true)}
                  className="px-2 py-0.5 rounded bg-status-ai/15 border border-status-ai/30 text-status-ai text-[10px] flex items-center gap-1 hover:bg-status-ai/25 transition-all"
                  title="Operator-provided approximate location active"
                >
                  <span className="material-symbols-outlined text-[12px]">location_on</span>
                  <span>APPROX: {operatorLocation.latitude.toFixed(2)}, {operatorLocation.longitude.toFixed(2)}</span>
                </button>
              ) : (
                <button
                  onClick={() => setIsLocationModalOpen(true)}
                  className="px-2 py-0.5 rounded bg-elevated/80 border border-white/[0.1] text-muted hover:text-accent hover:border-accent/40 text-[10px] flex items-center gap-1 transition-all"
                  title="Asset lacks embedded GPS. Provide approximate coordinates for geo-enrichment."
                >
                  <span className="material-symbols-outlined text-[12px]">add_location_alt</span>
                  <span>APPROX LOCATION</span>
                </button>
              )}

              {/* Operational Situation Report Navigation */}
              <Link
                to={`/situations/${situation?.id || '00000000-0000-0000-0000-000000000001'}/report${activeAnalysisResult?.analysis_id ? `?analysis_id=${activeAnalysisResult.analysis_id}` : ''}`}
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

              {/* Annotated Evidence vs Raw Toggle */}
              {activeAnalysisResult && (activeAnalysisResult.annotated_image_base64 || activeAnalysisResult.annotated_video_artifact) && (
                <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5 ml-1">
                  <button
                    onClick={() => setViewMode('annotated')}
                    className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                      viewMode === 'annotated'
                        ? 'bg-accent text-graphite font-bold shadow'
                        : 'text-muted hover:text-paper'
                    }`}
                  >
                    ANNOTATED EVIDENCE
                  </button>
                  <button
                    onClick={() => setViewMode('raw')}
                    className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                      viewMode === 'raw'
                        ? 'bg-accent text-graphite font-bold shadow'
                        : 'text-muted hover:text-paper'
                    }`}
                  >
                    RAW INGEST
                  </button>
                </div>
              )}

              {/* Display Controls Toolbar */}
              {activeAnalysisResult && activeAnalysisResult.annotated_video_artifact ? (
                <div
                  className="flex items-center rounded bg-elevated/70 border border-white/[0.1] px-2 py-0.5 ml-1 gap-1.5 font-mono text-[9px] text-muted shrink-0"
                  title="VIDEO ANNOTATION: PRE-RENDERED | BOXES: ON | LABELS: ON | CONFIDENCE: ON | TRACK IDS: ON | IMMUTABLE ARTIFACT"
                >
                  <span className="material-symbols-outlined text-[13px] text-accent">videocam</span>
                  <span className="text-accent font-bold">VIDEO ANNOTATION: PRE-RENDERED</span>
                  <span className="hidden xl:inline">|</span>
                  <span className="text-paper hidden xl:inline">BOXES: ON</span>
                  <span className="hidden xl:inline">|</span>
                  <span className="text-paper hidden xl:inline">LABELS: ON</span>
                  <span className="hidden xl:inline">|</span>
                  <span className="text-paper hidden xl:inline">CONFIDENCE: ON</span>
                  <span className="hidden xl:inline">|</span>
                  <span className="text-paper hidden xl:inline">TRACK IDS: ON</span>
                  <span>|</span>
                  <span className="px-1 py-0.2 rounded bg-accent/15 text-accent text-[8px] font-bold">IMMUTABLE ARTIFACT</span>
                </div>
              ) : activeAnalysisResult && (activeAnalysisResult.detections?.length || activeAnalysisResult.annotated_image_base64) ? (
                <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5 ml-1 gap-1 font-mono text-[9px]">
                  <button
                    onClick={() => setShowBoxes(!showBoxes)}
                    className={`px-1.5 py-0.5 rounded transition-all cursor-pointer ${
                      showBoxes ? 'bg-accent/20 text-accent font-bold' : 'text-faint hover:text-muted'
                    }`}
                    title="Toggle Bounding Boxes"
                  >
                    BOXES: {showBoxes ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowLabels(!showLabels)}
                    className={`px-1.5 py-0.5 rounded transition-all cursor-pointer ${
                      showLabels ? 'bg-accent/20 text-accent font-bold' : 'text-faint hover:text-muted'
                    }`}
                    title="Toggle Labels"
                  >
                    LABELS: {showLabels ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowConfidence(!showConfidence)}
                    className={`px-1.5 py-0.5 rounded transition-all cursor-pointer ${
                      showConfidence ? 'bg-accent/20 text-accent font-bold' : 'text-faint hover:text-muted'
                    }`}
                    title="Toggle Confidence %"
                  >
                    CONF: {showConfidence ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setShowDetectionIds(!showDetectionIds)}
                    className={`px-1.5 py-0.5 rounded transition-all cursor-pointer ${
                      showDetectionIds ? 'bg-accent/20 text-accent font-bold' : 'text-faint hover:text-muted'
                    }`}
                    title="Toggle Detection IDs"
                  >
                    IDS: {showDetectionIds ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => setDensityMode(densityMode === 'normal' ? 'dense' : 'normal')}
                    className={`px-1.5 py-0.5 rounded transition-all cursor-pointer ${
                      densityMode === 'dense' ? 'bg-status-warning text-graphite font-bold' : 'text-faint hover:text-muted'
                    }`}
                    title="Toggle High Density Mode"
                  >
                    {densityMode === 'dense' ? 'DENSE' : 'NORMAL'}
                  </button>
                </div>
              ) : null}
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px] shrink-0">
              <button
                onClick={() => { setUploadMode('drone_image'); setIsUploadOpen(true); }}
                className="px-2 py-1 rounded bg-elevated/70 border border-white/[0.1] text-paper hover:border-accent hover:text-accent transition-all flex items-center gap-1 text-[10px] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">flight</span>
                <span>INGEST DRONE</span>
              </button>

              <button
                onClick={() => { setUploadMode('satellite_image'); setIsUploadOpen(true); }}
                className="px-2 py-1 rounded bg-elevated/70 border border-white/[0.1] text-paper hover:border-accent hover:text-accent transition-all flex items-center gap-1 text-[10px] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">satellite_alt</span>
                <span>INGEST SATELLITE</span>
              </button>

              <button
                onClick={() => { setUploadMode('border_video'); setIsUploadOpen(true); }}
                className="px-2 py-1 rounded bg-elevated/70 border border-white/[0.1] text-paper hover:border-accent hover:text-accent transition-all flex items-center gap-1 text-[10px] cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">videocam</span>
                <span>INGEST VIDEO</span>
              </button>
            </div>
          </div>

          {/* Surveillance Visual Canvas */}
          <div className="flex-1 relative bg-canvas telemetry-grid flex items-center justify-center overflow-hidden">
            {activeAnalysisResult ? (
              <div className="relative w-full h-full p-4 flex flex-col items-center justify-center">
                {/* Real Ingested Visual Container */}
                <div className="relative border border-slate-200 rounded-xl bg-white shadow-card w-full h-full max-h-[85vh] overflow-hidden flex items-center justify-center">
                  {analyzedImageUrl ? (
                    <div className="relative max-w-full max-h-full flex items-center justify-center">
                      {/* If viewMode is 'annotated' and backend generated annotated_image_base64 exists, display the authoritative annotated visual artifact */}
                      {viewMode === 'annotated' && activeAnalysisResult.annotated_image_base64 ? (
                        <div className="relative max-w-full max-h-full flex items-center justify-center">
                          <img
                            src={`data:image/jpeg;base64,${activeAnalysisResult.annotated_image_base64}`}
                            alt="Authoritative Annotated Visual Evidence"
                            className="max-w-full max-h-[78vh] object-contain select-none shadow-2xl"
                          />
                          <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded bg-graphite/90 border border-accent/40 text-[9px] font-mono text-accent">
                              BACKEND DERIVED ARTIFACT (SHA-256 VERIFIED)
                            </span>
                            <a
                              href={`data:image/jpeg;base64,${activeAnalysisResult.annotated_image_base64}`}
                              download={`AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_annotated_${Date.now()}.jpg`}
                              className="px-2 py-0.5 rounded bg-accent text-graphite hover:bg-accent/90 text-[9px] font-mono font-bold flex items-center gap-1 shadow transition-all"
                            >
                              <span className="material-symbols-outlined text-[11px]">download</span>
                              <span>DOWNLOAD ANNOTATED IMAGE</span>
                            </a>
                          </div>
                        </div>
                      ) : (
                        <>
                          <img
                            src={analyzedImageUrl}
                            alt="Analyzed Aerial Ingest"
                            className="max-w-full max-h-[78vh] object-contain select-none pointer-events-none"
                          />
                          <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded bg-graphite/90 border border-white/[0.15] text-[9px] font-mono text-muted">
                              RAW SOURCE INGEST
                            </span>
                            {analyzedImageUrl && (
                              <a
                                href={analyzedImageUrl}
                                download={`AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_original.jpg`}
                                className="px-2 py-0.5 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[9px] font-mono flex items-center gap-1 shadow transition-all"
                              >
                                <span className="material-symbols-outlined text-[11px]">download</span>
                                <span>DOWNLOAD ORIGINAL IMAGE</span>
                              </a>
                            )}
                          </div>
                        </>
                      )}

                      {/* Interactive SVG overlay shown in raw view or when no pre-rendered base64 is available */}
                      {showBoxes && (viewMode === 'raw' || !activeAnalysisResult.annotated_image_base64) && activeAnalysisResult.detections && activeAnalysisResult.detections.length > 0 && activeAnalysisResult.image_width && activeAnalysisResult.image_height && (
                        <svg
                          className="absolute inset-0 w-full h-full pointer-events-auto"
                          viewBox={`0 0 ${activeAnalysisResult.image_width} ${activeAnalysisResult.image_height}`}
                          preserveAspectRatio="xMidYMid meet"
                        >
                          {activeAnalysisResult.detections.map((det, idx) => {
                            if (det.bbox) {
                              const x = det.bbox.x1;
                              const y = det.bbox.y1;
                              const w = det.bbox.x2 - det.bbox.x1;
                              const h = det.bbox.y2 - det.bbox.y1;
                              const isSelected = selectedRuntimeDetection === det;
                              const shortClass = det.class_name.toUpperCase().replace(/_/g, ' ');
                              const confStr = showConfidence ? ` ${Math.round(det.confidence * 100)}%` : '';
                              const idStr = showDetectionIds ? ` #${idx + 1}` : '';
                              const labelText = `${shortClass}${confStr}${idStr}`;
                              const badgeW = Math.max(50, labelText.length * 8 + 12);
                              const isNearTop = y < 22;
                              const badgeY = isNearTop ? y + 2 : y - 20;
                              const textY = isNearTop ? y + 15 : y - 6;

                              return (
                                <g
                                  key={`det-${idx}`}
                                  onClick={() => setSelectedRuntimeDetection(det)}
                                  className="cursor-pointer"
                                >
                                  {/* High-tech tactical bounding box */}
                                  <rect
                                    x={x}
                                    y={y}
                                    width={w}
                                    height={h}
                                    fill={isSelected ? 'rgba(56, 213, 245, 0.22)' : 'rgba(239, 68, 68, 0.12)'}
                                    stroke={isSelected ? '#38D5F5' : '#EF4444'}
                                    strokeWidth={Math.max(1.5, (activeAnalysisResult.image_width || 1000) / 550)}
                                    rx={1}
                                  />
                                  {/* Compact label badge */}
                                  {showLabels && (densityMode === 'normal' || isSelected || w >= 45) && (
                                    <>
                                      <rect
                                        x={x}
                                        y={badgeY}
                                        width={badgeW}
                                        height={18}
                                        fill={isSelected ? '#38D5F5' : '#EF4444'}
                                        rx={2}
                                      />
                                      <text
                                        x={x + 4}
                                        y={textY}
                                        fill="#07090C"
                                        fontSize={Math.max(9, (activeAnalysisResult.image_width || 1000) / 105)}
                                        fontFamily="monospace"
                                        fontWeight="bold"
                                      >
                                        {labelText}
                                      </text>
                                    </>
                                  )}
                                </g>
                              );
                            } else if (det.obb_points && det.obb_points.length === 4) {
                              const pts = det.obb_points.map(p => `${p.x},${p.y}`).join(' ');
                              const isSelected = selectedRuntimeDetection === det;
                              const shortClass = det.class_name.toUpperCase().replace(/_/g, ' ');
                              const confStr = showConfidence ? ` ${Math.round(det.confidence * 100)}%` : '';
                              const idStr = showDetectionIds ? ` #${idx + 1}` : '';
                              const labelText = `${shortClass}${confStr}${idStr}`;
                              return (
                                <g
                                  key={`obb-${idx}`}
                                  onClick={() => setSelectedRuntimeDetection(det)}
                                  className="cursor-pointer"
                                >
                                  <polygon
                                    points={pts}
                                    fill={isSelected ? 'rgba(56, 213, 245, 0.25)' : 'rgba(56, 213, 245, 0.12)'}
                                    stroke="#38D5F5"
                                    strokeWidth={Math.max(1.5, (activeAnalysisResult.image_width || 1000) / 550)}
                                  />
                                  {showLabels && (
                                    <text
                                      x={det.obb_points[0].x}
                                      y={Math.max(12, det.obb_points[0].y - 5)}
                                      fill="#38D5F5"
                                      fontSize={Math.max(9, (activeAnalysisResult.image_width || 1000) / 105)}
                                      fontFamily="monospace"
                                      fontWeight="bold"
                                    >
                                      {labelText}
                                    </text>
                                  )}
                                </g>
                              );
                            }
                            return null;
                          })}
                        </svg>
                      )}

                      {/* Honest zero-detection indicator banner overlay if detections is empty */}
                      {(!activeAnalysisResult.detections || activeAnalysisResult.detections.length === 0) && (
                        <div className="absolute bottom-4 inset-x-8 flex justify-center pointer-events-none">
                          <div className="px-4 py-2 rounded bg-graphite/90 border border-white/[0.2] text-faint font-mono text-xs shadow-lg flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-muted"></span>
                            <span>VERIFIED SCENE ANALYSIS: NO DETECTIONS (COUNT = 0)</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : analyzedVideoUrl || activeAnalysisResult.annotated_video_artifact ? (
                    /* Video Evidence Container */
                    <div className="relative max-w-full max-h-full flex flex-col items-center justify-center p-2">
                      {/* Video Header & Status */}
                      <div className="w-full flex items-center justify-between pb-2 mb-2 border-b border-white/[0.08] font-mono text-xs">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded bg-accent/15 border border-accent/40 text-accent font-bold text-[10px]">
                            [ANNOTATED VIDEO]
                          </span>
                          <span className="text-paper font-semibold text-[11px]">
                            DERIVED BORDER SURVEILLANCE EVIDENCE
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded bg-elevated/80 border border-white/[0.1] text-status-ai text-[10px] font-medium">
                            PRE-RENDERED / IMMUTABLE ARTIFACT
                          </span>
                          <button
                            onClick={() => { setActiveAnalysisResult(null); setAnalyzedImageUrl(null); setAnalyzedVideoUrl(null); setSelectedRuntimeDetection(null); }}
                            className="px-2 py-0.5 rounded bg-elevated/80 border border-white/[0.1] text-[10px] font-mono text-muted hover:text-paper hover:border-accent flex items-center gap-1 transition-all cursor-pointer"
                            title="Clear active ingested analysis"
                          >
                            <span className="material-symbols-outlined text-[12px]">refresh</span>
                            <span>CLEAR</span>
                          </button>
                        </div>
                      </div>

                      {/* Video Player Box */}
                      <div className="relative border border-white/[0.1] rounded overflow-hidden max-h-[65vh] w-full flex items-center justify-center bg-black shadow-2xl">
                        {(viewMode === 'annotated' && activeAnalysisResult.annotated_video_artifact?.artifact_key) ? (
                          videoError ? (
                            <div className="p-8 text-center font-mono text-xs text-muted max-w-xl mx-auto flex flex-col items-center">
                              <span className="material-symbols-outlined text-4xl text-status-warning block mb-2">
                                {videoError.type === 'auth' ? 'lock' : videoError.type === 'not_found' ? 'search_off' : videoError.type === 'network' ? 'cloud_off' : 'videocam_off'}
                              </span>
                              <span className="text-status-warning font-semibold text-sm block mb-1">
                                {videoError.title}
                              </span>
                              <span className="block text-[11px] text-faint mb-4 leading-relaxed">
                                {videoError.message}
                              </span>
                              <div className="flex items-center gap-3 flex-wrap justify-center">
                                {videoError.canRetry && (
                                  <button
                                    onClick={() => {
                                      setVideoError(null);
                                      if (videoPlayerRef.current) {
                                        videoPlayerRef.current.load();
                                        videoPlayerRef.current.play().catch(() => {});
                                      }
                                    }}
                                    className="px-3.5 py-2 rounded bg-elevated border border-white/[0.2] text-paper font-bold text-xs inline-flex items-center gap-1.5 shadow hover:bg-elevated/80 cursor-pointer"
                                  >
                                    <span className="material-symbols-outlined text-[16px]">refresh</span>
                                    <span>RETRY PLAYBACK</span>
                                  </button>
                                )}
                                {analyzedVideoUrl && (
                                  <button
                                    onClick={() => { setViewMode('raw'); setVideoError(null); }}
                                    className="px-3.5 py-2 rounded bg-accent/20 border border-accent text-accent font-bold text-xs inline-flex items-center gap-1.5 shadow hover:bg-accent/30 cursor-pointer"
                                  >
                                    <span className="material-symbols-outlined text-[16px]">play_circle</span>
                                    <span>PLAY SOURCE WITH OVERLAY</span>
                                  </button>
                                )}
                                <button
                                  onClick={async () => {
                                    const artKey = activeAnalysisResult.annotated_video_artifact?.artifact_key;
                                    if (!artKey) return;
                                    const dlUrl = getEvidenceUrl(artKey, true);
                                    const filename = `AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_annotated.mp4`;
                                    try {
                                      await downloadAuthenticatedArtifact(dlUrl, filename);
                                    } catch (e: any) {
                                      alert(e.message || 'Download failed');
                                    }
                                  }}
                                  className="px-3.5 py-2 rounded bg-accent text-graphite font-bold text-xs inline-flex items-center gap-1.5 shadow hover:bg-accent/90 cursor-pointer"
                                >
                                  <span className="material-symbols-outlined text-[16px]">download</span>
                                  <span>DOWNLOAD ANNOTATED VIDEO</span>
                                </button>
                                <Link
                                  to={`/situations/${situation?.id || '00000000-0000-0000-0000-000000000001'}/report?analysis_id=${activeAnalysisResult.analysis_id}`}
                                  className="px-3 py-2 rounded bg-elevated/80 border border-white/[0.1] text-paper hover:text-accent hover:border-accent/40 text-xs inline-flex items-center gap-1.5 transition-all"
                                >
                                  <span className="material-symbols-outlined text-[15px]">description</span>
                                  <span>OPEN REPORT</span>
                                </Link>
                              </div>
                            </div>
                          ) : (
                            <video
                              ref={videoPlayerRef}
                              key={`annotated-${activeAnalysisResult.annotated_video_artifact.artifact_key}`}
                              src={getEvidenceUrl(activeAnalysisResult.annotated_video_artifact.artifact_key, false)}
                              controls
                              autoPlay
                              loop
                              muted
                              onTimeUpdate={handleVideoTimeUpdate}
                              onError={handleVideoError}
                              className="max-w-full max-h-[62vh] object-contain select-none transform-gpu will-change-transform"
                            />
                          )
                        ) : analyzedVideoUrl ? (
                          <video
                            ref={videoPlayerRef}
                            key={`raw-${analyzedVideoUrl}`}
                            src={analyzedVideoUrl}
                            controls
                            autoPlay
                            loop
                            muted
                            onTimeUpdate={handleVideoTimeUpdate}
                            onError={handleVideoError}
                            className="max-w-full max-h-[62vh] object-contain select-none transform-gpu will-change-transform"
                          />
                        ) : (
                          <div className="p-12 text-center font-mono text-xs text-muted">
                            <span className="material-symbols-outlined text-3xl text-accent block mb-2">videocam</span>
                            <span>DERIVED VIDEO ARTIFACT PERSISTED</span>
                            <span className="block text-[10px] text-faint mt-1">KEY: {activeAnalysisResult.annotated_video_artifact?.artifact_key}</span>
                          </div>
                        )}

                        <div className="absolute top-2 left-2 z-10 flex flex-col gap-1">
                          {activeAnalysisResult.annotated_video_artifact && viewMode === 'annotated' ? (
                            <span className="px-2 py-0.5 rounded bg-graphite/90 border border-accent/40 text-[9px] font-mono text-accent">
                              ANNOTATED TRACKING EVIDENCE (BOUNDING BOXES & IDS)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-graphite/90 border border-white/[0.15] text-[9px] font-mono text-muted">
                              RAW SURVEILLANCE VIDEO INGEST
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Video Metadata Grid & Action Toolbar */}
                      {activeAnalysisResult.annotated_video_artifact && (
                        <div className="w-full mt-2 bg-graphite/90 border border-white/[0.1] rounded p-2.5 font-mono text-xs">
                          {/* Metadata Grid */}
                          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 pb-2 mb-2 border-b border-white/[0.06] text-[10px]">
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px] uppercase">FPS</span>
                              <span className="text-paper font-semibold">{activeAnalysisResult.annotated_video_artifact.fps}</span>
                            </div>
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px] uppercase">FRAME COUNT</span>
                              <span className="text-paper font-semibold">
                                {activeAnalysisResult.annotated_video_artifact.frame_count} / {activeAnalysisResult.annotated_video_artifact.source_frame_count}
                              </span>
                            </div>
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px] uppercase">DURATION</span>
                              <span className="text-paper font-semibold">
                                {activeAnalysisResult.annotated_video_artifact.duration_seconds !== undefined
                                  ? `${Number(activeAnalysisResult.annotated_video_artifact.duration_seconds).toFixed(1)}s`
                                  : (activeAnalysisResult.annotated_video_artifact.duration ? `${activeAnalysisResult.annotated_video_artifact.duration}s` : '--')}
                              </span>
                            </div>
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px] uppercase">DETECTIONS</span>
                              <span className="text-accent font-semibold">
                                {activeAnalysisResult.annotated_video_artifact.total_detections_count !== undefined
                                  ? activeAnalysisResult.annotated_video_artifact.total_detections_count
                                  : (activeAnalysisResult.detections?.length || 0)}
                              </span>
                            </div>
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px] uppercase">TRACKS</span>
                              <span className="text-status-ai font-semibold">
                                {activeAnalysisResult.annotated_video_artifact.unique_tracks_count !== undefined
                                  ? activeAnalysisResult.annotated_video_artifact.unique_tracks_count
                                  : (activeAnalysisResult.tracks?.length || 0)}
                              </span>
                            </div>
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px] uppercase">CODEC</span>
                              <span className="text-paper font-semibold">{activeAnalysisResult.annotated_video_artifact.codec || 'mp4v'}</span>
                            </div>
                            <div className="p-1.5 bg-elevated/40 rounded border border-white/[0.04] col-span-2 md:col-span-1">
                              <span className="text-faint block text-[8px] uppercase">ARTIFACT SHA256</span>
                              <span className="text-accent font-semibold truncate block" title={activeAnalysisResult.annotated_video_artifact.sha256}>
                                {activeAnalysisResult.annotated_video_artifact.sha256 ? `${activeAnalysisResult.annotated_video_artifact.sha256.substring(0, 10)}...` : 'PENDING'}
                              </span>
                            </div>
                          </div>

                          {/* Action Toolbar */}
                          <div className="flex items-center justify-between flex-wrap gap-2 pt-1">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={async () => {
                                  const artKey = activeAnalysisResult.annotated_video_artifact?.artifact_key;
                                  const dlUrl = artKey ? getEvidenceUrl(artKey, true) : (analyzedVideoUrl || '');
                                  const filename = `AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_annotated.mp4`;
                                  try {
                                    await downloadAuthenticatedArtifact(dlUrl, filename);
                                  } catch (e: any) {
                                    alert(e.message || 'Download failed');
                                  }
                                }}
                                className="px-2.5 py-1 rounded bg-accent text-graphite hover:bg-accent/90 text-[10px] font-bold flex items-center gap-1 shadow transition-all cursor-pointer"
                              >
                                <span className="material-symbols-outlined text-[13px]">download</span>
                                <span>DOWNLOAD ANNOTATED VIDEO</span>
                              </button>

                              {analyzedVideoUrl && (
                                <a
                                  href={analyzedVideoUrl}
                                  download={`AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_original.mp4`}
                                  className="px-2.5 py-1 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[10px] flex items-center gap-1 shadow transition-all cursor-pointer"
                                >
                                  <span className="material-symbols-outlined text-[13px]">download</span>
                                  <span>DOWNLOAD ORIGINAL VIDEO</span>
                                </a>
                              )}
                            </div>

                            <div className="flex items-center gap-2">
                              <Link
                                to={`/situations/${situation?.id || '00000000-0000-0000-0000-000000000001'}/report?analysis_id=${activeAnalysisResult.analysis_id}`}
                                className="px-2.5 py-1 rounded bg-status-ai/20 border border-status-ai/40 text-status-ai hover:bg-status-ai/30 text-[10px] font-semibold flex items-center gap-1 transition-all"
                              >
                                <span className="material-symbols-outlined text-[13px]">description</span>
                                <span>OPEN REPORT</span>
                              </Link>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Dynamic Threat Level Transitions Alerts */}
                      {threatLevelChanges.length > 0 && (
                        <div className="w-full mt-2 p-2 bg-panel/90 border border-status-warning/30 rounded font-mono text-[11px] space-y-1">
                          <div className="flex items-center gap-1.5 text-status-warning font-semibold text-[10px]">
                            <span className="material-symbols-outlined text-[14px]">notifications_active</span>
                            <span>DYNAMIC THREAT LEVEL TRANSITIONS DETECTED ({threatLevelChanges.length})</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {threatLevelChanges.map((ch: any, idx: number) => (
                              <div key={idx} className="px-2 py-0.5 rounded bg-graphite/80 border border-white/[0.08] text-[10px] flex items-center gap-1">
                                <span className="text-paper font-bold">TRK-{ch.track_id}</span>
                                <span className="text-muted">{ch.previous_level}</span>
                                <span className="text-accent">→</span>
                                <span className={`font-bold ${
                                  ch.new_level === 'CRITICAL' ? 'text-status-critical' : ch.new_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                                }`}>
                                  {ch.new_level}
                                </span>
                                <span className="text-faint text-[9px]">@{Number(ch.time_offset_seconds).toFixed(1)}s</span>
                                {ch.reason && <span className="text-faint text-[8px] truncate max-w-[120px]">({ch.reason})</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Overview Grid: Vehicle Summary + Demo Zone Activity */}
                      <div className="w-full mt-2 grid grid-cols-1 md:grid-cols-2 gap-2">
                        {/* Vehicle / Track Summary */}
                        <div className="p-2.5 bg-panel/80 border border-white/[0.06] rounded font-mono text-xs space-y-1">
                          <div className="flex items-center justify-between text-[10px] text-muted">
                            <span className="font-bold text-accent uppercase">VEHICLE INVENTORY & TRACKS</span>
                            <span>TOTAL: {vehicleSummary?.total_vehicles_observed ?? (activeAnalysisResult.tracks?.length || 0)}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-[10px] pt-1">
                            <div className="p-1.5 bg-graphite/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px]">ACTIVE TRACKS</span>
                              <span className="text-paper font-bold">{vehicleSummary?.active_tracks_count ?? activeAnalysisResult.tracks?.length ?? 0}</span>
                            </div>
                            <div className="p-1.5 bg-graphite/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px]">MAX THREAT</span>
                              <span className={`font-bold ${
                                vehicleSummary?.max_threat_level === 'CRITICAL' ? 'text-status-critical' : vehicleSummary?.max_threat_level === 'HIGH' ? 'text-status-warning' : 'text-accent'
                              }`}>
                                {vehicleSummary?.max_threat_level ?? 'MONITORED'}
                              </span>
                            </div>
                            <div className="p-1.5 bg-graphite/40 rounded border border-white/[0.04]">
                              <span className="text-faint block text-[8px]">CATEGORIES</span>
                              <span className="text-paper font-semibold truncate block">
                                {vehicleSummary?.vehicle_categories ? Object.entries(vehicleSummary.vehicle_categories).map(([k, v]) => `${k}:${v}`).join(', ') : 'VEHICLES'}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Demo Zone Activity */}
                        <div className="p-2.5 bg-panel/80 border border-white/[0.06] rounded font-mono text-xs space-y-1">
                          <div className="flex items-center justify-between text-[10px] text-muted">
                            <span className="font-bold text-accent uppercase">DEMO ZONE SURVEILLANCE</span>
                            <span className={`px-1.5 py-0.2 rounded text-[9px] ${
                              demoZoneActivity?.zone_configured || activeConfiguredZone
                                ? 'bg-status-success/15 text-status-success'
                                : 'bg-elevated text-faint'
                            }`}>
                              {demoZoneActivity?.zone_configured || activeConfiguredZone ? 'ZONE ACTIVE' : 'NO DEMO ZONE CONFIGURED'}
                            </span>
                          </div>
                          {demoZoneActivity?.zone_configured || activeConfiguredZone ? (
                            <div className="grid grid-cols-3 gap-2 text-[10px] pt-1">
                              <div className="p-1.5 bg-graphite/40 rounded border border-white/[0.04]">
                                <span className="text-faint block text-[8px]">ENTRIES</span>
                                <span className="text-status-warning font-bold">{demoZoneActivity?.zone_entries_count || 0}</span>
                              </div>
                              <div className="p-1.5 bg-graphite/40 rounded border border-white/[0.04]">
                                <span className="text-faint block text-[8px]">EXITS</span>
                                <span className="text-paper font-bold">{demoZoneActivity?.zone_exits_count || 0}</span>
                              </div>
                              <div className="p-1.5 bg-graphite/40 rounded border border-white/[0.04]">
                                <span className="text-faint block text-[8px]">ACTIVE INSIDE</span>
                                <span className="text-status-critical font-bold">{demoZoneActivity?.active_vehicles_inside || 0}</span>
                              </div>
                            </div>
                          ) : (
                            <div className="p-2 bg-graphite/40 rounded border border-white/[0.04] text-[10px] text-faint flex items-center justify-between">
                              <span>BORDER CONTEXT NOT SET — Threat levels evaluated without containment.</span>
                              <button
                                onClick={() => setIsZoneConfigOpen(true)}
                                className="px-2 py-0.5 rounded bg-elevated border border-white/[0.1] text-accent text-[9px] hover:bg-elevated/80 cursor-pointer"
                              >
                                CONFIGURE ZONE
                              </button>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Synchronized Real-Time Vehicle Threat Timeline Table */}
                      <div className="w-full mt-2 bg-graphite/80 border border-white/[0.08] rounded p-2.5 text-xs font-mono">
                        <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/[0.06] text-[10px]">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-accent uppercase">REAL-TIME VEHICLE THREAT TIMELINE</span>
                            <span className="px-1.5 py-0.2 rounded bg-elevated text-paper text-[9px]">
                              PLAYHEAD: {currentVideoTime.toFixed(1)}s
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[9px] text-faint">
                            <span className="hidden sm:inline">CLICK ROW TO SEEK VIDEO</span>
                            <span>EVENTS: {threatTimeline.length > 0 ? threatTimeline.length : (activeAnalysisResult.detections?.length || 0)}</span>
                          </div>
                        </div>

                        {threatTimeline.length > 0 ? (
                          <div className="overflow-x-auto max-h-56 custom-scrollbar">
                            <table className="w-full text-left font-mono text-[10px] border-collapse">
                              <thead>
                                <tr className="border-b border-white/[0.06] text-faint text-[9px] uppercase">
                                  <th className="py-1 px-1.5">TIME</th>
                                  <th className="py-1 px-1.5">TRACK</th>
                                  <th className="py-1 px-1.5">OBJECT</th>
                                  <th className="py-1 px-1.5">ZONE STATE</th>
                                  <th className="py-1 px-1.5">THREAT LEVEL</th>
                                  <th className="py-1 px-1.5">TREND</th>
                                  <th className="py-1 px-1.5">CONF</th>
                                  <th className="py-1 px-1.5 text-right">EVIDENCE</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-white/[0.03]">
                                {threatTimeline.map((ev: any, idx: number) => {
                                  const evTime = ev.time_offset_seconds ?? ev.timestamp_seconds ?? (ev.frame_number ? ev.frame_number / 15 : 0);
                                  const isActive = activeTimelineIndex === idx;
                                  return (
                                    <tr
                                      key={idx}
                                      onClick={() => handleSeekToTimelineEvent(ev, idx)}
                                      className={`cursor-pointer transition-colors ${
                                        isActive
                                          ? 'bg-accent/20 border-l-2 border-accent text-accent font-semibold'
                                          : 'hover:bg-white/[0.03] text-paper'
                                      }`}
                                    >
                                      <td className="py-1 px-1.5 font-mono text-faint">{Number(evTime).toFixed(1)}s</td>
                                      <td className="py-1 px-1.5 text-status-ai font-bold">TRK-{ev.track_id}</td>
                                      <td className="py-1 px-1.5 uppercase font-medium">{ev.object_class || ev.class_name}</td>
                                      <td className="py-1 px-1.5">
                                        <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                                          ev.zone_state === 'INSIDE'
                                            ? 'bg-status-critical/20 text-status-critical border border-status-critical/30'
                                            : ev.zone_state === 'APPROACHING'
                                            ? 'bg-status-warning/20 text-status-warning border border-status-warning/30'
                                            : ev.zone_state === 'EXITED'
                                            ? 'bg-status-ai/20 text-status-ai border border-status-ai/30'
                                            : 'bg-elevated text-faint'
                                        }`}>
                                          {ev.zone_state || 'OUTSIDE'}
                                        </span>
                                      </td>
                                      <td className="py-1 px-1.5">
                                        <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                                          ev.threat_level === 'CRITICAL'
                                            ? 'bg-status-critical text-graphite font-black'
                                            : ev.threat_level === 'HIGH'
                                            ? 'bg-status-warning/20 text-status-warning'
                                            : ev.threat_level === 'MEDIUM'
                                            ? 'bg-status-warning/15 text-status-warning/80'
                                            : ev.threat_level === 'LOW'
                                            ? 'bg-status-success/15 text-status-success'
                                            : 'bg-elevated text-faint'
                                        }`}>
                                          {ev.threat_level || 'UNAVAILABLE'}
                                        </span>
                                      </td>
                                      <td className="py-1 px-1.5">
                                        <span className="flex items-center gap-0.5 text-[9px]">
                                          <span className="material-symbols-outlined text-[11px]">
                                            {ev.threat_trend === 'ESCALATING' ? 'trending_up' : ev.threat_trend === 'DE_ESCALATING' ? 'trending_down' : 'trending_flat'}
                                          </span>
                                          <span className="text-[8px]">{ev.threat_trend || 'STABLE'}</span>
                                        </span>
                                      </td>
                                      <td className="py-1 px-1.5 text-faint">{ev.confidence ? `${Math.round(ev.confidence * 100)}%` : '--'}</td>
                                      <td className="py-1 px-1.5 text-right">
                                        {ev.evidence_frame_key ? (
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              setSelectedEvidenceFrame({
                                                artifact_key: ev.evidence_frame_key,
                                                sha256: ev.evidence_frame_sha256,
                                                frame_number: ev.frame_number,
                                                track_id: ev.track_id,
                                                timestamp_seconds: evTime,
                                                threat_level: ev.threat_level,
                                              });
                                            }}
                                            className="px-1.5 py-0.5 rounded bg-accent/15 border border-accent/30 text-accent text-[8px] hover:bg-accent/25 cursor-pointer"
                                          >
                                            VIEW
                                          </button>
                                        ) : (
                                          <span className="text-faint text-[8px]">--</span>
                                        )}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        ) : activeAnalysisResult.detections && activeAnalysisResult.detections.length > 0 ? (
                          <div className="overflow-x-auto max-h-56 custom-scrollbar">
                            <table className="w-full text-left font-mono text-[10px] border-collapse">
                              <thead>
                                <tr className="border-b border-white/[0.06] text-faint text-[9px] uppercase">
                                  <th className="py-1 px-1.5">FRAME</th>
                                  <th className="py-1 px-1.5">TRACK</th>
                                  <th className="py-1 px-1.5">CLASS</th>
                                  <th className="py-1 px-1.5">CONF</th>
                                  <th className="py-1 px-1.5">BBOX</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-white/[0.03]">
                                {activeAnalysisResult.detections.slice(0, 50).map((d: any, idx: number) => (
                                  <tr
                                    key={idx}
                                    onClick={() => setSelectedRuntimeDetection(d)}
                                    className={`cursor-pointer transition-colors ${
                                      selectedRuntimeDetection === d
                                        ? 'bg-accent/20 border-l-2 border-accent text-accent font-semibold'
                                        : 'hover:bg-white/[0.03] text-paper'
                                    }`}
                                  >
                                    <td className="py-1 px-1.5 font-mono text-faint">#{d.frame_number ?? '--'}</td>
                                    <td className="py-1 px-1.5 text-status-ai font-bold">TRK-{d.track_id ?? '--'}</td>
                                    <td className="py-1 px-1.5 uppercase font-medium">{d.class_name}</td>
                                    <td className="py-1 px-1.5 text-accent">{Math.round((d.confidence ?? 1) * 100)}%</td>
                                    <td className="py-1 px-1.5 text-faint text-[9px] truncate">
                                      {d.bbox ? `[${Math.round(d.bbox.x1)}, ${Math.round(d.bbox.y1)}, ${Math.round(d.bbox.x2)}, ${Math.round(d.bbox.y2)}]` : '--'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-[10px] text-muted text-center">
                            No detections or timeline events recorded.
                          </div>
                        )}
                      </div>

                      {/* Authenticated Evidence Frames Gallery */}
                      {evidenceFrames.length > 0 && (
                        <div className="w-full mt-2 bg-graphite/80 border border-white/[0.08] rounded p-2.5 text-xs font-mono">
                          <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-white/[0.06] text-[10px]">
                            <span className="font-bold text-accent uppercase">AUTHENTICATED EVIDENCE FRAMES ({evidenceFrames.length})</span>
                            <span className="text-faint text-[9px]">SHA-256 INTEGRITY VERIFIED</span>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
                            {evidenceFrames.map((frame: any, idx: number) => (
                              <div
                                key={idx}
                                onClick={() => setSelectedEvidenceFrame(frame)}
                                className="group relative bg-panel/90 border border-white/[0.08] rounded overflow-hidden cursor-pointer hover:border-accent transition-all"
                              >
                                <img
                                  src={getEvidenceUrl(frame.artifact_key, false)}
                                  alt={`Evidence Frame #${frame.frame_number}`}
                                  className="w-full h-16 object-cover bg-black"
                                />
                                <div className="p-1 bg-graphite/90 text-[8px] space-y-0.5">
                                  <div className="flex items-center justify-between">
                                    <span className="text-paper font-bold">#{frame.frame_number}</span>
                                    <span className="text-accent">{Number(frame.timestamp_seconds).toFixed(1)}s</span>
                                  </div>
                                  <div className="flex items-center justify-between text-faint">
                                    <span>TRK-{frame.track_id}</span>
                                    <span className="text-status-warning">{frame.threat_level}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Structured Results without preview */
                    <div className="w-full h-full p-6 flex flex-col overflow-y-auto custom-scrollbar">
                      <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
                        <div className="flex items-center gap-2 text-accent font-mono text-xs">
                          <span className="material-symbols-outlined">analytics</span>
                          <span>BATCH INFERENCE RESULT — {activeAnalysisResult.overall_status || 'COMPLETED'}</span>
                        </div>
                        <span className="text-muted font-mono text-[11px]">
                          ANALYSIS ID: {activeAnalysisResult.analysis_id}
                        </span>
                      </div>
                      <div className={`grid ${activeAnalysisResult.processed_frames !== undefined ? 'grid-cols-4' : 'grid-cols-3'} gap-4 my-4`}>
                        {activeAnalysisResult.processed_frames !== undefined && (
                          <div className="p-3 rounded bg-elevated/40 border border-white/[0.06] text-center">
                            <span className="text-[10px] text-muted block">PROCESSED FRAMES</span>
                            <span className="text-2xl font-mono font-bold text-paper">
                              {activeAnalysisResult.processed_frames}
                              {activeAnalysisResult.total_video_frames ? ` / ${activeAnalysisResult.total_video_frames}` : ''}
                            </span>
                          </div>
                        )}
                        <div className="p-3 rounded bg-elevated/40 border border-white/[0.06] text-center">
                          <span className="text-[10px] text-muted block">VERIFIED DETECTIONS</span>
                          <span className="text-2xl font-mono font-bold text-paper">
                            {activeAnalysisResult.detections ? activeAnalysisResult.detections.length : 0}
                          </span>
                        </div>
                        <div className="p-3 rounded bg-elevated/40 border border-white/[0.06] text-center">
                          <span className="text-[10px] text-muted block">ACTIVE TRACKS</span>
                          <span className="text-2xl font-mono font-bold text-accent">
                            {activeAnalysisResult.tracks ? activeAnalysisResult.tracks.length : 0}
                          </span>
                        </div>
                        <div className="p-3 rounded bg-elevated/40 border border-white/[0.06] text-center">
                          <span className="text-[10px] text-muted block">TACTICAL THREAT LEVEL</span>
                          <span className="text-xl font-mono font-bold text-status-warning">
                            {activeAnalysisResult.overall_status || 'NOMINAL'}
                          </span>
                        </div>
                      </div>

                      {/* Real Detections List */}
                      <div className="flex-1 overflow-y-auto">
                        <span className="text-[11px] font-mono text-muted uppercase block mb-2">
                          VERIFIED DETECTIONS LIST
                        </span>
                        {activeAnalysisResult.detections && activeAnalysisResult.detections.length > 0 ? (
                          <div className="space-y-1.5">
                            {activeAnalysisResult.detections.map((d, i) => (
                              <div
                                key={i}
                                onClick={() => setSelectedRuntimeDetection(d)}
                                className={`p-2 rounded border font-mono text-xs flex items-center justify-between cursor-pointer transition-all ${
                                  selectedRuntimeDetection === d
                                    ? 'border-accent bg-accent/15 text-accent'
                                    : 'border-white/[0.06] bg-elevated/20 text-paper hover:border-white/[0.2]'
                                }`}
                              >
                                <div className="flex items-center gap-3">
                                  <span className="text-faint">#{i + 1}</span>
                                  <span className="font-bold uppercase">{d.class_name}</span>
                                </div>
                                <div className="flex items-center gap-4 text-muted text-[11px]">
                                  {d.bbox && <span>[{d.bbox.x1}, {d.bbox.y1}, {d.bbox.x2}, {d.bbox.y2}]</span>}
                                  <span className="text-accent font-semibold">{Math.round(d.confidence * 100)}%</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-6 text-center text-muted font-mono text-xs">
                            NO VERIFIED DETECTIONS FOUND IN PROCESSED FRAMES
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : situation?.detections && situation.detections.length > 0 ? (
              <div className="relative w-full h-full p-8 flex items-center justify-center">
                {/* Visual Canvas with detected targets */}
                <div className="relative border border-white/[0.08] rounded-lg bg-panel/30 w-full h-full overflow-hidden flex items-center justify-center">
                  <div className="absolute top-4 left-4 font-mono text-[11px] text-muted flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-accent"></span>
                    <span>SECTOR BASELINE OVERVIEW</span>
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
                  Sector is clear or awaiting asset ingest for asynchronous analysis.
                </p>
                <button
                  onClick={() => { setUploadMode('drone_image'); setIsUploadOpen(true); }}
                  className="mt-4 px-3 py-1.5 rounded bg-accent/15 border border-accent/40 text-accent text-xs font-mono hover:bg-accent/25 transition-all flex items-center gap-1.5"
                >
                  <span className="material-symbols-outlined text-[15px]">upload</span>
                  <span>INGEST TEST ASSET</span>
                </button>
              </div>
            )}
          </div>
        </section>

        {/* ============================================================ */}
        {/* RIGHT INTELLIGENCE PANEL                                    */}
        {/* ============================================================ */}
        <aside className={`${mobileTab === 'intelligence' ? 'flex' : 'hidden lg:flex'} w-full lg:w-80 xl:w-96 flex-shrink-0 bg-panel flex-col overflow-y-auto custom-scrollbar border-l border-white/[0.06]`}>
          {/* Dynamic Tactical Crossing Indicators */}
          <div className="p-4 border-b border-white/[0.06]">
            <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
              TACTICAL INTELLIGENCE
            </h2>
            {(() => {
              const indicators = activeAnalysisResult?.potential_unauthorized_crossing_indicators ||
                activeAnalysisResult?.report?.crossing_indicators;

              if (indicators && indicators.length > 0) {
                return (
                  <div className="mt-2 space-y-2">
                    {indicators.map((ind: any, i: number) => {
                      const isInternational = ind.geographic_reference_type === 'INTERNATIONAL_BORDER';
                      const label = isInternational
                        ? 'POTENTIAL INTERNATIONAL BORDER CROSSING'
                        : (ind.crossing_type || ind.indicator_type || 'RESTRICTED GEOFENCE EVENT');
                      return (
                        <div key={i} className="p-2.5 rounded bg-status-critical/10 border border-status-critical/25">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-paper uppercase">
                              {label}
                            </span>
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-status-critical/20 text-status-critical font-bold">
                              {ind.confidence ? `${Math.round(ind.confidence * 100)}%` : 'DETECTED'}
                            </span>
                          </div>
                          {ind.description && (
                            <p className="text-[10px] text-muted mt-1 leading-normal font-mono">
                              {ind.description}
                            </p>
                          )}
                          <div className="text-[9px] text-faint font-mono mt-1 flex items-center justify-between">
                            <span>REF: {isInternational ? 'INTERNATIONAL BORDER' : 'OPERATIONAL GEOFENCE'}</span>
                            {ind.coordinates && (
                              <span>PIX: [{Array.isArray(ind.coordinates) ? ind.coordinates.join(', ') : ind.coordinates}]</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              }

              if (activeAnalysisResult) {
                return (
                  <div className="mt-2 p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                    <span className="text-[11px] font-mono text-muted block">
                      NO ACTIVE CROSSING INDICATORS
                    </span>
                    <span className="text-[9px] font-mono text-faint mt-0.5 block">
                      Verified perimeter: Zero crossing cues detected
                    </span>
                  </div>
                );
              }

              return (
                <div className="mt-2 p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                  <span className="text-[11px] font-mono text-faint block">
                    CROSSING INDICATOR DATA UNAVAILABLE
                  </span>
                  <span className="text-[9px] font-mono text-faint mt-0.5 block">
                    Awaiting asset ingest for tactical crossing analysis
                  </span>
                </div>
              );
            })()}
          </div>

          {/* Dedicated Section 12 Geo Context UI */}
          <div className="p-4 border-b border-border bg-slate-50/70">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
                GEOREFERENCE & JURISDICTION
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono ${
                operatorLocation
                  ? 'bg-status-ai/15 text-status-ai border border-status-ai/25'
                  : 'bg-elevated text-faint border border-white/[0.06]'
              }`}>
                {operatorLocation ? operatorLocation.location_precision : 'UNAVAILABLE'}
              </span>
            </div>

            {operatorLocation ? (
              <div className="space-y-2 text-xs font-mono">
                <div className="p-2.5 bg-graphite/50 rounded border border-white/[0.04] space-y-1.5">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-faint">SOURCE:</span>
                    <span className="text-paper">{operatorLocation.location_source}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-faint">METHOD:</span>
                    <span className="text-accent">{operatorLocation.location_method || 'MANUAL_COORDINATES'}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-faint">COORDINATES:</span>
                    <span className="text-paper">{operatorLocation.latitude.toFixed(4)}, {operatorLocation.longitude.toFixed(4)}</span>
                  </div>
                  {operatorLocation.label && (
                    <div className="text-[10px] text-muted truncate border-t border-white/[0.04] pt-1">
                      LABEL: {operatorLocation.label}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                    <span className="text-faint block text-[9px]">STATE / REGION</span>
                    <span className="text-paper font-medium">{operatorLocation.state || 'Admin Area'}</span>
                  </div>
                  <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                    <span className="text-faint block text-[9px]">COUNTRY</span>
                    <span className="text-paper font-medium">{operatorLocation.country || 'India'}</span>
                  </div>
                </div>

                <div className="p-2 bg-graphite/40 rounded border border-white/[0.04] text-[10px]">
                  <span className="text-faint block text-[9px]">INTERNATIONAL BORDER REFERENCE</span>
                  <span className={operatorLocation.relevant_border === 'BORDER CONTEXT UNAVAILABLE' ? 'text-status-warning font-bold' : 'text-paper'}>
                    {operatorLocation.relevant_border || 'BORDER CONTEXT UNAVAILABLE'}
                  </span>
                  {operatorLocation.relevant_border === 'BORDER CONTEXT UNAVAILABLE' ? (
                    <p className="text-[8.5px] text-amber-300/90 mt-1 leading-tight font-mono">
                      Perception remains sensor-frame relative. No authoritative border geometry is available for this analysis.
                    </p>
                  ) : (
                    <span className="text-[8px] text-faint block mt-0.5">
                      Official Survey of India demarcation only
                    </span>
                  )}
                </div>

                <div className="p-2 bg-graphite/40 rounded border border-white/[0.04] text-[10px]">
                  <span className="text-faint block text-[9px]">OPERATIONAL GEOFENCE</span>
                  <span className="text-paper">
                    {activeAnalysisResult?.potential_unauthorized_crossing_indicators?.length
                      ? 'ACTIVE RESTRICTED-ZONE EVENT'
                      : 'RESTRICTED CORRIDOR ACTIVE'}
                  </span>
                  <span className="text-[8px] text-muted/70 block mt-0.5">
                    Tactical geofence != International border
                  </span>
                </div>

                <button
                  onClick={() => setIsLocationModalOpen(true)}
                  className="w-full mt-1 py-1 rounded bg-elevated/70 border border-white/[0.08] hover:border-accent/40 text-accent text-[10px] font-mono hover:bg-elevated transition-all flex items-center justify-center gap-1"
                >
                  <span className="material-symbols-outlined text-[13px]">edit_location</span>
                  <span>CHANGE LOCATION</span>
                </button>
              </div>
            ) : (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint block">
                  GEO-CONTEXT UNAVAILABLE
                </span>
                <span className="text-[9px] font-mono text-muted/60 mt-1 block">
                  Asset lacks embedded GPS telemetry.
                </span>
                <button
                  onClick={() => setIsLocationModalOpen(true)}
                  className="mt-2 px-2.5 py-1 rounded bg-accent/15 border border-accent/40 text-accent text-[10px] font-mono hover:bg-accent/25 transition-all flex items-center justify-center gap-1 mx-auto"
                >
                  <span className="material-symbols-outlined text-[13px]">add_location_alt</span>
                  <span>PROVIDE APPROXIMATE LOCATION</span>
                </button>
              </div>
            )}
          </div>

          {/* Sector Vulnerability Index */}
          <div className="p-4 border-b border-white/[0.06]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
                SECTOR VULNERABILITY
              </span>
              <button
                onClick={async () => {
                  setEvaluatingBoundary(true);
                  try {
                    // Collect real evidence points if operator location or detections exist
                    const points: any[] = [];
                    if (operatorLocation) {
                      points.push({
                        latitude: operatorLocation.latitude,
                        longitude: operatorLocation.longitude,
                        point_id: 'OP_LOCATION',
                      });
                    }
                    const res = await boundariesApi.evaluate('DEMO_VULNERABILITY_BOUNDARY', {
                      evidence_points: points.length > 0 ? points : [{ latitude: 32.65, longitude: 74.85, weight: 1.0 }],
                    });
                    if (res.success && res.data) {
                      setDemoBoundaryResult(res.data);
                    }
                  } catch (e: any) {
                    console.warn('Boundary evaluation error:', e);
                  } finally {
                    setEvaluatingBoundary(false);
                  }
                }}
                disabled={evaluatingBoundary}
                className="px-1.5 py-0.5 rounded bg-accent/15 border border-accent/30 text-accent text-[9px] font-mono hover:bg-accent/25 transition-all flex items-center gap-1 disabled:opacity-50"
                title="Evaluate spatial intersection against Demo Pentagon Boundary (Synthetic AOI)"
              >
                <span className="material-symbols-outlined text-[11px]">pentagon</span>
                <span>{evaluatingBoundary ? 'EVALUATING...' : 'DEMO AOI (SYNTHETIC)'}</span>
              </button>
            </div>

            {demoBoundaryResult ? (
              <div className="space-y-2 font-mono">
                <div className="p-2.5 bg-graphite/50 rounded border border-accent/20">
                  <div className="flex items-center justify-between text-[10px] mb-1">
                    <span className="text-paper font-semibold">{demoBoundaryResult.boundary_name}</span>
                    <span className="text-[8px] px-1.5 py-0.2 rounded bg-elevated text-status-warning border border-status-warning/30 font-bold">
                      SYNTHETIC DEMO AOI (NON-AUTHORITATIVE)
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between mb-1">
                    <span className="text-xl font-mono font-bold text-accent">
                      {demoBoundaryResult.vulnerability_score !== null && demoBoundaryResult.vulnerability_score !== undefined
                        ? `${demoBoundaryResult.vulnerability_score.toFixed(1)} / 100`
                        : 'INSUFFICIENT EVIDENCE'}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded ${
                      demoBoundaryResult.vulnerability_status === 'COMPUTED'
                        ? 'bg-status-warning/15 text-status-warning'
                        : 'bg-elevated text-faint'
                    }`}>
                      {demoBoundaryResult.vulnerability_status}
                    </span>
                  </div>
                  <div className="text-[9px] text-faint leading-tight space-y-0.5">
                    <div>INTERSECTING EVIDENCE: {demoBoundaryResult.intersecting_evidence_count} / {demoBoundaryResult.total_evidence_evaluated}</div>
                    <div className="text-status-warning text-[8px] font-semibold">{demoBoundaryResult.disclaimer}</div>
                  </div>
                </div>
              </div>
            ) : situation?.vulnerability_score !== undefined && situation.vulnerability_score !== null ? (
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
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center space-y-1">
                <span className="text-[11px] font-mono text-faint block font-semibold">
                  BORDER CONTEXT NOT SET
                </span>
                <span className="text-[9px] font-mono text-muted/60 block">
                  NO DEMO ZONE CONFIGURED — Spatial boundary intersection requires an active zone definition.
                </span>
                <button
                  onClick={() => setIsZoneConfigOpen(true)}
                  className="mt-1 px-2.5 py-0.5 rounded bg-elevated border border-white/[0.1] text-accent text-[9px] font-mono hover:bg-elevated/80 transition-all cursor-pointer"
                >
                  CONFIGURE DEMO ZONE
                </button>
              </div>
            )}
          </div>

          {/* Meteorological Data */}
          <div className="p-4 border-b border-white/[0.06]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
                ENVIRONMENTAL CONDITIONS
              </span>
              {operatorLocation && (
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-status-ai/15 text-status-ai border border-status-ai/25">
                  OPERATOR-PROVIDED
                </span>
              )}
            </div>

            {weatherLoading ? (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center font-mono text-[10px] text-muted">
                <span className="material-symbols-outlined text-xs animate-spin mr-1">progress_activity</span>
                FETCHING OPEN-METEO WEATHER...
              </div>
            ) : weather && weather.status === 'AVAILABLE' ? (
              <div>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono mb-2">
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
                <div className="text-[9px] font-mono text-faint flex items-center justify-between px-1">
                  <span>
                    {operatorLocation ? `SOURCE: ${operatorLocation.location_source} (${operatorLocation.location_precision})` : 'SOURCE: ASSET METADATA'}
                  </span>
                  {operatorLocation?.label && (
                    <span className="truncate max-w-[120px]">{operatorLocation.label}</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint block">
                  WEATHER DATA UNAVAILABLE
                </span>
                <span className="text-[9px] font-mono text-muted/60 mt-1 block">
                  {operatorLocation
                    ? 'Failed to fetch weather from provider for supplied coordinates.'
                    : 'No verified geographic coordinates available for this asset.'}
                </span>
                {!operatorLocation && (
                  <button
                    onClick={() => setIsLocationModalOpen(true)}
                    className="mt-2 px-2 py-1 rounded bg-elevated border border-white/[0.08] text-accent text-[10px] font-mono hover:bg-elevated/80 transition-all"
                  >
                    PROVIDE APPROXIMATE LOCATION
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Selected Target Telemetry */}
          <div className="p-4 flex-1">
            <span className="text-[11px] font-mono text-muted uppercase tracking-wider block mb-2">
              SELECTED TARGET TELEMETRY
            </span>
            {selectedRuntimeDetection ? (
              <div className="space-y-2 text-xs font-mono bg-graphite/40 p-3 rounded border border-accent/20">
                <div className="flex justify-between">
                  <span className="text-faint">SOURCE:</span>
                  <span className="text-paper uppercase">{selectedRuntimeDetection.source}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-faint">CLASS:</span>
                  <span className="text-accent uppercase font-bold">{selectedRuntimeDetection.class_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-faint">CONFIDENCE:</span>
                  <span className="text-accent font-semibold">{Math.round(selectedRuntimeDetection.confidence * 100)}%</span>
                </div>
                {selectedRuntimeDetection.bbox && (
                  <div className="flex justify-between">
                    <span className="text-faint">BOUNDING BOX:</span>
                    <span className="text-paper text-[10px]">
                      [{selectedRuntimeDetection.bbox.x1}, {selectedRuntimeDetection.bbox.y1}, {selectedRuntimeDetection.bbox.x2}, {selectedRuntimeDetection.bbox.y2}]
                    </span>
                  </div>
                )}
                {selectedRuntimeDetection.obb_points && (
                  <div>
                    <span className="text-faint block mb-1">OBB VERTICES (4-PT):</span>
                    <span className="text-paper text-[9px] block">
                      {selectedRuntimeDetection.obb_points.map(p => `(${p.x},${p.y})`).join(' ')}
                    </span>
                  </div>
                )}
                <div className="pt-2 mt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px]">
                  <span className="text-faint">TARGET GEOLOCATION:</span>
                  <span className="text-status-warning bg-status-warning/10 px-1.5 py-0.5 rounded text-[9px] font-bold">
                    UNAVAILABLE (Pixel Space)
                  </span>
                </div>
              </div>
            ) : selectedTarget ? (
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
                <div className="pt-2 mt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px]">
                  <span className="text-faint">TARGET GEOLOCATION:</span>
                  <span className="text-status-warning bg-status-warning/10 px-1.5 py-0.5 rounded text-[9px] font-bold">
                    UNAVAILABLE (Pixel Space)
                  </span>
                </div>
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
      <footer className="h-28 bg-white border-t border-border p-4 flex flex-col justify-between flex-shrink-0 z-30 shadow-xs">
        <div className="flex items-center justify-between font-mono text-[10px] text-slate-500 uppercase tracking-wider mb-2">
          <span>OPERATIONAL EVENT LOG (CHRONOLOGICAL)</span>
          <span>{events.length} EVENTS RECORDED</span>
        </div>

        <div className="flex-1 flex gap-3 overflow-x-auto custom-scrollbar items-center pb-1">
          {events.length > 0 ? (
            events.map((ev) => (
              <div
                key={ev.id}
                className="flex-shrink-0 w-64 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono flex flex-col justify-between shadow-2xs"
              >
                <div className="flex items-center justify-between text-[10px] text-slate-400">
                  <span>{new Date(ev.created_at).toISOString().substring(11, 19)} UTC</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
                      ev.severity === 'CRITICAL'
                        ? 'bg-status-critical/10 text-status-critical'
                        : 'bg-status-warning/10 text-status-warning'
                    }`}
                  >
                    {ev.severity}
                  </span>
                </div>
                <div className="text-slate-800 text-[11px] font-semibold truncate mt-1">
                  {ev.title}
                </div>
              </div>
            ))
          ) : (
            <div className="w-full text-center text-[11px] font-mono text-slate-400">
              NO SITUATION EVENTS LOGGED
            </div>
          )}
        </div>
      </footer>

      {/* Upload & Perception Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        defaultMode={uploadMode}
        onAnalysisSuccess={(res, meta) => {
          setActiveAnalysisResult(res);
          if (meta?.imageUrl) {
            setAnalyzedImageUrl(meta.imageUrl);
            setAnalyzedVideoUrl(null);
          } else if (meta?.videoUrl) {
            setAnalyzedVideoUrl(meta.videoUrl);
            setAnalyzedImageUrl(null);
          }
          if (res.detections && res.detections.length > 0) {
            setSelectedRuntimeDetection(res.detections[0]);
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
        currentMode="border"
        onSelectAnalysis={async (item) => {
          const targetId = item.analysis_id || item.job_id;
          if (targetId) {
            setSearchParams({ analysis_id: targetId });
            try {
              const resp = await analysisApi.getById(targetId);
              if (resp.success && resp.data) {
                setActiveAnalysisResult(resp.data);
                setVideoError(null);
                if (resp.data.annotated_image_base64) {
                  setAnalyzedImageUrl(`data:image/jpeg;base64,${resp.data.annotated_image_base64}`);
                  setViewMode('annotated');
                } else if (resp.data.annotated_video_artifact) {
                  setViewMode('annotated');
                  if (resp.data.source_artifact?.artifact_key) {
                    setAnalyzedVideoUrl(getEvidenceUrl(resp.data.source_artifact.artifact_key, false));
                  }
                }
              }
            } catch (err) {
              console.warn('Could not reopen analysis:', err);
            }
          }
        }}
      />

      {/* Operator-Provided Approximate Location Modal */}
      <OperatorLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        existingLocation={operatorLocation}
        onConfirmLocation={async (loc: LocationProvenance) => {
          setOperatorLocation(loc);
          if (loc) {
            setWeatherLoading(true);
            try {
              const [weatherRes, adminRes, borderRes] = await Promise.all([
                situationsApi.getWeather(situation?.id || '00000000-0000-0000-0000-000000000001', loc.latitude, loc.longitude),
                geospatialApi.resolveAdmin(loc.latitude, loc.longitude).catch(() => null),
                geospatialApi.resolveBorder(loc.latitude, loc.longitude).catch(() => null),
              ]);

              if (weatherRes.success && weatherRes.data) {
                setWeather(weatherRes.data);
              }

              const enriched: LocationProvenance = { ...loc };
              if (adminRes && adminRes.success && adminRes.data) {
                enriched.state = adminRes.data.state || undefined;
                enriched.country = adminRes.data.country || 'India';
              }
              if (borderRes && borderRes.success && borderRes.data && borderRes.data.available) {
                enriched.relevant_border = borderRes.data.nearest_boundary_name || 'India-Pakistan';
              } else {
                enriched.relevant_border = 'BORDER CONTEXT UNAVAILABLE';
              }
              setOperatorLocation(enriched);
            } catch (err) {
              console.error('Failed to resolve geospatial enrichment for operator coordinates:', err);
            } finally {
              setWeatherLoading(false);
            }
          }
        }}
      />

      {/* Explicit Border Zone Configuration Modal */}
      {isZoneConfigOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-panel border border-white/[0.1] rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-2">
              <div className="flex items-center gap-2 text-accent">
                <span className="material-symbols-outlined text-[18px]">polyline</span>
                <span className="font-bold uppercase text-sm">Configure Operational Border Zone</span>
              </div>
              <button
                onClick={() => setIsZoneConfigOpen(false)}
                className="text-muted hover:text-paper"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            <p className="text-muted text-[11px] leading-relaxed">
              Define the authoritative border zone polygon for real-time vehicle containment, entry/exit detection, and threat assessment. Leaving this unconfigured maintains truthful &ldquo;BORDER CONTEXT NOT SET&rdquo; mode with zero synthetic sector assumptions.
            </p>

            <div className="space-y-2">
              <label className="text-[10px] text-faint block uppercase">ZONE PRESETS:</label>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setActiveConfiguredZone([
                      [32.65, 74.85],
                      [32.68, 74.87],
                      [32.67, 74.92],
                      [32.63, 74.90],
                      [32.62, 74.86],
                    ]);
                    setActiveSectorName('DEMO BORDER PERIMETER');
                    setIsZoneConfigOpen(false);
                  }}
                  className="px-3 py-1.5 rounded bg-accent/15 border border-accent/30 text-accent text-[11px] hover:bg-accent/25 transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[14px]">pentagon</span>
                  <span>LOAD DEMO PERIMETER</span>
                </button>

                <button
                  onClick={() => {
                    setActiveConfiguredZone(null);
                    setActiveSectorName('');
                    setIsZoneConfigOpen(false);
                  }}
                  className="px-3 py-1.5 rounded bg-elevated border border-white/[0.08] text-status-warning hover:bg-elevated/80 text-[11px] transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[14px]">clear</span>
                  <span>CLEAR (UNSET CONTEXT)</span>
                </button>
              </div>
            </div>

            <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px] text-faint">
              <span>CURRENT STATUS: <span className="text-paper">{activeConfiguredZone ? activeSectorName || 'ZONE ACTIVE' : 'NO DEMO ZONE CONFIGURED'}</span></span>
              <button
                onClick={() => setIsZoneConfigOpen(false)}
                className="px-3 py-1.5 rounded bg-elevated hover:bg-elevated/80 text-paper cursor-pointer"
              >
                CLOSE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Selected Evidence Frame Inspection Modal */}
      {selectedEvidenceFrame && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-panel border border-white/[0.1] rounded-xl max-w-2xl w-full p-5 space-y-4 shadow-2xl font-mono text-xs">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-2">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-accent text-[18px]">verified</span>
                <span className="font-bold uppercase text-paper">
                  Evidence Frame #{selectedEvidenceFrame.frame_number} // TRK-{selectedEvidenceFrame.track_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedEvidenceFrame(null)}
                className="text-muted hover:text-paper cursor-pointer"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            <div className="relative border border-white/[0.08] rounded overflow-hidden bg-black flex items-center justify-center max-h-[60vh]">
              <img
                src={getEvidenceUrl(selectedEvidenceFrame.artifact_key, false)}
                alt={`Evidence Frame #${selectedEvidenceFrame.frame_number}`}
                className="max-w-full max-h-[55vh] object-contain"
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] p-2.5 bg-graphite/70 rounded border border-white/[0.04]">
              <div>
                <span className="text-faint block">TIMESTAMP:</span>
                <span className="text-paper font-bold">{Number(selectedEvidenceFrame.timestamp_seconds).toFixed(1)}s</span>
              </div>
              <div>
                <span className="text-faint block">TRACK ID:</span>
                <span className="text-status-ai font-bold">TRK-{selectedEvidenceFrame.track_id}</span>
              </div>
              <div>
                <span className="text-faint block">THREAT LEVEL:</span>
                <span className={`font-bold ${
                  selectedEvidenceFrame.threat_level === 'CRITICAL' ? 'text-status-critical' : selectedEvidenceFrame.threat_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                }`}>
                  {selectedEvidenceFrame.threat_level}
                </span>
              </div>
              <div>
                <span className="text-faint block">SHA-256:</span>
                <span className="text-accent truncate block" title={selectedEvidenceFrame.sha256}>
                  {selectedEvidenceFrame.sha256 ? `${selectedEvidenceFrame.sha256.substring(0, 10)}...` : 'VERIFIED'}
                </span>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={async () => {
                  const dlUrl = getEvidenceUrl(selectedEvidenceFrame.artifact_key, true);
                  const filename = `AERION_evidence_frame_${selectedEvidenceFrame.frame_number}_trk${selectedEvidenceFrame.track_id}.jpg`;
                  try {
                    await downloadAuthenticatedArtifact(dlUrl, filename);
                  } catch (e: any) {
                    alert(e.message || 'Download failed');
                  }
                }}
                className="px-3 py-1.5 rounded bg-accent text-graphite font-bold text-xs hover:bg-accent/90 flex items-center gap-1 cursor-pointer"
              >
                <span className="material-symbols-outlined text-[14px]">download</span>
                <span>DOWNLOAD EVIDENCE JPEG</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
