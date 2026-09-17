import React, { useEffect, useState } from 'react';
import { AnalysisHistoryItem } from '../types';
import { analysisApi } from '../api';

interface AnalysisHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectAnalysis: (item: AnalysisHistoryItem) => void;
  currentMode?: 'border' | 'disaster';
}

export const AnalysisHistoryModal: React.FC<AnalysisHistoryModalProps> = ({
  isOpen,
  onClose,
  onSelectAnalysis,
  currentMode,
}) => {
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>(currentMode || 'all');

  useEffect(() => {
    if (!isOpen) return;

    const fetchHistory = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const modeParam = selectedFilter !== 'all' ? selectedFilter : undefined;
        const resp = await analysisApi.getHistory({ mode: modeParam, limit: 50 });
        if (resp.success && resp.data) {
          setHistory(resp.data);
        } else {
          setError(typeof resp.error === 'string' ? resp.error : 'Failed to load analysis history.');
        }
      } catch (err: any) {
        setError(err.message || 'Error communicating with analysis service.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, [isOpen, selectedFilter]);

  if (!isOpen) return null;

  const formatDate = (isoStr?: string | null) => {
    if (!isoStr) return '--';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return isoStr;
    }
  };

  const getStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    if (s.includes('COMPLETED')) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-status-success/15 text-status-success border border-status-success/30">
          {s}
        </span>
      );
    }
    if (s.includes('FAIL') || s.includes('ERROR')) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-status-critical/15 text-status-critical border border-status-critical/30">
          {s}
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-accent/15 text-accent border border-accent/30 animate-pulse">
        {s}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0D1218] border border-white/[0.08] rounded-lg shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden font-sans">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between bg-panel/60">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded flex items-center justify-center bg-accent/10 border border-accent/20">
              <span className="material-symbols-outlined text-accent text-[18px]">history</span>
            </div>
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-white font-mono flex items-center gap-2">
                OPERATIONAL ANALYSIS HISTORY
              </h2>
              <p className="text-[11px] text-muted font-mono">
                DISCOVER & REOPEN PERSISTED ANALYSES • USER-SCOPED AUDIT TRAIL
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Mode Filter */}
            <div className="flex rounded bg-elevated/70 border border-white/[0.08] p-0.5 text-[11px] font-mono">
              <button
                onClick={() => setSelectedFilter('all')}
                className={`px-2.5 py-0.5 rounded transition-all ${
                  selectedFilter === 'all' ? 'bg-accent text-graphite font-bold' : 'text-muted hover:text-paper'
                }`}
              >
                ALL
              </button>
              <button
                onClick={() => setSelectedFilter('border')}
                className={`px-2.5 py-0.5 rounded transition-all ${
                  selectedFilter === 'border' ? 'bg-accent text-graphite font-bold' : 'text-muted hover:text-paper'
                }`}
              >
                BORDER
              </button>
              <button
                onClick={() => setSelectedFilter('disaster')}
                className={`px-2.5 py-0.5 rounded transition-all ${
                  selectedFilter === 'disaster' ? 'bg-accent text-graphite font-bold' : 'text-muted hover:text-paper'
                }`}
              >
                DISASTER
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-muted hover:text-paper transition-colors p-1 rounded hover:bg-elevated/60"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-3">
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center text-muted font-mono text-xs gap-3">
              <span className="material-symbols-outlined text-accent animate-spin text-2xl">progress_activity</span>
              <span>SYNCHRONIZING TENANT ANALYSIS RECORDS...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded bg-status-critical/10 border border-status-critical/30 text-status-critical font-mono text-xs flex items-center gap-2">
              <span className="material-symbols-outlined">error</span>
              <span>{error}</span>
            </div>
          ) : history.length === 0 ? (
            <div className="py-16 flex flex-col items-center justify-center text-muted font-mono text-xs gap-2">
              <span className="material-symbols-outlined text-muted/40 text-4xl">inventory_2</span>
              <span>NO RECORDED ANALYSES FOUND FOR THIS OPERATIONAL SCOPE</span>
              <span className="text-[10px] text-faint">Submit a border image, video, or bi-temporal damage pair to initiate records.</span>
            </div>
          ) : (
            history.map((item) => {
              const targetId = item.analysis_id || item.job_id;

              return (
                <div
                  key={item.job_id}
                  className="p-4 rounded-lg bg-panel/50 border border-white/[0.06] hover:border-accent/40 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 group"
                >
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono text-xs font-semibold text-paper">
                        {item.mode?.toUpperCase()}
                      </span>
                      {getStatusBadge(item.status)}
                      <span className="font-mono text-[10px] text-faint truncate max-w-[220px]" title={targetId}>
                        ID: {targetId}
                      </span>
                    </div>

                    <div className="text-[11px] font-mono text-muted flex items-center gap-4 flex-wrap">
                      <span>CREATED: {formatDate(item.created_at)}</span>
                      {item.completed_at && <span>COMPLETED: {formatDate(item.completed_at)}</span>}
                      {item.detections_count !== null && item.detections_count !== undefined && (
                        <span className="text-accent font-semibold">
                          {item.detections_count} DETECTIONS
                        </span>
                      )}
                      {item.damage_summary && (
                        <span className="text-status-warning font-semibold">
                          DAMAGE: {item.damage_summary.damage_percentage?.toFixed(1)}% ({item.damage_summary.classification})
                        </span>
                      )}
                    </div>

                    {item.limitations && item.limitations.length > 0 && (
                      <div className="text-[10px] font-mono text-status-warning/80 flex items-center gap-1">
                        <span className="material-symbols-outlined text-[12px]">info</span>
                        <span>{item.limitations.length} operational limitation(s) noted</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    <button
                      onClick={() => {
                        onSelectAnalysis(item);
                        onClose();
                      }}
                      className="px-3 py-1.5 rounded bg-accent text-graphite font-mono font-bold text-xs hover:bg-accent/90 transition-all flex items-center gap-1.5 shadow-sm"
                    >
                      <span className="material-symbols-outlined text-[15px]">open_in_new</span>
                      <span>REOPEN</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/[0.06] bg-panel/40 flex items-center justify-between text-[11px] font-mono text-muted">
          <span>SHOWING {history.length} RECORDED ANALYSES</span>
          <span>TENANT ISOLATED • DETERMINISTIC EVIDENCE</span>
        </div>
      </div>
    </div>
  );
};
