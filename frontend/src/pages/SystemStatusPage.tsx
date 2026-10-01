import React, { useEffect, useState } from 'react';
import { systemApi } from '../api';
import { HealthStatus } from '../types';

export const SystemStatusPage: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [readyData, setReadyData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchSystemStatus = async () => {
      setIsLoading(true);
      try {
        const [healthRes, readyRes] = await Promise.all([
          systemApi.getHealth(),
          systemApi.getReady(),
        ]);
        if (healthRes.success && healthRes.data) {
          setHealth(healthRes.data);
        }
        if (readyRes.success && readyRes.data) {
          setReadyData(readyRes.data);
        }
      } catch {
        // Fallback
      } finally {
        setIsLoading(false);
      }
    };
    fetchSystemStatus();
  }, []);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        POLLING SUBSYSTEM READINESS PROBES...
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-slate-50 p-6 sm:p-8">
      <div className="max-w-5xl mx-auto w-full space-y-6">
        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-accent text-[22px]">monitor_heart</span>
            <h1 className="text-lg font-bold text-slate-900 tracking-wide uppercase font-sans">
              SYSTEM STATUS & ORCHESTRATION PROBES
            </h1>
          </div>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            FASTAPI AUTOMATED HEALTHCHECK AND SUBSYSTEM RUNTIME TELEMETRY
          </p>
        </div>

        {/* Liveness Card */}
        <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <span className="text-xs font-mono text-slate-700 uppercase font-bold">LIVENESS PROBE (GET /HEALTH)</span>
            <span className="px-3 py-0.5 rounded-full text-[11px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              {health?.status?.toUpperCase() || 'UNKNOWN'}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs font-mono">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase">API VERSION</span>
              <span className="text-slate-900 font-bold">{health?.version || 'v1'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase">ENVIRONMENT</span>
              <span className="text-slate-900 font-bold">{health?.environment || 'development'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 col-span-2 md:col-span-1">
              <span className="text-slate-400 block text-[10px] uppercase">PROBE TIMESTAMP</span>
              <span className="text-slate-900 font-bold">{health?.timestamp || '--'}</span>
            </div>
          </div>
        </div>

        {/* Readiness Card */}
        <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <span className="text-xs font-mono text-slate-700 uppercase font-bold">READINESS SUBSYSTEMS (GET /READY)</span>
            <span className="text-[11px] font-mono text-slate-400">POSTGRES • REDIS • ONNX • ML INFERENCE</span>
          </div>

          {readyData?.components ? (
            <div className="space-y-3 font-mono text-xs">
              {Object.entries(readyData.components).map(([key, value]: [string, any]) => (
                <div key={key} className="card-3d-interactive p-4 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-slate-900 font-bold uppercase tracking-wider">{key}</span>
                    <span
                      className={`text-[10px] px-2.5 py-0.5 rounded-full font-bold uppercase border ${
                        value.status === 'ready'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {value.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">{value.details}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs font-mono text-slate-400 py-4 text-center">
              READINESS DATA PENDING QUERY EXECUTION
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
