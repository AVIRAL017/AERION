import React, { useEffect, useState } from 'react';
import { usageApi } from '../api';
import { UsageSummary } from '../types';

export const UsagePage: React.FC = () => {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [upgrading, setUpgrading] = useState<boolean>(false);
  const [message, setMessage] = useState<string | null>(null);

  const fetchUsage = async () => {
    setIsLoading(true);
    try {
      const res = await usageApi.getSummary();
      if (res.success && res.data) {
        setUsage(res.data);
      }
    } catch {
      // Fallback
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, []);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        SYNCHRONIZING RESOURCE USAGE TELEMETRY...
      </div>
    );
  }

  const handleUpgrade = async () => {
    setUpgrading(true);
    setMessage(null);
    try {
      const res = await usageApi.upgradeSubscription('PRO');
      if (res.success) {
        setMessage('Subscription upgraded to PRO (₹9/month).');
        fetchUsage();
      } else {
        setMessage(res.error || 'Upgrade failed');
      }
    } catch (err: any) {
      setMessage(err.message || 'Upgrade request failed');
    } finally {
      setUpgrading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-slate-50 p-6 sm:p-8">
      <div className="max-w-5xl mx-auto w-full space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-200 pb-5 gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-accent text-[22px]">data_usage</span>
              <h1 className="text-lg font-bold text-slate-900 tracking-wide uppercase font-sans">
                RESOURCE USAGE & QUOTAS
              </h1>
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">
              AUDITABLE METERED CONSUMPTION TELEMETRY & EDGE WORKLOAD ALLOCATION
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-sky-700 font-mono text-xs font-semibold uppercase shadow-2xs">
              TIER: {usage?.tier || 'FREE'}
            </span>
            {usage?.tier !== 'PRO' && (
              <button
                onClick={handleUpgrade}
                disabled={upgrading}
                className="px-3.5 py-1.5 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white rounded-lg font-mono text-xs uppercase font-semibold transition-all shadow-sm"
              >
                {upgrading ? 'Processing...' : 'Upgrade to PRO (₹9/mo)'}
              </button>
            )}
          </div>
        </div>

        {message && (
          <div className="p-3.5 bg-sky-50 border border-sky-200 rounded-xl text-sky-800 text-xs font-mono shadow-2xs">
            {message}
          </div>
        )}

        {/* Metering Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* API Requests */}
          <div className="card-3d-interactive p-6 bg-white border border-slate-200 rounded-xl space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-sky-600 text-[18px]">api</span>
                <span className="text-xs font-mono text-slate-600 uppercase font-bold">API REQUESTS</span>
              </div>
              <span className="text-sm font-mono text-slate-900 font-bold">
                {usage ? `${usage.api_requests_used} / ${usage.api_requests_limit}` : '--'}
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60">
              <div
                className="bg-sky-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: usage ? `${Math.min((usage.api_requests_used / usage.api_requests_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400 font-mono block">Inference and situational query calls across edge gateway</span>
          </div>

          {/* Drone Processing Minutes */}
          <div className="card-3d-interactive p-6 bg-white border border-slate-200 rounded-xl space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-600 text-[18px]">flight</span>
                <span className="text-xs font-mono text-slate-600 uppercase font-bold">DRONE PROCESSING (MIN)</span>
              </div>
              <span className="text-sm font-mono text-slate-900 font-bold">
                {usage ? `${usage.drone_processing_minutes_used} / ${usage.drone_processing_minutes_limit}` : '--'}
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60">
              <div
                className="bg-amber-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: usage ? `${Math.min((usage.drone_processing_minutes_used / usage.drone_processing_minutes_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400 font-mono block">Tactical aerial stream transcoding and frame segmentation</span>
          </div>

          {/* Satellite Scenes */}
          <div className="card-3d-interactive p-6 bg-white border border-slate-200 rounded-xl space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-emerald-600 text-[18px]">satellite_alt</span>
                <span className="text-xs font-mono text-slate-600 uppercase font-bold">SATELLITE SCENES</span>
              </div>
              <span className="text-sm font-mono text-slate-900 font-bold">
                {usage ? `${usage.satellite_scenes_used} / ${usage.satellite_scenes_limit}` : '--'}
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: usage ? `${Math.min((usage.satellite_scenes_used / usage.satellite_scenes_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400 font-mono block">Multi-spectral satellite tiles ingested from Copernicus & Sentinel</span>
          </div>

          {/* Storage Bytes */}
          <div className="card-3d-interactive p-6 bg-white border border-slate-200 rounded-xl space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-indigo-600 text-[18px]">hard_drive</span>
                <span className="text-xs font-mono text-slate-600 uppercase font-bold">STORAGE ALLOCATION</span>
              </div>
              <span className="text-sm font-mono text-slate-900 font-bold">
                {usage ? `${(usage.storage_bytes_used / 1e6).toFixed(1)} MB / ${(usage.storage_bytes_limit / 1e6).toFixed(0)} MB` : '--'}
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60">
              <div
                className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                style={{
                  width: usage ? `${Math.min((usage.storage_bytes_used / usage.storage_bytes_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
            <span className="text-[10px] text-slate-400 font-mono block">Encrypted telemetry, vector embeddings, and forensic reports</span>
          </div>
        </div>

        {/* Policy Invariant Note */}
        <div className="card-3d p-4 bg-white/90 border border-slate-200 rounded-xl text-xs font-mono text-slate-500 flex items-center gap-3">
          <span className="material-symbols-outlined text-sky-600 text-[20px]">verified</span>
          <span>INVARIANT: Plans are strictly bounded. Quotas enforce fair allocation across edge and cloud infrastructure without silent overflows.</span>
        </div>
      </div>
    </div>
  );
};
