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
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-graphite p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
          <div>
            <h1 className="text-base font-semibold text-white tracking-wide uppercase font-sans">
              RESOURCE USAGE & QUOTAS
            </h1>
            <p className="text-xs text-muted font-mono">
              AUDITABLE METERED CONSUMPTION TELEMETRY
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded bg-accent/10 border border-accent/20 text-accent font-mono text-xs uppercase">
              TIER: {usage?.tier || 'FREE'}
            </span>
            {usage?.tier !== 'PRO' && (
              <button
                onClick={handleUpgrade}
                disabled={upgrading}
                className="px-3 py-1 bg-accent/20 hover:bg-accent/30 border border-accent/40 rounded text-accent font-mono text-xs transition-colors"
              >
                {upgrading ? 'Processing...' : 'Upgrade to PRO (₹9/mo)'}
              </button>
            )}
          </div>
        </div>

        {message && (
          <div className="p-3 bg-panel border border-accent/30 rounded text-accent text-xs font-mono">
            {message}
          </div>
        )}

        {/* Metering Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* API Requests */}
          <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-mono text-muted uppercase">API REQUESTS</span>
              <span className="text-xs font-mono text-paper font-medium">
                {usage ? `${usage.api_requests_used} / ${usage.api_requests_limit}` : '--'}
              </span>
            </div>
            <div className="w-full bg-graphite rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-accent h-full"
                style={{
                  width: usage ? `${Math.min((usage.api_requests_used / usage.api_requests_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
          </div>

          {/* Drone Processing Minutes */}
          <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-mono text-muted uppercase">DRONE PROCESSING (MIN)</span>
              <span className="text-xs font-mono text-paper font-medium">
                {usage ? `${usage.drone_processing_minutes_used} / ${usage.drone_processing_minutes_limit}` : '--'}
              </span>
            </div>
            <div className="w-full bg-graphite rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-status-warning h-full"
                style={{
                  width: usage ? `${Math.min((usage.drone_processing_minutes_used / usage.drone_processing_minutes_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
          </div>

          {/* Satellite Scenes */}
          <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-mono text-muted uppercase">SATELLITE SCENES</span>
              <span className="text-xs font-mono text-paper font-medium">
                {usage ? `${usage.satellite_scenes_used} / ${usage.satellite_scenes_limit}` : '--'}
              </span>
            </div>
            <div className="w-full bg-graphite rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-status-success h-full"
                style={{
                  width: usage ? `${Math.min((usage.satellite_scenes_used / usage.satellite_scenes_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
          </div>

          {/* Storage Bytes */}
          <div className="p-5 bg-panel border border-white/[0.06] rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-mono text-muted uppercase">STORAGE ALLOCATION</span>
              <span className="text-xs font-mono text-paper font-medium">
                {usage ? `${(usage.storage_bytes_used / 1e6).toFixed(1)} MB / ${(usage.storage_bytes_limit / 1e6).toFixed(0)} MB` : '--'}
              </span>
            </div>
            <div className="w-full bg-graphite rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-status-ai h-full"
                style={{
                  width: usage ? `${Math.min((usage.storage_bytes_used / usage.storage_bytes_limit) * 100, 100)}%` : '0%',
                }}
              ></div>
            </div>
          </div>
        </div>

        {/* Policy Invariant Note */}
        <div className="p-4 bg-graphite/40 border border-white/[0.04] rounded text-xs font-mono text-faint">
          INVARIANT: Plans are bounded. Quotas strictly enforce fair allocation across edge and cloud infrastructure without silent overflows.
        </div>
      </div>
    </div>
  );
};
