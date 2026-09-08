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
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-graphite p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        <div className="border-b border-white/[0.06] pb-4">
          <h1 className="text-base font-semibold text-white tracking-wide uppercase font-sans">
            SYSTEM STATUS & ORCHESTRATION PROBES
          </h1>
          <p className="text-xs text-muted font-mono">
            FASTAPI /HEALTH AND /READY PROBE TELEMETRY
          </p>
        </div>

        {/* Liveness Card */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono text-muted uppercase">LIVENESS PROBE (GET /HEALTH)</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-status-success/10 text-status-success border border-status-success/20">
              {health?.status?.toUpperCase() || 'UNKNOWN'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <span className="text-faint block">API VERSION:</span>
              <span className="text-paper">{health?.version || 'v1'}</span>
            </div>
            <div>
              <span className="text-faint block">ENVIRONMENT:</span>
              <span className="text-paper">{health?.environment || 'development'}</span>
            </div>
            <div className="col-span-2">
              <span className="text-faint block">PROBE TIMESTAMP:</span>
              <span className="text-paper">{health?.timestamp || '--'}</span>
            </div>
          </div>
        </div>

        {/* Readiness Card */}
        <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono text-muted uppercase">READINESS SUBSYSTEMS (GET /READY)</span>
          </div>

          {readyData?.components ? (
            <div className="space-y-3 font-mono text-xs">
              {Object.entries(readyData.components).map(([key, value]: [string, any]) => (
                <div key={key} className="p-3 bg-graphite/40 rounded border border-white/[0.04]">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-paper uppercase">{key}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        value.status === 'ready'
                          ? 'bg-status-success/10 text-status-success'
                          : 'bg-status-warning/10 text-status-warning'
                      }`}
                    >
                      {value.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-faint">{value.details}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs font-mono text-faint">
              READINESS DATA PENDING INSPECTION
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
