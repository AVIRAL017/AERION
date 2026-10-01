import React, { useEffect, useState, useCallback } from 'react';
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

  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

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
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
          {s}
        </span>
      );
    }
    if (s.includes('FAIL') || s.includes('ERROR')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200">
          {s}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-50 text-accent border border-sky-200 animate-pulse">
        {s}
      </span>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          handleClose();
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="history-modal-title"
    >
      <div className="bg-white border border-slate-200 rounded-xl shadow-floating w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden font-sans animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/80 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-sky-100 text-accent">
              <span className="material-symbols-outlined text-[20px]">history</span>
            </div>
            <div>
              <h2 id="history-modal-title" className="text-sm font-bold uppercase tracking-wider text-slate-800 font-mono">
                OPERATIONAL ANALYSIS HISTORY
              </h2>
              <p className="text-[11px] text-slate-500 font-mono">
                DISCOVER & REOPEN PERSISTED ANALYSES • USER-SCOPED AUDIT TRAIL
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Mode Filter */}
            <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-xs font-mono">
              <button
                onClick={() => setSelectedFilter('all')}
                className={`px-3 py-1 rounded-md transition-all ${
                  selectedFilter === 'all' ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                ALL
              </button>
              <button
                onClick={() => setSelectedFilter('border')}
                className={`px-3 py-1 rounded-md transition-all ${
                  selectedFilter === 'border' ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                BORDER
              </button>
              <button
                onClick={() => setSelectedFilter('disaster')}
                className={`px-3 py-1 rounded-md transition-all ${
                  selectedFilter === 'disaster' ? 'bg-white text-accent font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                DISASTER
              </button>
            </div>

            <button
              onClick={handleClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              title="Close modal (Escape)"
              aria-label="Close modal"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-3 bg-white">
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center text-slate-500 font-mono text-xs gap-3">
              <span className="material-symbols-outlined text-accent animate-spin text-2xl">progress_activity</span>
              <span>SYNCHRONIZING TENANT ANALYSIS RECORDS...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 font-mono text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-rose-600">error</span>
              <span>{error}</span>
            </div>
          ) : history.length === 0 ? (
            <div className="py-16 flex flex-col items-center justify-center text-slate-400 font-mono text-xs gap-2">
              <span className="material-symbols-outlined text-slate-300 text-4xl">inventory_2</span>
              <span className="font-semibold text-slate-700">NO RECORDED ANALYSES FOUND FOR THIS OPERATIONAL SCOPE</span>
              <span className="text-[11px] text-slate-400">Submit a border image, video, or bi-temporal damage pair to initiate records.</span>
            </div>
          ) : (
            history.map((item) => {
              const targetId = item.analysis_id || item.job_id;

              return (
                <div
                  key={item.job_id}
                  className="p-4 rounded-xl bg-white border border-slate-200 hover:border-accent hover:shadow-card-hover transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 card-3d"
                >
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono text-xs font-bold text-slate-800">
                        {item.mode?.toUpperCase()}
                      </span>
                      {getStatusBadge(item.status)}
                      <span className="font-mono text-[10px] text-slate-400 truncate max-w-[220px]" title={targetId}>
                        ID: {targetId}
                      </span>
                    </div>

                    <div className="text-[11px] font-mono text-slate-500 flex items-center gap-4 flex-wrap">
                      <span>CREATED: {formatDate(item.created_at)}</span>
                      {item.completed_at && <span>COMPLETED: {formatDate(item.completed_at)}</span>}
                      {item.detections_count !== null && item.detections_count !== undefined && (
                        <span className="text-accent font-semibold">
                          {item.detections_count} DETECTIONS
                        </span>
                      )}
                      {item.damage_summary && (
                        <span className="text-amber-600 font-semibold">
                          DAMAGE: {item.damage_summary.damage_percentage?.toFixed(1)}% ({item.damage_summary.classification})
                        </span>
                      )}
                    </div>

                    {item.limitations && item.limitations.length > 0 && (
                      <div className="text-[10px] font-mono text-amber-700 flex items-center gap-1">
                        <span className="material-symbols-outlined text-[13px]">info</span>
                        <span>{item.limitations.length} operational limitation(s) noted</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    <button
                      onClick={() => {
                        onSelectAnalysis(item);
                        handleClose();
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-accent text-white font-mono font-bold text-xs hover:bg-accent-hover transition-all flex items-center gap-1.5 shadow-sm active:scale-95 cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                      <span>REOPEN</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>SHOWING {history.length} RECORDED ANALYSES</span>
          <span>TENANT ISOLATED • DETERMINISTIC EVIDENCE</span>
        </div>
      </div>
    </div>
  );
};
