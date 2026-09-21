import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { situationsApi } from '../api';
import { SituationReport } from '../types';
import { downloadAuthenticatedReport } from '../utils/download';

export const SituationReportPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [report, setReport] = useState<SituationReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  const analysisId = searchParams.get('analysis_id') || undefined;

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
        <div className="w-12 h-12 rounded-full bg-critical/10 border border-critical/30 flex items-center justify-center text-critical mb-3">
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

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-graphite p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        {/* Top Header */}
        <div className="border-b border-white/[0.06] pb-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <button
                onClick={handleReturn}
                className="px-2 py-0.5 rounded bg-elevated/70 border border-white/[0.08] text-muted hover:text-paper text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">arrow_back</span>
                <span>RETURN</span>
              </button>
              <h1 className="text-base font-semibold text-white tracking-wide uppercase font-sans">
                OPERATIONAL SITUATION REPORT
              </h1>
            </div>
            <p className="text-xs text-muted font-mono">
              STRUCTURED INTELLIGENCE & DETERMINISTIC SYNTHESIS
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => handleDownload('pdf')}
              disabled={isDownloading}
              className="px-3 py-1.5 rounded bg-accent text-graphite hover:bg-accent/90 disabled:opacity-50 text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-all cursor-pointer"
            >
              <span className="material-symbols-outlined text-[15px]">picture_as_pdf</span>
              <span>{isDownloading ? 'DOWNLOADING...' : 'DOWNLOAD REPORT (PDF)'}</span>
            </button>

            <button
              onClick={() => handleDownload('json')}
              disabled={isDownloading}
              className="px-3 py-1.5 rounded bg-elevated border border-white/[0.1] hover:border-accent text-paper hover:text-accent disabled:opacity-50 text-xs font-mono flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <span className="material-symbols-outlined text-[15px]">data_object</span>
              <span>JSON</span>
            </button>

            <span className="px-2.5 py-1 rounded bg-elevated border border-white/[0.08] text-[11px] font-mono text-muted">
              {report?.generated_at ? new Date(report.generated_at).toUTCString() : 'AWAITING GENERATION'}
            </span>
          </div>
        </div>

        {/* 1. Canonical Analysis Identity & Provenance */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block">
              1. PERSISTED ANALYSIS IDENTITY
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-accent/15 text-accent border border-accent/30">
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
              <span className="text-accent uppercase">
                {report?.mode || (isBorder ? 'BORDER' : 'DISASTER')}
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

        {/* 2. Geographic Context & Provenance */}
        <div className="p-4 bg-panel border border-white/[0.06] rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider block">
              2. GEOGRAPHIC CONTEXT & PROVENANCE
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
              (report as any)?.location_context?.source_type === 'OPERATOR_PROVIDED'
                ? 'bg-status-ai/15 text-status-ai border border-status-ai/25'
                : 'bg-elevated text-muted border border-white/[0.08]'
            }`}>
              {(report as any)?.location_context?.source_type || 'ASSET METADATA / SECTOR DELTA-9'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono mt-2">
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">PRECISION</span>
              <span className="text-paper">
                {(report as any)?.location_context?.precision || 'VERIFIED / MONITORED'}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">PROVENANCE</span>
              <span className="text-accent">
                {(report as any)?.location_context?.source_type || 'SYSTEM REGISTERED'}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">INTERNATIONAL BORDER</span>
              <span className="text-status-warning font-medium">
                {(report as any)?.location_context?.relevant_border || 'BORDER CONTEXT UNAVAILABLE'}
              </span>
            </div>
            <div className="p-2.5 bg-graphite/40 rounded border border-white/[0.04]">
              <span className="text-[10px] text-faint block">OPERATIONAL GEOFENCE</span>
              <span className="text-paper font-medium">
                {(report as any)?.location_context?.geofence_status || 'MONITORED ZONE'}
              </span>
            </div>
          </div>
        </div>

        {/* 3. Operational Mode Intelligence: Border Contact Table OR Disaster Damage Assessment */}
        {isBorder ? (
          <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-muted uppercase tracking-wider block">
                3. BORDER DETECTION CONTACT TABLE
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-elevated text-accent border border-white/[0.08]">
                TOTAL: {report?.detection_summary?.total_detections ?? 0}
              </span>
            </div>

            {report?.detection_summary?.detections && report.detection_summary.detections.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.08] text-faint text-[10px] uppercase">
                      <th className="py-2 px-2">ID</th>
                      <th className="py-2 px-2">Class</th>
                      <th className="py-2 px-2">Confidence</th>
                      <th className="py-2 px-2">Track</th>
                      <th className="py-2 px-2">Bounding Box</th>
                      <th className="py-2 px-2">Evidence Ref</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {report.detection_summary.detections.map((d) => (
                      <tr key={d.id} className="hover:bg-white/[0.02]">
                        <td className="py-2 px-2 text-paper">{d.id}</td>
                        <td className="py-2 px-2 text-accent font-medium">{d.class_name}</td>
                        <td className="py-2 px-2 text-paper">{(d.confidence * 100).toFixed(1)}%</td>
                        <td className="py-2 px-2 text-muted">{d.track_id ?? '-'}</td>
                        <td className="py-2 px-2 text-faint text-[11px]">
                          {d.bbox ? `[${Math.round(d.bbox.x1)}, ${Math.round(d.bbox.y1)}, ${Math.round(d.bbox.x2)}, ${Math.round(d.bbox.y2)}]` : 'PIXEL_REF'}
                        </td>
                        <td className="py-2 px-2 text-muted text-[11px]">{d.evidence_reference || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : report?.detection_summary?.status === 'UNAVAILABLE' ? (
              <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted">
                Detection data unavailable for this analysis.
              </div>
            ) : (
              <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted">
                0 detections returned by this analysis.
              </div>
            )}
          </div>
        ) : (
          <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-muted uppercase tracking-wider block">
                3. BI-TEMPORAL DAMAGE ASSESSMENT
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                (report?.damage_summary?.damage_percentage ?? 0) > 30
                  ? 'bg-status-critical/15 text-status-critical border border-status-critical/30'
                  : (report?.damage_summary?.damage_percentage ?? 0) > 10
                  ? 'bg-status-warning/15 text-status-warning border border-status-warning/30'
                  : 'bg-status-safe/15 text-status-safe border border-status-safe/30'
              }`}>
                {report?.damage_summary?.classification || 'COMPUTED'}
              </span>
            </div>

            {report?.damage_summary?.status === 'PAIR_VALIDATION_FAILED' || report?.damage_summary?.pair_validation?.is_compatible === false ? (
              <div className="p-4 bg-status-critical/10 border border-status-critical/40 rounded space-y-2 font-mono text-xs">
                <div className="flex items-center gap-2 text-status-critical font-bold">
                  <span className="material-symbols-outlined text-[18px]">gpp_bad</span>
                  <span>PAIR VALIDATION FAILED — INFERENCE HALTED</span>
                </div>
                <p className="text-paper text-[11px] leading-tight">
                  {report?.damage_summary?.pair_validation?.rejection_reason ||
                    'Bi-temporal imagery pair failed scene compatibility validation. Change detection was halted upstream to prevent false damage attribution.'}
                </p>
                <div className="p-2.5 bg-graphite/60 rounded border border-white/[0.06] text-[10px] space-y-1">
                  <div className="flex justify-between text-muted">
                    <span>PAIR STATUS:</span>
                    <span className="font-bold text-status-critical">{report?.damage_summary?.pair_validation?.status || 'PAIR_MISMATCH'}</span>
                  </div>
                  <div className="flex justify-between text-muted">
                    <span>EVALUATED PIXELS:</span>
                    <span className="text-paper">0</span>
                  </div>
                  <div className="flex justify-between text-muted">
                    <span>DAMAGE PERCENTAGE:</span>
                    <span className="text-paper">0.00%</span>
                  </div>
                  <div className="flex justify-between text-muted">
                    <span>SEVERITY CLASSIFICATION:</span>
                    <span className="text-muted">NOT GENERATED (INFERENCE HALTED)</span>
                  </div>
                </div>
              </div>
            ) : report?.damage_summary && report.damage_summary.status !== 'UNAVAILABLE' ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                <div className="p-3 bg-graphite/40 rounded border border-white/[0.04]">
                  <span className="text-[10px] text-faint block">DAMAGE RATIO</span>
                  <span className="text-base text-accent font-bold">
                    {report.damage_summary.damage_percentage.toFixed(2)}%
                  </span>
                  <span className="text-[10px] text-faint block mt-0.5">
                    Ratio: {report.damage_summary.damage_ratio.toFixed(6)}
                  </span>
                </div>
                <div className="p-3 bg-graphite/40 rounded border border-white/[0.04]">
                  <span className="text-[10px] text-faint block">DAMAGED PIXELS</span>
                  <span className="text-base text-paper font-bold">
                    {report.damage_summary.damage_pixels.toLocaleString()}
                  </span>
                  <span className="text-[10px] text-faint block mt-0.5">
                    of {report.damage_summary.total_pixels.toLocaleString()} total
                  </span>
                </div>
                <div className="p-3 bg-graphite/40 rounded border border-white/[0.04]">
                  <span className="text-[10px] text-faint block">PAIR VALIDATION</span>
                  <span className="text-paper font-medium">
                    {report.damage_summary.pair_validation?.status || 'VALIDATED'}
                  </span>
                  <span className="text-[10px] text-faint block mt-0.5">
                    Threshold: {report.damage_summary.threshold ?? 0.5}
                  </span>
                </div>
                <div className="p-3 bg-graphite/40 rounded border border-white/[0.04]">
                  <span className="text-[10px] text-faint block">DAMAGE ARTIFACT</span>
                  <span className="text-paper text-[11px] truncate block" title={report.damage_summary.mask_storage_key || 'GENERATED'}>
                    {report.damage_summary.mask_storage_key ? 'STORED MASK' : 'AVAILABLE'}
                  </span>
                  <span className="text-[10px] text-accent block mt-0.5">
                    Prob Mean: {(report.damage_summary.mean_probability ?? 0).toFixed(4)}
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-muted">
                Damage analysis unavailable for this analysis.
              </div>
            )}
          </div>
        )}

        {/* 4. Mistral AI Advisory Banner */}
        <div className="p-4 bg-panel border border-status-ai/30 rounded-lg">
          <div className="flex items-center gap-2 text-status-ai text-xs font-mono font-medium mb-2">
            <span className="material-symbols-outlined text-[18px]">psychology</span>
            <span>4. AERION INTELLIGENCE // AI ADVISORY (ADVISORY ONLY)</span>
          </div>
          <p className="text-xs text-paper leading-relaxed">
            {report?.ai_advisory?.advisory_text ||
              'Advisory model bounds all commentary strictly to verified ground truths. No hallucination of casualties, road blockages, or unverified crossing points permitted.'}
          </p>
          <div className="mt-3 pt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px] text-faint font-mono">
            <span>MODEL: {report?.ai_advisory?.model || 'open-mistral-nemo (bounded)'}</span>
            <span>PROVIDER STATUS: {report?.ai_advisory?.status || 'AVAILABLE'}</span>
            <span>HUMAN OPERATOR VERIFICATION REQUIRED</span>
          </div>
        </div>

        {/* 5. Verified Facts */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block mb-3">
            5. VERIFIED GROUND FACTS (EVIDENCE-LINKED)
          </span>
          {report?.verified_facts && report.verified_facts.length > 0 ? (
            <ul className="space-y-2 text-xs font-mono">
              {report.verified_facts.map((fact, i) => (
                <li key={i} className="flex items-start gap-2 text-paper">
                  <span className="text-accent mt-0.5">•</span>
                  <span>{fact}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-faint">
              NO VERIFIED FACTS FILED IN ACTIVE SITUATION
            </div>
          )}
        </div>

        {/* 6. Artifacts and Evidence Lineage */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block mb-3">
            6. AUDITABLE EVIDENCE LINEAGE & ARTIFACTS
          </span>
          {report?.evidence_lineage && report.evidence_lineage.length > 0 ? (
            <div className="space-y-2 text-xs font-mono">
              {report.evidence_lineage.map((ev, idx) => (
                <div key={ev.evidence_id || idx} className="p-2.5 bg-graphite/40 border border-white/[0.04] rounded flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-accent font-medium">{ev.source}</span>
                    {ev.verification_state && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] bg-elevated text-muted">
                        {ev.verification_state}
                      </span>
                    )}
                  </div>
                  <div className="text-faint text-[11px]">
                    SHA256: {ev.hash ? `${ev.hash.substring(0, 16)}...` : 'RECORDED'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-faint">
              ZERO FABRICATION: EVIDENCE LINEAGE UNRECORDED
            </div>
          )}

          {report?.artifacts && report.artifacts.length > 0 && (
            <div className="mt-4 pt-3 border-t border-white/[0.06] space-y-2">
              <span className="text-[11px] font-mono text-faint uppercase block">PERSISTED ARTIFACTS:</span>
              {report.artifacts.map((art, idx) => (
                <div key={art.artifact_key || idx} className="p-2 bg-graphite/30 rounded text-xs font-mono flex items-center justify-between text-muted">
                  <span>[{art.type}] {art.artifact_key}</span>
                  <span className="text-faint text-[10px]">SHA256: {art.sha256.substring(0, 12)}...</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

