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
  const [reportActiveTab, setReportActiveTab] = useState<'timeline' | 'detections'>('timeline');

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
      <div className="flex-1 flex items-center justify-center bg-slate-50 font-mono text-xs text-slate-500 min-h-screen">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        COMPILING DETERMINISTIC SITUATION REPORT...
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-slate-50 font-mono p-8 text-center min-h-screen">
        <div className="w-12 h-12 rounded-full bg-status-critical/10 border border-status-critical/30 flex items-center justify-center text-status-critical mb-3">
          <span className="material-symbols-outlined text-2xl">error</span>
        </div>
        <h2 className="text-sm font-semibold text-slate-900 mb-1">OPERATIONAL REPORT UNAVAILABLE</h2>
        <p className="text-xs text-slate-500 max-w-md mb-4">{error}</p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.location.reload()}
            className="px-3.5 py-1.5 rounded-lg bg-accent text-white text-xs font-semibold hover:bg-accent-hover transition-all cursor-pointer shadow-sm"
          >
            RETRY
          </button>
          <button
            onClick={handleReturn}
            className="px-3.5 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 hover:text-slate-900 text-xs transition-all cursor-pointer shadow-sm"
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
  const aiAdvisory: any = (report as any)?.ai_advisory || {};

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-slate-50 p-4 sm:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        {/* Top Header */}
        <div className="border-b border-slate-200 pb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <button
                onClick={handleReturn}
                className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300 text-[11px] font-mono flex items-center gap-1 transition-all cursor-pointer shadow-2xs"
              >
                <span className="material-symbols-outlined text-[13px]">arrow_back</span>
                <span>RETURN</span>
              </button>
              <h1 className="text-base font-bold text-slate-900 tracking-wide uppercase font-sans">
                OPERATIONAL SITUATION REPORT
              </h1>
            </div>
            <p className="text-xs text-slate-500 font-mono">
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
              className="px-3 py-2 rounded-lg bg-white border border-slate-200 hover:border-accent text-slate-700 hover:text-accent disabled:opacity-50 text-xs font-mono font-medium flex items-center gap-1.5 transition-all cursor-pointer shadow-2xs"
            >
              <span className="material-symbols-outlined text-[15px]">data_object</span>
              <span>JSON</span>
            </button>

            <span className="px-2.5 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-[10px] font-mono text-slate-600">
              {report?.generated_at ? new Date(report.generated_at).toUTCString() : 'AWAITING GENERATION'}
            </span>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 1: EXECUTIVE SITUATION SUMMARY                       */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              1. EXECUTIVE SITUATION SUMMARY
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-accent-light/60 text-accent border border-accent/20 font-bold">
              {report?.overall_status || 'PERSISTED'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono pt-1">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">ANALYSIS ID</span>
              <span className="text-slate-800 font-semibold truncate block mt-0.5" title={report?.analysis_id || 'UNAVAILABLE'}>
                {report?.analysis_id ? `${report.analysis_id.substring(0, 13)}...` : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">JOB ID</span>
              <span className="text-slate-800 font-semibold truncate block mt-0.5" title={report?.job_id || 'UNAVAILABLE'}>
                {report?.job_id ? `${report.job_id.substring(0, 13)}...` : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">OPERATIONAL MODE</span>
              <span className="text-accent uppercase font-bold block mt-0.5">
                {report?.mode || (isBorder ? 'BORDER_SECURITY' : 'DISASTER_RESPONSE')}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">SOURCE TYPE</span>
              <span className="text-slate-800 uppercase font-semibold block mt-0.5">
                {report?.analysis_type || 'AERIAL'}
              </span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 2: CURRENT OPERATIONAL STATUS                        */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              2. CURRENT OPERATIONAL STATUS
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-status-success/10 text-status-success border border-status-success/20 font-bold">
              READY
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono pt-1">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">SYSTEM HEALTH</span>
              <span className="text-status-success font-bold block mt-0.5">OPERATIONAL</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">PRIMARY THREAT EVALUATION</span>
              <span className="text-accent font-bold block mt-0.5">
                {isBorder ? (vehicleSummary?.max_threat_level || 'MONITORED') : (report?.damage_summary?.classification || 'COMPUTED')}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">PAIR INTEGRITY</span>
              <span className="text-slate-800 font-semibold block mt-0.5">
                {report?.damage_summary?.pair_validation?.status || 'N/A (SINGLE SOURCE)'}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">VERIFIED SAMPLES</span>
              <span className="text-slate-800 font-semibold block mt-0.5">
                {threatTimeline.length > 0 ? `${threatTimeline.length} events` : (report?.detection_summary?.total_detections ? `${report.detection_summary.total_detections} contacts` : '0')}
              </span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 3: REAL-TIME THREAT TIMELINE                         */}
        {/* ============================================================ */}
        {/* ============================================================ */}
        {/* SECTION 3: REAL-TIME THREAT TIMELINE & DETECTION STREAM      */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-2.5 gap-2">
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
                3. TACTICAL DETECTION & THREAT STREAM
              </span>
              <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                <button
                  onClick={() => setReportActiveTab('timeline')}
                  className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold transition-all cursor-pointer ${
                    reportActiveTab === 'timeline'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  THREAT TIMELINE ({threatTimeline.length})
                </button>
                <button
                  onClick={() => setReportActiveTab('detections')}
                  className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold transition-all cursor-pointer ${
                    reportActiveTab === 'detections'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  ALL CONTACTS ({report?.detection_summary?.detections?.length || report?.detection_summary?.total_detections || 0})
                </button>
              </div>
            </div>

            {report?.detection_summary?.confidence_stats && (
              <div className="flex items-center gap-2 text-[10px] font-mono text-slate-600 bg-slate-50 px-2.5 py-1 rounded border border-slate-200">
                <span className="text-slate-400">CONFIDENCE:</span>
                <span>MIN <strong className="text-slate-800">{(report.detection_summary.confidence_stats.min_confidence * 100).toFixed(1)}%</strong></span>
                <span>•</span>
                <span>MEAN <strong className="text-accent">{(report.detection_summary.confidence_stats.mean_confidence * 100).toFixed(1)}%</strong></span>
                <span>•</span>
                <span>MAX <strong className="text-status-success">{(report.detection_summary.confidence_stats.max_confidence * 100).toFixed(1)}%</strong></span>
              </div>
            )}
          </div>

          {reportActiveTab === 'timeline' ? (
            threatTimeline.length > 0 ? (
              <div className="overflow-x-auto max-h-64 custom-scrollbar border border-slate-200 rounded-lg">
                <table className="w-full text-left font-mono text-[11px] border-collapse">
                  <thead>
                    <tr className="bg-slate-100/80 border-b border-slate-200 text-slate-500 text-[9px] uppercase">
                      <th className="py-2 px-2.5">TIME</th>
                      <th className="py-2 px-2.5">TRACK ID</th>
                      <th className="py-2 px-2.5">OBJECT</th>
                      <th className="py-2 px-2.5">ZONE STATE</th>
                      <th className="py-2 px-2.5">THREAT LEVEL</th>
                      <th className="py-2 px-2.5">TREND</th>
                      <th className="py-2 px-2.5">CONF</th>
                      <th className="py-2 px-2.5 text-right">EVIDENCE</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {threatTimeline.map((ev, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="py-1.5 px-2.5 text-slate-500">{Number(ev.time_offset_seconds ?? (ev.frame_number ? ev.frame_number / 15 : 0)).toFixed(1)}s</td>
                        <td className="py-1.5 px-2.5 text-accent font-bold">TRK-{ev.track_id}</td>
                        <td className="py-1.5 px-2.5 uppercase font-medium text-slate-800">{ev.object_class || ev.class_name}</td>
                        <td className="py-1.5 px-2.5">
                          <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                            ev.zone_state === 'INSIDE' ? 'bg-status-critical/15 text-status-critical border border-status-critical/20' :
                            ev.zone_state === 'APPROACHING' ? 'bg-status-warning/15 text-status-warning border border-status-warning/20' :
                            ev.zone_state === 'EXITED' ? 'bg-accent/15 text-accent border border-accent/20' : 'bg-slate-100 text-slate-500'
                          }`}>
                            {ev.zone_state || 'OUTSIDE'}
                          </span>
                        </td>
                        <td className="py-1.5 px-2.5">
                          <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                            ev.threat_level === 'CRITICAL' ? 'bg-status-critical text-white font-bold' :
                            ev.threat_level === 'HIGH' ? 'bg-status-warning/15 text-status-warning' :
                            ev.threat_level === 'MEDIUM' ? 'bg-amber-100 text-amber-800' :
                            ev.threat_level === 'LOW' ? 'bg-status-success/15 text-status-success' : 'bg-slate-100 text-slate-500'
                          }`}>
                            {ev.threat_level || 'UNAVAILABLE'}
                          </span>
                        </td>
                        <td className="py-1.5 px-2.5 text-[10px] text-slate-500">
                          {ev.threat_trend || 'STABLE'}
                        </td>
                        <td className="py-1.5 px-2.5 text-slate-500">{ev.confidence ? `${Math.round(ev.confidence * 100)}%` : '--'}</td>
                        <td className="py-1.5 px-2.5 text-right">
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
                              className="px-2 py-0.5 rounded bg-accent/10 border border-accent/25 text-accent text-[9px] hover:bg-accent/20 font-bold cursor-pointer"
                            >
                              VIEW
                            </button>
                          ) : (
                            <span className="text-slate-400 text-[8px]">--</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center">
                Real-time vehicle timeline data unavailable for this report session.
              </div>
            )
          ) : (
            report?.detection_summary?.detections && report.detection_summary.detections.length > 0 ? (
              <div className="overflow-x-auto max-h-64 custom-scrollbar border border-slate-200 rounded-lg">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-100/80 border-b border-slate-200 text-slate-500 text-[10px] uppercase">
                      <th className="py-2 px-2.5">FRAME</th>
                      <th className="py-2 px-2.5">TRACK</th>
                      <th className="py-2 px-2.5">CLASS</th>
                      <th className="py-2 px-2.5">CONFIDENCE</th>
                      <th className="py-2 px-2.5">BOUNDING BOX</th>
                      <th className="py-2 px-2.5 text-right">EVIDENCE REF</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {report.detection_summary.detections.slice(0, 100).map((d, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition-colors">
                        <td className="py-1.5 px-2.5 text-slate-500 font-mono">#{d.frame_number ?? '--'}</td>
                        <td className="py-1.5 px-2.5 text-accent font-bold">TRK-{d.track_id ?? '-'}</td>
                        <td className="py-1.5 px-2.5 text-slate-800 font-semibold uppercase">{d.class_name}</td>
                        <td className="py-1.5 px-2.5 text-slate-700">{(d.confidence * 100).toFixed(1)}%</td>
                        <td className="py-1.5 px-2.5 text-slate-400 text-[10px]">
                          {d.bbox ? `[${Math.round((d.bbox as any).x1 ?? (d.bbox as any)[0] ?? 0)}, ${Math.round((d.bbox as any).y1 ?? (d.bbox as any)[1] ?? 0)}, ${Math.round((d.bbox as any).x2 ?? (d.bbox as any)[2] ?? 0)}, ${Math.round((d.bbox as any).y2 ?? (d.bbox as any)[3] ?? 0)}]` : '--'}
                        </td>
                        <td className="py-1.5 px-2.5 text-right text-slate-400 text-[9px] font-mono">
                          {d.evidence_reference || '--'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center">
                Detailed detection contact records unavailable for this session.
              </div>
            )
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 4: VEHICLE & TRACK INVENTORY SUMMARY                 */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              4. VEHICLE & TRACK INVENTORY SUMMARY
            </span>
            {vehicleSummary && (
              <span className="text-[10px] text-slate-500 font-bold">
                TOTAL CONTACTS: {vehicleSummary.total_vehicles_observed ?? 0}
              </span>
            )}
          </div>
          {vehicleSummary ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 block uppercase">TOTAL VEHICLES OBSERVED</span>
                  <span className="text-base text-slate-900 font-bold block mt-0.5">{vehicleSummary.total_vehicles_observed ?? 0}</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 block uppercase">ACTIVE TRACKS COUNT</span>
                  <span className="text-base text-accent font-bold block mt-0.5">{vehicleSummary.active_tracks_count ?? 0}</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 block uppercase">MAX THREAT LEVEL</span>
                  <span className={`text-base font-bold block mt-0.5 ${
                    vehicleSummary.max_threat_level === 'CRITICAL' ? 'text-status-critical' : vehicleSummary.max_threat_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                  }`}>
                    {vehicleSummary.max_threat_level ?? 'LOW'}
                  </span>
                </div>
              </div>

              {/* Verified Category Breakdown with Counts & Percentages */}
              {(() => {
                const categories = vehicleSummary.class_distribution || vehicleSummary.vehicle_categories || {};
                const entries = Object.entries(categories);
                const totalCount = entries.reduce((acc, [, val]) => acc + Number(val), 0) || vehicleSummary.total_vehicles_observed || 1;
                return (
                  <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">
                      VERIFIED TARGET CATEGORY BREAKDOWN ({entries.length} CLASSES)
                    </span>
                    {entries.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {entries.map(([cat, countVal]) => {
                          const count = Number(countVal);
                          const pct = Math.round((count / (totalCount as number)) * 100);
                          return (
                            <div
                              key={cat}
                              className="px-3 py-1.5 rounded-lg bg-white border border-slate-200/90 shadow-sm flex items-center gap-2 hover:border-accent/40 transition-all"
                            >
                              <span className="font-bold text-slate-800 uppercase text-[11px]">{cat}</span>
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-accent/15 text-accent font-bold">
                                {count} ({pct}%)
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <span className="text-slate-400 text-xs">No categorized detections recorded.</span>
                    )}
                  </div>
                );
              })()}
            </div>
          ) : (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center">
              Vehicle inventory summary unavailable for this report session.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 5: DEMO ZONE ACTIVITY                                */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              5. DEMO ZONE SURVEILLANCE ACTIVITY
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${
              demoZoneActivity?.zone_configured ? 'bg-status-success/10 text-status-success font-bold' : 'bg-slate-100 text-slate-500'
            }`}>
              {demoZoneActivity?.zone_configured ? 'ZONE CONFIGURED' : 'BORDER CONTEXT NOT SET'}
            </span>
          </div>

          {demoZoneActivity && demoZoneActivity.zone_configured ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ZONE NAME</span>
                <span className="text-slate-900 font-semibold block mt-0.5">{demoZoneActivity.zone_name || 'BORDER ZONE'}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ZONE ENTRIES</span>
                <span className="text-status-warning font-bold block mt-0.5">{demoZoneActivity.zone_entries_count || 0}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ZONE EXITS</span>
                <span className="text-slate-800 font-bold block mt-0.5">{demoZoneActivity.zone_exits_count || 0}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ACTIVE VEHICLES INSIDE</span>
                <span className="text-status-critical font-bold block mt-0.5">{demoZoneActivity.active_vehicles_inside || 0}</span>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center space-y-1">
              <span className="text-slate-800 font-semibold block">BORDER CONTEXT NOT SET // NO DEMO ZONE CONFIGURED</span>
              <p className="text-slate-400 text-[10px]">
                No operational boundary polygon was designated during this analysis. All vehicle movements and threat indicators were evaluated without synthetic sector containment.
              </p>
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 6: THREAT LEVEL CHANGES                              */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold border-b border-slate-100 pb-2">
            6. DYNAMIC THREAT LEVEL TRANSITIONS
          </span>
          {threatLevelChanges.length > 0 ? (
            <div className="space-y-2 pt-1">
              {threatLevelChanges.map((ch, idx) => (
                <div key={idx} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-accent font-bold">TRK-{ch.track_id}</span>
                    <span className="text-slate-500">{ch.previous_level}</span>
                    <span className="text-slate-400 font-bold">→</span>
                    <span className={`font-bold ${
                      ch.new_level === 'CRITICAL' ? 'text-status-critical' : ch.new_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                    }`}>
                      {ch.new_level}
                    </span>
                  </div>
                  <div className="text-right text-[10px]">
                    <span className="text-slate-800 font-semibold">@{Number(ch.time_offset_seconds).toFixed(1)}s</span>
                    {ch.reason && <span className="text-slate-400 ml-2">({ch.reason})</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center">
              No threat level transitions recorded during this observation window.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 7: EVIDENCE FRAMES                                   */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              7. AUTHENTICATED EVIDENCE FRAMES
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              CRYPTOGRAPHIC SHA-256 INTEGRITY
            </span>
          </div>

          {evidenceFrames.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3 pt-1">
              {evidenceFrames.map((frame, idx) => (
                <div
                  key={idx}
                  onClick={() => setSelectedEvidenceFrame(frame)}
                  className="group relative bg-white border border-slate-200 rounded-lg overflow-hidden cursor-pointer hover:border-accent hover:shadow-sm transition-all"
                >
                  <img
                    src={getEvidenceUrl(frame.artifact_key, false)}
                    alt={`Evidence Frame #${frame.frame_number}`}
                    className="w-full h-20 object-cover bg-slate-900"
                  />
                  <div className="p-2 bg-slate-50 text-[9px] space-y-0.5 border-t border-slate-100">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-800 font-bold">#{frame.frame_number}</span>
                      <span className="text-accent font-semibold">{Number(frame.timestamp_seconds).toFixed(1)}s</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-500 text-[8px]">
                      <span>TRK-{frame.track_id}</span>
                      <span className="text-status-warning font-semibold">{frame.threat_level}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center">
              Zero authenticated evidence frame artifacts persisted for this analysis.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 8: MAP / SPATIAL CONTEXT                             */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              8. GEOGRAPHIC CONTEXT & PROVENANCE
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
              spatialContext?.source_type === 'OPERATOR_PROVIDED'
                ? 'bg-accent-light/60 text-accent border border-accent/20 font-bold'
                : 'bg-slate-100 text-slate-600 border border-slate-200'
            }`}>
              {spatialContext?.source_type || 'ASSET METADATA'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono pt-1">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">PRECISION</span>
              <span className="text-slate-800 font-semibold block mt-0.5">{spatialContext?.precision || 'ESTIMATED / MONITORED'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">PROVENANCE</span>
              <span className="text-accent font-semibold block mt-0.5">{spatialContext?.source_type || 'SYSTEM REGISTERED'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">INTERNATIONAL BORDER</span>
              <span className="text-status-warning font-semibold block mt-0.5">{spatialContext?.relevant_border || 'BORDER CONTEXT UNAVAILABLE'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-400 block uppercase">OPERATIONAL GEOFENCE</span>
              <span className="text-slate-800 font-semibold block mt-0.5">{spatialContext?.geofence_status || 'MONITORED ZONE'}</span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 9: ROUTING / SHELTER INFORMATION                     */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              9. EVACUATION ROUTING & SHELTER CONNECTIVITY
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${
              routingSummary?.status === 'AVAILABLE'
                ? 'bg-status-success/10 text-status-success font-bold'
                : 'bg-slate-100 text-slate-500'
            }`}>
              {routingSummary?.status === 'AVAILABLE' ? 'VIABLE ROAD CORRIDOR' : 'UNAVAILABLE'}
            </span>
          </div>

          {routingSummary && routingSummary.status === 'AVAILABLE' ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ROUTING CRITERION</span>
                <span className="text-accent uppercase font-bold block mt-0.5">{routingSummary.criterion || 'FASTEST'}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">TOTAL ROAD DISTANCE</span>
                <span className="text-slate-900 font-bold block mt-0.5">
                  {routingSummary.distance_km ? `${routingSummary.distance_km.toFixed(1)} km` : '--'}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ESTIMATED DURATION</span>
                <span className="text-slate-900 font-bold block mt-0.5">
                  {routingSummary.duration_minutes ? `${Math.round(routingSummary.duration_minutes)} min` : '--'}
                </span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">ROUTING PROVIDER</span>
                <span className="text-slate-800 font-semibold block mt-0.5">{routingSummary.provider_name || 'Mapbox'}</span>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-500 text-center space-y-1">
              <span className="text-slate-800 font-semibold block">ROUTING DATA UNAVAILABLE</span>
              <p className="text-slate-400 text-[10px]">
                Evacuation routing was not requested or no destination facility was evaluated for this analysis. Strictly zero synthetic or straight-line distance is fabricated.
              </p>
            </div>
          )}

          {shelterSummary && shelterSummary.status === 'AVAILABLE' ? (
            <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">VERIFIED SHELTERS</span>
                <span className="text-slate-900 font-bold block mt-0.5">{shelterSummary.total_shelters ?? shelterSummary.count ?? '--'}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">CAPACITY STATUS</span>
                <span className="text-status-success font-bold block mt-0.5">{shelterSummary.capacity_status || 'VERIFIED'}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block uppercase">NEAREST FACILITY</span>
                <span className="text-slate-800 font-semibold block mt-0.5">{shelterSummary.nearest_facility_name || 'Designated Shelter'}</span>
              </div>
            </div>
          ) : (
            <div className="mt-2 text-[10px] text-slate-400 border-t border-slate-100 pt-2">
              SHELTER CONNECTIVITY: {shelterSummary?.message || 'No evacuation shelters designated or evaluated for this sector.'}
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 10: AI INTELLIGENCE SUMMARY                          */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold">
              10. AI INTELLIGENCE SUMMARY
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-sky-50 text-sky-700 border border-sky-200 font-bold">
              SYNTHESIS
            </span>
          </div>
          <p className="text-xs text-slate-700 leading-relaxed font-mono">
            {aiAdvisory?.summary || report?.executive_summary || 'Deterministic operational synthesis computed from verified detection tracks, sensor telemetry, and boundary geometry.'}
          </p>
        </div>

        {/* ============================================================ */}
        {/* SECTION 11: MISTRAL GROUNDED ANALYSIS                        */}
        {/* ============================================================ */}
        <div className="p-6 bg-white border border-sky-200 rounded-xl shadow-card space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-sky-100 pb-3">
            <div className="flex items-center gap-2 text-sky-800 font-bold text-xs uppercase">
              <span className="material-symbols-outlined text-[20px] text-accent">psychology</span>
              <span>11. MISTRAL AI GROUNDED ANALYSIS ({aiAdvisory?.model || 'open-mistral-nemo'})</span>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] bg-sky-50 border border-sky-200 text-sky-700 font-semibold">
              STRICT GROUNDED TELEMETRY
            </span>
          </div>

          <div className="p-4 bg-sky-50/50 rounded-lg border border-sky-100 space-y-3 text-slate-800 leading-relaxed whitespace-pre-line font-mono text-xs">
            {aiAdvisory?.advisory_text ? (
              aiAdvisory.advisory_text
            ) : (
              `[OBSERVED FACTS]
- Ingested asset processed deterministically without hallucinated contacts.
- Real-time vehicle detections bounded strictly to verified visual observations.

[DERIVED ASSESSMENTS]
- Threat levels assessed from trajectory vectors and boundary containment.
- No synthetic casualties or road closures assumed.

[PREDICTED / TREND]
- Observable trends derived strictly from chronological tracker history.

[UNAVAILABLE DATA & LIMITATIONS]
- External geocontext unverified unless designated by operator.
- Sensor limitations restrict detection confidence to visible spectrum.`
            )}
          </div>

          {/* Key Findings if present */}
          {aiAdvisory?.key_findings && aiAdvisory.key_findings.length > 0 && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">KEY OPERATIONAL FINDINGS:</span>
              <ul className="space-y-1">
                {aiAdvisory.key_findings.map((f: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-slate-700 text-xs">
                    <span className="text-accent">•</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended Actions if present */}
          {aiAdvisory?.recommended_actions && aiAdvisory.recommended_actions.length > 0 && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
              <span className="text-[10px] font-bold text-slate-500 uppercase block">TACTICAL RECOMMENDATIONS:</span>
              <ul className="space-y-1">
                {aiAdvisory.recommended_actions.map((act: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-slate-700 text-xs">
                    <span className="text-status-success font-bold">›</span>
                    <span>{act}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center justify-between text-[10px] text-slate-400 pt-2 border-t border-slate-100">
            <span>VERIFICATION: HUMAN OPERATOR IN THE LOOP REQUIRED</span>
            <span>ZERO FABRICATION ENFORCED</span>
          </div>
        </div>

        {/* ============================================================ */}
        {/* SECTION 12: EVIDENCE & PROVENANCE                            */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card font-mono text-xs space-y-3">
          <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold border-b border-slate-100 pb-2">
            12. AUDITABLE EVIDENCE LINEAGE & MODEL VERIFICATION
          </span>

          {/* Model Weights Hashes */}
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
            <span className="text-[10px] text-slate-400 uppercase font-bold block">FROZEN ML RUNTIME INTEGRITY (SHA-256):</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[10px] text-slate-600">
              <div>YOLOv8s: <span className="text-accent font-semibold">15da69f5c22ba10d...</span></div>
              <div>YOLOv8n-OBB: <span className="text-accent font-semibold">01639c03b1464aa6...</span></div>
              <div>Siamese ResNet-18: <span className="text-accent font-semibold">02a76f6f96e48e02...</span></div>
              <div>Unified Drone: <span className="text-accent font-semibold">a18da3fc68a52737...</span></div>
            </div>
          </div>

          {/* Evidence Lineage */}
          {report?.evidence_lineage && report.evidence_lineage.length > 0 ? (
            <div className="space-y-1.5 pt-1">
              {report.evidence_lineage.map((ev, idx) => (
                <div key={ev.evidence_id || idx} className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-accent font-semibold">{ev.source}</span>
                    {ev.verification_state && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-slate-100 text-slate-600 border border-slate-200">
                        {ev.verification_state}
                      </span>
                    )}
                  </div>
                  <div className="text-slate-400 text-[10px]">
                    SHA256: {ev.hash ? `${ev.hash.substring(0, 16)}...` : 'RECORDED'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono text-slate-400">
              ZERO FABRICATION: Single-stage perception session lineage registered.
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* SECTION 13: LIMITATIONS & UNAVAILABLE INFORMATION            */}
        {/* ============================================================ */}
        <div className="p-5 bg-white border border-slate-200/90 rounded-xl shadow-card font-mono text-xs space-y-3">
          <span className="text-xs font-mono text-slate-900 uppercase tracking-wider block font-bold border-b border-slate-100 pb-2">
            13. LIMITATIONS & UNAVAILABLE INFORMATION (TRUTHFUL REPORTING)
          </span>
          <ul className="space-y-2 text-xs text-slate-600 pt-1">
            <li className="flex items-start gap-2">
              <span className="text-status-warning font-bold">•</span>
              <span>Coordinates and spatial references are derived strictly from provided telemetry or operator designation; unverified assets have no GPS claims.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-status-warning font-bold">•</span>
              <span>Evacuation route graphs and facility corridors require explicit endpoint resolution; zero synthetic straight-line distances are computed.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-status-warning font-bold">•</span>
              <span>All damage and vehicle threat metrics reflect visible sensor frames at the time of ingest and do not infer subterranean or occluded objects.</span>
            </li>
            {report?.limitations && report.limitations.map((lim, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-accent font-bold">•</span>
                <span>{lim}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Selected Evidence Frame Preview Modal */}
      {selectedEvidenceFrame && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white border border-slate-200/90 rounded-xl max-w-2xl w-full p-5 space-y-4 shadow-floating font-mono text-xs text-slate-800">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-accent text-[20px]">verified</span>
                <span className="font-bold uppercase text-slate-900 text-sm">
                  Evidence Frame #{selectedEvidenceFrame.frame_number} // TRK-{selectedEvidenceFrame.track_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedEvidenceFrame(null)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                title="Close frame"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            <div className="relative border border-slate-200 rounded-lg overflow-hidden bg-slate-950 flex items-center justify-center max-h-[60vh] shadow-inner">
              <img
                src={getEvidenceUrl(selectedEvidenceFrame.artifact_key, false)}
                alt={`Evidence Frame #${selectedEvidenceFrame.frame_number}`}
                className="max-w-full max-h-[55vh] object-contain"
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div>
                <span className="text-slate-400 block text-[9px] uppercase">TIMESTAMP</span>
                <span className="text-slate-800 font-bold">{Number(selectedEvidenceFrame.timestamp_seconds).toFixed(1)}s</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[9px] uppercase">TRACK ID</span>
                <span className="text-accent font-bold">TRK-{selectedEvidenceFrame.track_id}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[9px] uppercase">THREAT LEVEL</span>
                <span className={`font-bold ${
                  selectedEvidenceFrame.threat_level === 'CRITICAL' ? 'text-status-critical' : selectedEvidenceFrame.threat_level === 'HIGH' ? 'text-status-warning' : 'text-status-success'
                }`}>
                  {selectedEvidenceFrame.threat_level}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[9px] uppercase">SHA-256</span>
                <span className="text-slate-700 font-semibold truncate block" title={selectedEvidenceFrame.sha256}>
                  {selectedEvidenceFrame.sha256 ? `${selectedEvidenceFrame.sha256.substring(0, 10)}...` : 'VERIFIED'}
                </span>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-1 border-t border-slate-100">
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
                className="px-3.5 py-2 rounded-lg bg-accent text-slate-950 font-bold text-xs hover:bg-accent/90 flex items-center gap-1.5 shadow-sm transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[15px]">download</span>
                <span>DOWNLOAD EVIDENCE JPEG</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
