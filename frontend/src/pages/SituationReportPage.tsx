import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { situationsApi } from '../api';
import { SituationReport } from '../types';

export const SituationReportPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<SituationReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchReport = async () => {
      setIsLoading(true);
      try {
        if (id) {
          const res = await situationsApi.getReport(id);
          if (res.success && res.data) {
            setReport(res.data);
          }
        }
      } catch {
        // Fallback
      } finally {
        setIsLoading(false);
      }
    };
    fetchReport();
  }, [id]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        COMPILING DETERMINISTIC SITUATION REPORT...
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-graphite p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        <div className="border-b border-white/[0.06] pb-4 flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-white tracking-wide uppercase font-sans">
              OPERATIONAL SITUATION REPORT
            </h1>
            <p className="text-xs text-muted font-mono">
              STRUCTURED INTELLIGENCE & DETERMINISTIC SYNTHESIS
            </p>
          </div>
          <span className="px-2.5 py-1 rounded bg-elevated border border-white/[0.08] text-[11px] font-mono text-muted">
            {report?.generated_at ? new Date(report.generated_at).toUTCString() : 'AWAITING GENERATION'}
          </span>
        </div>

        {/* Mistral AI Advisory Banner */}
        <div className="p-4 bg-panel border border-status-ai/30 rounded-lg">
          <div className="flex items-center gap-2 text-status-ai text-xs font-mono font-medium mb-2">
            <span className="material-symbols-outlined text-[18px]">psychology</span>
            <span>AERION INTELLIGENCE // AI ADVISORY (ADVISORY ONLY)</span>
          </div>
          <p className="text-xs text-paper leading-relaxed">
            {report?.ai_advisory?.advisory_text ||
              'Advisory model bounds all commentary strictly to verified ground truths. No hallucination of casualties, road blockages, or unverified crossing points permitted.'}
          </p>
          <div className="mt-3 pt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px] text-faint font-mono">
            <span>MODEL: {report?.ai_advisory?.model || 'open-mistral-nemo (bounded)'}</span>
            <span>HUMAN OPERATOR VERIFICATION REQUIRED</span>
          </div>
        </div>

        {/* Verified Facts */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block mb-3">
            VERIFIED GROUND FACTS (EVIDENCE-LINKED)
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

        {/* Evidence Lineage */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
          <span className="text-xs font-mono text-muted uppercase tracking-wider block mb-3">
            AUDITABLE EVIDENCE LINEAGE
          </span>
          {report?.evidence_lineage && report.evidence_lineage.length > 0 ? (
            <div className="space-y-2 text-xs font-mono">
              {report.evidence_lineage.map((ev) => (
                <div key={ev.evidence_id} className="p-2 bg-graphite/40 border border-white/[0.04] rounded flex justify-between">
                  <span className="text-paper">{ev.source}</span>
                  <span className="text-faint">{ev.hash.substring(0, 12)}...</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 rounded border border-white/[0.04] text-xs font-mono text-faint">
              ZERO FABRICATION: EVIDENCE LINEAGE UNRECORDED
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
