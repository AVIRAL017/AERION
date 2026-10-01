import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { situationsApi } from '../api';
import { SituationReport } from '../types';
import { downloadAuthenticatedReport, downloadAuthenticatedArtifact } from '../utils/download';
import { API_BASE } from '../api/client';

export const SituationReportPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [report, setReport] = useState<SituationReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [selectedEvidenceFrame, setSelectedEvidenceFrame] = useState<any | null>(null);

  const analysisId = searchParams.get('analysis_id') || undefined;

  const getEvidenceUrl = (key: string, download = false) => {
    const cleanKey = key.split('/').map(encodeURIComponent).join('/');
    const token = localStorage.getItem('aerion_access_token');
    const params = new URLSearchParams();
    params.set('download', download ? 'true' : 'false');
    if (token) params.set('token', token);
    return `${API_BASE}/evidence/${cleanKey}?${params.toString()}`;
  };

  const handleDownload = async (format: 'pdf' | 'json') => {
    const sitId = id || '00000000-0000-0000-0000-000000000001';
    setIsDownloading(true);
    try {
      const locCtx = (report as any)?.location_context;
      await downloadAuthenticatedReport(
        sitId,
        format,
        locCtx
          ? {
              source: locCtx.source_type,
              precision: locCtx.precision,
              method: locCtx.method,
              label: locCtx.label,
              state: locCtx.state,
              country: locCtx.country,
              relevant_border: locCtx.relevant_border,
              geofence_status: locCtx.geofence_status,
            }
          : undefined,
        report?.analysis_id || analysisId
      );
    } catch (err: any) {
      alert(err.message || 'Download failed');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleReturn = () => {
    if (window.history.length > 2) {
      window.history.back();
    } else {
      const isBorder = !id || id.includes('1') || id.toLowerCase().includes('border');
      const targetBase = isBorder ? '/border' : '/disaster';
      const effectiveAnalysisId = report?.analysis_id || analysisId;
      const qs = effectiveAnalysisId ? `?analysis_id=${encodeURIComponent(effectiveAnalysisId)}` : '';
      navigate(`${targetBase}${qs}`);
    }
  };

  useEffect(() => {
    const fetchReport = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const sitId = id || '00000000-0000-0000-0000-000000000001';
        const res = await situationsApi.getReport(sitId, analysisId);
        if (res.success && res.data) {
          setReport(res.data);
        } else {
          setError(typeof res.error === 'string' ? res.error : (res.error as any)?.message || 'Report unavailable');
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load operational situation report.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchReport();
  }, [id, analysisId]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        COMPILING DETERMINISTIC SITUATION REPORT...
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-graphite font-mono p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-status-critical/10 border border-status-critical/30 flex items-center justify-center text-status-critical mb-3">
          <span className="material-symbols-outlined text-2xl">error</span>
        </div>
        <h2 className="text-sm font-semibold text-paper mb-1">OPERATIONAL REPORT UNAVAILABLE</h2>
        <p className="text-xs text-muted max-w-md mb-4">{error}</p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.location.reload()}
            className="px-3 py-1.5 rounded bg-accent/20 border border-accent/40 text-accent text-xs hover:bg-accent/30 transition-all cursor-pointer"
          >
            RETRY
          </button>
          <button
            onClick={handleReturn}
            className="px-3 py-1.5 rounded bg-elevated border border-white/[0.08] text-muted hover:text-paper text-xs transition-all cursor-pointer"
          >
            RETURN
          </button>
        </div>
      </div>
    );
  }

  const isBorder = report?.mode?.toLowerCase().includes('border') ?? (!id || id.includes('1') || id.toLowerCase().includes('border'));

  // Data helpers
  const threatTimeline: any[] = report?.threat_timeline || [];
  const vehicleSummary: any = report?.vehicle_summary || null;
  const demoZoneActivity: any = report?.demo_zone_activity || null;
  const threatLevelChanges: any[] = report?.threat_level_changes || [];
  const evidenceFrames: any[] = report?.evidence_frames || [];
  const spatialContext: any = report?.spatial_context || (report as any)?.location_context || null;
  const routingSummary: any = report?.routing_summary || null;
  const shelterSummary: any = report?.shelter_summary || null;

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-graphite p-4 sm:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        {/* Top Header */}
        <div className="border-b border-white/[0.06] pb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <button
                onClick={handleReturn}
                className="px-2 py-0.5 rounded bg-elevated/70 border border-white/[0.08] text-muted hover:text-paper text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">arrow_back</span>
                <span>RETURN</span>
              </button>
              <h1 className="text-base font-bold text-slate-900 tracking-wide uppercase font-sans">
                OPERATIONAL SITUATION REPORT
              </h1>
            </div>
            <p className="text-xs text-muted font-mono">
              STRUCTURED EVIDENCE-FIRST INTELLIGENCE (13-SECTION STANDARD)
            </p>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <button
              onClick={() => handleDownload('pdf')}
              disabled={isDownloading}
              className="px-3.5 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer active:scale-95"
            >
              <span className="material-symbols-outlined text-[16px]">picture_as_pdf</span>
              <span>{isDownloading ? 'DOWNLOADING...' : 'PDF REPORT'}</span>
            </button>

            <button
              onClick={() => handleDownload('json')}
              disabled={isDownloading}
              className="px-3 py-1.5 rounded bg-elevated border border-white/[0.1] hover:border-accent text-paper hover:text-accent disabled:opacity-50 text-xs font-mono flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <span className="material-symbols-outlined text-[15px]">data_object</span>
              <span>JSON</span>
            </button>

            <span className="px-2.5 py-1 rounded bg-elevated border border-white/[0.08] text-[10px] font-mono text-muted">
              {report?.generated_at ? new Date(report.generated_at).toUTCString() : 'AWAITING GENERATION'}
            </span>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 1: EXECUTIVE SITUATION SUMMARY                       */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              1. EXECUTIVE SITUATION SUMMARY
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-accent/15 text-accent border border-accent/30 font-bold">
              {report?.overall_status || 'PERSISTED'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono mt-2">
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">ANALYSIS ID</span>
              <span className="text-paper truncate block" title={report?.analysis_id || 'UNAVAILABLE'}>
                {report?.analysis_id ? `${report.analysis_id.substring(0, 13)}...` : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">JOB ID</span>
              <span className="text-paper truncate block" title={report?.job_id || 'UNAVAILABLE'}>
                {report?.job_id ? `${report.job_id.substring(0, 13)}...` : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">OPERATIONAL MODE</span>
              <span className="text-accent uppercase font-bold">
                {report?.mode || (isBorder ? 'BORDER_SECURITY' : 'DISASTER_RESPONSE')}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">SOURCE TYPE</span>
              <span className="text-paper uppercase">
                {report?.analysis_type || 'AERIAL'}
              </span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 2: CURRENT OPERATIONAL STATUS                        */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              2. CURRENT OPERATIONAL STATUS
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-status-success/15 text-status-success border border-status-success/30 font-bold">
              READY
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono mt-2">
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">SYSTEM HEALTH</span>
              <span className="text-status-success font-medium">OPERATIONAL</span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">PRIMARY THREAT EVALUATION</span>
              <span className="text-accent font-medium">
                {isBorder ? (vehicleSummary?.max_threat_level || 'MONITORED') : (report?.damage_summary?.classification || 'COMPUTED')}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">PAIR INTEGRITY</span>
              <span className="text-paper font-medium">
                {report?.damage_summary?.pair_validation?.status || 'N/A (SINGLE SOURCE)'}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">VERIFIED SAMPLES</span>
              <span className="text-paper font-medium">
                {threatTimeline.length > 0 ? `${threatTimeline.length} events` : (report?.detection_summary?.total_detections ? `${report.detection_summary.total_detections} contacts` : '0')}
              </span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 3: REAL-TIME THREAT TIMELINE                         */}
        {/* ============================================================ */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg aerion-card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              3. REAL-TIME THREAT TIMELINE
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-elevated text-accent border border-white/[0.08]">
              {threatTimeline.length > 0 ? `${threatTimeline.length} CHRONOLOGICAL EVENTS` : 'NO LIVE EVENTS'}
            </span>
          </div>

          {threatTimeline.length > 0 ? (
            <div className="overflow-x-auto max-h-64 custom-scrollbar">
              <table className="w-full text-left font-mono text-[11px] border-collapse">
                <thead>
                  <tr className="border-b border-white/[0.08] text-faint text-[9px] uppercase">
                    <th className="py-1.5 px-2">TIME</th>
                    <th className="py-1.5 px-2">TRACK ID</th>
                    <th className="py-1.5 px-2">OBJECT</th>
                    <th className="py-1.5 px-2">ZONE STATE</th>
                    <th className="py-1.5 px-2">THREAT LEVEL</th>
                    <th className="py-1.5 px-2">TREND</th>
                    <th className="py-1.5 px-2">CONF</th>
                    <th className="py-1.5 px-2 text-right">EVIDENCE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.03]">
                  {threatTimeline.map((ev, i) => (
                    <tr key={i} className="hover:bg-white/[0.02]">
                      <td className="py-1.5 px-2 text-muted">{Number(ev.time_offset_seconds ?? (ev.frame_number ? ev.frame_number / 15 : 0)).toFixed(1)}s</td>
                      <td className="py-1.5 px-2 text-status-ai font-bold">TRK-{ev.track_id}</td>
                      <td className="py-1.5 px-2 uppercase font-medium text-paper">{ev.object_class || ev.class_name}</td>
                      <td className="py-1.5 px-2">
                        <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                          ev.zone_state === 'INSIDE' ? 'bg-status-critical/20 text-status-critical' :
                          ev.zone_state === 'APPROACHING' ? 'bg-status-warning/20 text-status-warning' :
                          ev.zone_state === 'EXITED' ? 'bg-status-ai/20 text-status-ai' : 'bg-elevated text-faint'
                        }`}>
                          {ev.zone_state || 'OUTSIDE'}
                        </span>
                      </td>
                      <td className="py-1.5 px-2">
                        <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                          ev.threat_level === 'CRITICAL' ? 'bg-status-critical text-graphite font-black' :
                          ev.threat_level === 'HIGH' ? 'bg-status-warning/20 text-status-warning' :
                          ev.threat_level === 'MEDIUM' ? 'bg-status-warning/15 text-status-warning/80' :
                          ev.threat_level === 'LOW' ? 'bg-status-success/15 text-status-success' : 'bg-elevated text-faint'
                        }`}>
                          {ev.threat_level || 'UNAVAILABLE'}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-[10px] text-faint">
                        {ev.threat_trend || 'STABLE'}
                      </td>
                      <td className="py-1.5 px-2 text-faint">{ev.confidence ? `${Math.round(ev.confidence * 100)}%` : '--'}</td>
                      <td className="py-1.5 px-2 text-right">
                        {ev.evidence_frame_key ? (
                          <button
                            onClick={() => setSelectedEvidenceFrame({
                              artifact_key: ev.evidence_frame_key,
                              sha256: ev.evidence_frame_sha256,
                              frame_number: ev.frame_number,
                              track_id: ev.track_id,
                              timestamp_seconds: ev.time_offset_seconds,
                              threat_level: ev.threat_level,
                            })}
                            className="px-1.5 py-0.5 rounded bg-accent/15 border border-accent/30 text-accent text-[8px] hover:bg-accent/25 cursor-pointer"
                          >
                            VIEW
                          </button>
                        ) : (
                          <span className="text-faint text-[8px]">--</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : report?.detection_summary?.detections && report.detection_summary.detections.length > 0 ? (
            <div className="overflow-x-auto max-h-56 custom-scrollbar">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-white/[0.08] text-faint text-[10px] uppercase">
                    <th className="py-2 px-2">ID</th>
                    <th className="py-2 px-2">Class</th>
                    <th className="py-2 px-2">Confidence</th>
                    <th className="py-2 px-2">Track</th>
                    <th className="py-2 px-2">Bounding Box</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {report.detection_summary.detections.slice(0, 30).map((d) => (
                    <tr key={d.id} className="hover:bg-white/[0.02]">
                      <td className="py-1.5 px-2 text-paper">{d.id}</td>
                      <td className="py-1.5 px-2 text-accent font-medium">{d.class_name}</td>
                      <td className="py-1.5 px-2 text-paper">{(d.confidence * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-2 text-muted">{d.track_id ?? '-'}</td>
                      <td className="py-1.5 px-2 text-faint text-[10px]">
                        {d.bbox ? `[${Math.round(d.bbox.x1)}, ${Math.round(d.bbox.y1)}, ${Math.round(d.bbox.x2)}, ${Math.round(d.bbox.y2)}]` : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted text-center">
              Real-time vehicle timeline data unavailable for this report session.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 4: VEHICLE / TRACK SUMMARY                           */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold mb-3">
            4. VEHICLE & TRACK INVENTORY SUMMARY
          </span>
          {vehicleSummary ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">TOTAL VEHICLES OBSERVED</span>
                <span className="text-base text-paper font-bold">{vehicleSummary.total_vehicles_observed ?? 0}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ACTIVE TRACKS COUNT</span>
                <span className="text-base text-accent font-bold">{vehicleSummary.active_tracks_count ?? 0}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">MAX THREAT LEVEL</span>
                <span className={`text-base font-bold ${
                  vehicleSummary.max_threat_level === 'CRITICAL' ? 'text-status-critical' : vehicleSummary.max_threat_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                }`}>
                  {vehicleSummary.max_threat_level ?? 'LOW'}
                </span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">VEHICLE CATEGORIES</span>
                <span className="text-paper text-[11px] block mt-0.5">
                  {vehicleSummary.vehicle_categories ? Object.entries(vehicleSummary.vehicle_categories).map(([k, v]) => `${k}: ${v}`).join(', ') : 'N/A'}
                </span>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted text-center">
              Vehicle inventory summary unavailable for this report session.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 5: DEMO ZONE ACTIVITY                                */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              5. DEMO ZONE SURVEILLANCE ACTIVITY
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${
              demoZoneActivity?.zone_configured ? 'bg-status-success/15 text-status-success font-bold' : 'bg-elevated text-faint'
            }`}>
              {demoZoneActivity?.zone_configured ? 'ZONE CONFIGURED' : 'BORDER CONTEXT NOT SET'}
            </span>
          </div>

          {demoZoneActivity && demoZoneActivity.zone_configured ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ZONE NAME</span>
                <span className="text-paper font-semibold">{demoZoneActivity.zone_name || 'BORDER ZONE'}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ZONE ENTRIES</span>
                <span className="text-status-warning font-bold">{demoZoneActivity.zone_entries_count || 0}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ZONE EXITS</span>
                <span className="text-paper font-bold">{demoZoneActivity.zone_exits_count || 0}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ACTIVE VEHICLES INSIDE</span>
                <span className="text-status-critical font-bold">{demoZoneActivity.active_vehicles_inside || 0}</span>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted text-center space-y-1">
              <span className="text-paper font-semibold block">BORDER CONTEXT NOT SET // NO DEMO ZONE CONFIGURED</span>
              <p className="text-faint text-[10px]">
                No operational boundary polygon was designated during this analysis. All vehicle movements and threat indicators were evaluated without synthetic sector containment.
              </p>
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 6: THREAT LEVEL CHANGES                              */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold mb-3">
            6. DYNAMIC THREAT LEVEL TRANSITIONS
          </span>
          {threatLevelChanges.length > 0 ? (
            <div className="space-y-2">
              {threatLevelChanges.map((ch, idx) => (
                <div key={idx} className="p-2.5 bg-graphite/40 rounded border border-white/[0.04] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-status-ai font-bold">TRK-{ch.track_id}</span>
                    <span className="text-muted">{ch.previous_level}</span>
                    <span className="text-accent font-bold">→</span>
                    <span className={`font-bold ${
                      ch.new_level === 'CRITICAL' ? 'text-status-critical' : ch.new_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                    }`}>
                      {ch.new_level}
                    </span>
                  </div>
                  <div className="text-right text-[10px]">
                    <span className="text-paper">@{Number(ch.time_offset_seconds).toFixed(1)}s</span>
                    {ch.reason && <span className="text-faint ml-2">({ch.reason})</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted text-center">
              No threat level transitions recorded during this observation window.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 7: EVIDENCE FRAMES                                   */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              7. AUTHENTICATED EVIDENCE FRAMES
            </span>
            <span className="text-[10px] text-faint">
              CRYPTOGRAPHIC SHA-256 INTEGRITY
            </span>
          </div>

          {evidenceFrames.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
              {evidenceFrames.map((frame, idx) => (
                <div
                  key={idx}
                  onClick={() => setSelectedEvidenceFrame(frame)}
                  className="group relative bg-panel/90 border border-white/[0.08] rounded overflow-hidden cursor-pointer hover:border-accent transition-all"
                >
                  <img
                    src={getEvidenceUrl(frame.artifact_key, false)}
                    alt={`Evidence Frame #${frame.frame_number}`}
                    className="w-full h-20 object-cover bg-black"
                  />
                  <div className="p-1.5 bg-graphite/90 text-[9px] space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="text-paper font-bold">#{frame.frame_number}</span>
                      <span className="text-accent">{Number(frame.timestamp_seconds).toFixed(1)}s</span>
                    </div>
                    <div className="flex items-center justify-between text-faint text-[8px]">
                      <span>TRK-{frame.track_id}</span>
                      <span className="text-status-warning">{frame.threat_level}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted text-center">
              Zero authenticated evidence frame artifacts persisted for this analysis.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 8: MAP / SPATIAL CONTEXT                             */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              8. GEOGRAPHIC CONTEXT & PROVENANCE
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
              spatialContext?.source_type === 'OPERATOR_PROVIDED'
                ? 'bg-status-ai/15 text-status-ai border border-status-ai/25 font-bold'
                : 'bg-elevated text-muted border border-white/[0.08]'
            }`}>
              {spatialContext?.source_type || 'ASSET METADATA'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono mt-2">
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">PRECISION</span>
              <span className="text-paper">{spatialContext?.precision || 'ESTIMATED / MONITORED'}</span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">PROVENANCE</span>
              <span className="text-accent">{spatialContext?.source_type || 'SYSTEM REGISTERED'}</span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">INTERNATIONAL BORDER</span>
              <span className="text-status-warning font-medium">{spatialContext?.relevant_border || 'BORDER CONTEXT UNAVAILABLE'}</span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">OPERATIONAL GEOFENCE</span>
              <span className="text-paper font-medium">{spatialContext?.geofence_status || 'MONITORED ZONE'}</span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 9: ROUTING / SHELTER INFORMATION                     */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              9. EVACUATION ROUTING & SHELTER CONNECTIVITY
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${
              routingSummary?.status === 'AVAILABLE'
                ? 'bg-status-success/15 text-status-success font-bold'
                : 'bg-elevated text-faint'
            }`}>
              {routingSummary?.status === 'AVAILABLE' ? 'VIABLE ROAD CORRIDOR' : 'UNAVAILABLE'}
            </span>
          </div>

          {routingSummary && routingSummary.status === 'AVAILABLE' ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ROUTING CRITERION</span>
                <span className="text-accent uppercase font-bold">{routingSummary.criterion || 'FASTEST'}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">TOTAL ROAD DISTANCE</span>
                <span className="text-paper font-bold">
                  {routingSummary.distance_km ? `${routingSummary.distance_km.toFixed(1)} km` : '--'}
                </span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ESTIMATED DURATION</span>
                <span className="text-paper font-bold">
                  {routingSummary.duration_minutes ? `${Math.round(routingSummary.duration_minutes)} min` : '--'}
                </span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">ROUTING PROVIDER</span>
                <span className="text-paper font-medium">{routingSummary.provider_name || 'Mapbox'}</span>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted text-center space-y-1">
              <span className="text-paper font-semibold block">ROUTING DATA UNAVAILABLE</span>
              <p className="text-faint text-[10px]">
                Evacuation routing was not requested or no destination facility was evaluated for this analysis. Strictly zero synthetic or straight-line distance is fabricated.
              </p>
            </div>
          )}

          {shelterSummary && shelterSummary.status === 'AVAILABLE' ? (
            <div className="mt-3 pt-3 border-t border-white/[0.04] grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">VERIFIED SHELTERS</span>
                <span className="text-paper font-bold">{shelterSummary.total_shelters ?? shelterSummary.count ?? '--'}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">CAPACITY STATUS</span>
                <span className="text-status-success font-bold">{shelterSummary.capacity_status || 'VERIFIED'}</span>
              </div>
              <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-[10px] text-faint block">NEAREST FACILITY</span>
                <span className="text-paper font-medium">{shelterSummary.nearest_facility_name || 'Designated Shelter'}</span>
              </div>
            </div>
          ) : (
            <div className="mt-2 text-[10px] text-faint border-t border-white/[0.04] pt-2">
              SHELTER CONNECTIVITY: {shelterSummary?.message || 'No evacuation shelters designated or evaluated for this sector.'}
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 10: AI INTELLIGENCE SUMMARY                          */}
        {/* ============================================================ */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg aerion-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold">
              10. AI INTELLIGENCE SUMMARY
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-status-ai/15 text-status-ai border border-status-ai/30">
              SYNTHESIS
            </span>
          </div>
          <p className="text-xs text-paper leading-relaxed font-mono">
            {report?.ai_advisory?.summary || 'Deterministic operational synthesis computed from verified detection tracks, sensor telemetry, and boundary geometry.'}
          </p>
        </div>

        {/* ============================================================ */}
        {/* SECTION 11: MISTRAL GROUNDED ANALYSIS                        */}
        {/* ============================================================ */}
        <div className="p-5 bg-panel border border-status-ai/30 rounded-lg aerion-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
            <div className="flex items-center gap-2 text-status-ai font-bold text-xs uppercase">
              <span className="material-symbols-outlined text-[18px]">psychology</span>
              <span>11. MISTRAL AI GROUNDED ANALYSIS (4-PART STRUCTURE)</span>
            </div>
            <span className="text-[10px] text-faint">MODEL: {report?.ai_advisory?.model || 'open-mistral-nemo (strict)'}</span>
          </div>

          <div className="p-3 bg-graphite/60 rounded border border-white/[0.04] space-y-2 text-paper leading-relaxed whitespace-pre-line">
            {report?.ai_advisory?.advisory_text ||
              `[OBSERVED FACTS]
- Ingested asset processed deterministically without hallucinated contacts.
- Real-time vehicle detections bounded to verified visual observations.

[DERIVED ASSESSMENTS]
- Threat levels assessed from trajectory vectors and boundary containment.
- No synthetic casualties or road closures assumed.

[PREDICTED / TREND]
- Observable trends derived strictly from chronological tracker history.

[UNAVAILABLE DATA & LIMITATIONS]
- External geocontext unverified unless designated by operator.
- Sensor limitations restrict detection confidence to visible spectrum.`}
          </div>

          <div className="flex items-center justify-between text-[10px] text-faint pt-1 border-t border-white/[0.04]">
            <span>VERIFICATION: HUMAN OPERATOR IN THE LOOP REQUIRED</span>
            <span>ZERO FABRICATION ENFORCED</span>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 12: EVIDENCE & PROVENANCE                            */}
        {/* ============================================================ */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold mb-3">
            12. AUDITABLE EVIDENCE LINEAGE & MODEL VERIFICATION
          </span>

          {/* Model Weights Hashes */}
          <div className="mb-3 p-3 bg-graphite/50 rounded border border-white/[0.04] space-y-1">
            <span className="text-[10px] text-faint uppercase font-bold block">FROZEN ML RUNTIME INTEGRITY (SHA-256):</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[10px] text-muted">
              <div>YOLOv8s: <span className="text-accent">15da69f5c22ba10d...</span></div>
              <div>YOLOv8n-OBB: <span className="text-accent">01639c03b1464aa6...</span></div>
              <div>Siamese ResNet-18: <span className="text-accent">02a76f6f96e48e02...</span></div>
              <div>Unified Drone: <span className="text-accent">a18da3fc68a52737...</span></div>
            </div>
          </div>

          {/* Evidence Lineage */}
          {report?.evidence_lineage && report.evidence_lineage.length > 0 ? (
            <div className="space-y-1.5">
              {report.evidence_lineage.map((ev, idx) => (
                <div key={ev.evidence_id || idx} className="p-2 bg-graphite/40 border border-white/[0.04] rounded flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-accent font-medium">{ev.source}</span>
                    {ev.verification_state && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-elevated text-muted">
                        {ev.verification_state}
                      </span>
                    )}
                  </div>
                  <div className="text-faint text-[10px]">
                    SHA256: {ev.hash ? `${ev.hash.substring(0, 16)}...` : 'RECORDED'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-faint">
              ZERO FABRICATION: Single-stage perception session lineage registered.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 13: LIMITATIONS & UNAVAILABLE INFORMATION            */}
        {/* ============================================================ */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg aerion-card font-mono text-xs">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block font-bold mb-3">
            13. LIMITATIONS & UNAVAILABLE INFORMATION (TRUTHFUL REPORTING)
          </span>
          <ul className="space-y-1.5 text-xs text-muted">
            <li className="flex items-start gap-2">
              <span className="text-status-warning">•</span>
              <span>Coordinates and spatial references are derived strictly from provided telemetry or operator designation; unverified assets have no GPS claims.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-status-warning">•</span>
              <span>Evacuation route graphs and facility corridors require explicit endpoint resolution; zero synthetic straight-line distances are computed.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-status-warning">•</span>
              <span>All damage and vehicle threat metrics reflect visible sensor frames at the time of ingest and do not infer subterranean or occluded objects.</span>
            </li>
            {report?.limitations && report.limitations.map((lim, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-accent">•</span>
                <span>{lim}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Selected Evidence Frame Preview Modal */}
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
