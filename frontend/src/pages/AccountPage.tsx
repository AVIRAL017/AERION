import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { usageApi } from '../api';
import { UsageSummary } from '../types';

export const AccountPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [isLoadingUsage, setIsLoadingUsage] = useState<boolean>(true);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState<boolean>(false);

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const res = await usageApi.getSummary();
        if (res.success && res.data) {
          setUsage(res.data);
        }
      } catch {
        // Soft fallback
      } finally {
        setIsLoadingUsage(false);
      }
    };
    fetchUsage();
  }, []);

  if (!user) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        NO ACTIVE OPERATOR SESSION DETECTED.
      </div>
    );
  }

  const isGoogle = user.auth_provider === 'google';

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-graphite p-8">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
          <div>
            <h1 className="text-base font-semibold text-white tracking-wide uppercase font-sans">
              OPERATOR COMMAND HUB
            </h1>
            <p className="text-xs text-muted font-mono">
              AUTHENTICATED IDENTITY & SECURITY SETTINGS
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`px-2.5 py-1 rounded font-mono text-xs uppercase border ${
                isGoogle
                  ? 'bg-accent/10 border-accent/30 text-accent'
                  : 'bg-elevated border-white/[0.08] text-paper'
              }`}
            >
              AUTHENTICATION: {isGoogle ? 'GOOGLE WORKSPACE' : 'LOCAL ACCOUNT'}
            </span>
          </div>
        </div>

        {/* Identity & Tenant Card */}
        <div className="p-6 bg-panel border border-white/[0.06] rounded-lg space-y-4 font-mono text-xs">
          <div className="flex items-center gap-4 pb-4 border-b border-white/[0.06]">
            <div className="w-12 h-12 rounded-full bg-elevated border border-accent/30 flex items-center justify-center text-accent text-base font-bold">
              {(user.display_name || user.email).substring(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="text-sm font-semibold text-white">
                {user.display_name || user.email}
              </div>
              <div className="text-muted text-[11px]">{user.email}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div>
              <span className="text-faint uppercase text-[10px] block mb-1">Operator User ID</span>
              <span className="text-paper bg-graphite px-2 py-1 rounded border border-white/[0.04] block break-all">
                {user.id}
              </span>
            </div>

            <div>
              <span className="text-faint uppercase text-[10px] block mb-1">Assigned Role</span>
              <span className="text-accent bg-accent/10 px-2 py-1 rounded border border-accent/20 inline-block uppercase">
                {user.role}
              </span>
            </div>

            <div>
              <span className="text-faint uppercase text-[10px] block mb-1">Authentication Provider</span>
              <span className="text-paper">
                {isGoogle ? 'Google OAuth 2.0 OpenID Connect' : 'Argon2id Salted Passcode'}
              </span>
            </div>

            <div>
              <span className="text-faint uppercase text-[10px] block mb-1">Session Status</span>
              <span className="text-status-success flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse"></span>
                ACTIVE (Auto-renewed)
              </span>
            </div>

            <div>
              <span className="text-faint uppercase text-[10px] block mb-1">Account Created At</span>
              <span className="text-paper">{user.created_at || 'Authoritative session'}</span>
            </div>

            <div>
              <span className="text-faint uppercase text-[10px] block mb-1">Organization ID</span>
              <span className="text-paper bg-graphite px-2 py-1 rounded border border-white/[0.04] block break-all">
                {(user as any).organization_id || '00000000-0000-0000-0000-000000000001'}
              </span>
            </div>
          </div>
        </div>

        {/* Plan & Entitlement Overview */}
        <div className="p-6 bg-panel border border-white/[0.06] rounded-lg space-y-4 font-mono text-xs">
          <div className="flex justify-between items-center pb-3 border-b border-white/[0.06]">
            <span className="text-white font-semibold uppercase">SUBSCRIPTION & QUOTA TIER</span>
            <span className="px-2.5 py-0.5 rounded bg-accent/20 border border-accent/30 text-accent uppercase text-[11px]">
              {usage?.tier || 'FREE'}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-graphite rounded border border-white/[0.04]">
              <span className="text-faint block text-[10px] uppercase">API Calls</span>
              <span className="text-paper text-sm font-semibold">
                {isLoadingUsage ? '--' : `${usage?.api_requests_used} / ${usage?.api_requests_limit}`}
              </span>
            </div>
            <div className="p-3 bg-graphite rounded border border-white/[0.04]">
              <span className="text-faint block text-[10px] uppercase">Drone Minutes</span>
              <span className="text-paper text-sm font-semibold">
                {isLoadingUsage ? '--' : `${usage?.drone_processing_minutes_used} / ${usage?.drone_processing_minutes_limit}`}
              </span>
            </div>
            <div className="p-3 bg-graphite rounded border border-white/[0.04]">
              <span className="text-faint block text-[10px] uppercase">Satellite Scenes</span>
              <span className="text-paper text-sm font-semibold">
                {isLoadingUsage ? '--' : `${usage?.satellite_scenes_used} / ${usage?.satellite_scenes_limit}`}
              </span>
            </div>
            <div className="p-3 bg-graphite rounded border border-white/[0.04]">
              <span className="text-faint block text-[10px] uppercase">Storage</span>
              <span className="text-paper text-sm font-semibold">
                {isLoadingUsage ? '--' : `${((usage?.storage_bytes_used || 0) / 1e6).toFixed(1)} MB`}
              </span>
            </div>
          </div>
        </div>

        {/* Security Actions */}
        <div className="p-6 bg-panel border border-white/[0.06] rounded-lg flex items-center justify-between font-mono text-xs">
          <div>
            <div className="text-white font-semibold uppercase">TERMINATE COMMAND SESSION</div>
            <p className="text-faint text-[11px] mt-0.5">
              Securely invalidate your active token and return to the operator authentication portal.
            </p>
          </div>

          <button
            onClick={() => setShowLogoutConfirm(true)}
            className="px-4 py-2 rounded bg-status-critical/10 hover:bg-status-critical/20 border border-status-critical/30 text-status-critical transition-colors uppercase"
          >
            Sign Out
          </button>
        </div>
      </div>

      {/* Logout Confirmation Dialog */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-panel border border-white/[0.1] rounded-xl max-w-sm w-full p-6 space-y-4 shadow-2xl font-mono text-xs">
            <div className="flex items-center gap-3 text-status-warning">
              <span className="material-symbols-outlined text-[24px]">warning</span>
              <h3 className="text-white font-semibold text-sm uppercase">Confirm Sign Out</h3>
            </div>
            <p className="text-muted text-[11px]">
              Are you sure you want to end your operational command session?
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="px-3 py-1.5 rounded bg-elevated hover:bg-elevated/80 text-muted font-mono transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowLogoutConfirm(false);
                  logout();
                }}
                className="px-3 py-1.5 rounded bg-status-critical/20 hover:bg-status-critical/30 border border-status-critical/40 text-status-critical font-mono transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
