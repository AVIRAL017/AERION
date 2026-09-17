import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api';

// Default Google OAuth Client ID matching AERION Google Cloud project configuration
const GOOGLE_CLIENT_ID =
  (import.meta as any).env?.VITE_GOOGLE_CLIENT_ID ||
  '491914857043-sqs1p7ntalt2irvr4vju0nav3ol4hnqd.apps.googleusercontent.com';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: any) => void;
          renderButton: (parent: HTMLElement, options: any) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export const LoginPage: React.FC = () => {
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConfigError, setGoogleConfigError] = useState<string | null>(null);
  const [localMessage, setLocalMessage] = useState<string | null>(null);

  // Forgot password modal state
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSubmitting, setForgotSubmitting] = useState(false);
  const [forgotMsg, setForgotMsg] = useState<{ message: string; status: string; token?: string } | null>(null);
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);

  const { login, loginWithGoogle, register, error } = useAuth();
  const navigate = useNavigate();
  const googleBtnRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initialize Google Identity Services button
    const initGsi = () => {
      try {
        if (window.google?.accounts?.id && googleBtnRef.current) {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: async (response: { credential?: string }) => {
              if (response.credential) {
                setGoogleLoading(true);
                setGoogleConfigError(null);
                const ok = await loginWithGoogle(response.credential);
                setGoogleLoading(false);
                if (ok) {
                  navigate('/border');
                }
              }
            },
            auto_select: false,
            error_callback: (err: any) => {
              const msg = err?.type === 'origin_mismatch' || err?.message?.includes('origin_mismatch')
                ? `GOOGLE SIGN-IN UNAVAILABLE: Application origin (${window.location.origin}) is not registered in Google Cloud Console.`
                : 'GOOGLE SIGN-IN UNAVAILABLE: OAuth provider configuration mismatch.';
              setGoogleConfigError(msg);
            },
          });

          window.google.accounts.id.renderButton(googleBtnRef.current, {
            type: 'standard',
            theme: 'filled_black',
            size: 'large',
            text: 'signin_with',
            shape: 'rectangular',
            logo_alignment: 'left',
            width: googleBtnRef.current.clientWidth || 380,
          });
        }
      } catch (err: any) {
        setGoogleConfigError('GOOGLE SIGN-IN UNAVAILABLE: Google Identity Services could not initialize for this origin.');
      }
    };

    if (window.google?.accounts?.id) {
      initGsi();
    } else {
      const interval = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(interval);
          initGsi();
        }
      }, 200);
      return () => clearInterval(interval);
    }
  }, [loginWithGoogle, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setLocalMessage(null);

    if (authMode === 'register') {
      const ok = await register({
        email,
        password,
        full_name: orgName || 'AERION Operations',
        role: 'operator',
      });
      setIsSubmitting(false);
      if (ok) {
        navigate('/border');
      }
    } else {
      const ok = await login({ username: email, password });
      setIsSubmitting(false);
      if (ok) {
        navigate('/border');
      }
    }
  };

  const handleForgotSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotSubmitting(true);
    setForgotMsg(null);
    try {
      const res = await authApi.forgotPassword(forgotEmail);
      if (res.success && res.data) {
        setForgotMsg({
          message: res.data.message,
          status: res.data.delivery_status,
          token: res.data.reset_token,
        });
        if (res.data.reset_token) {
          setResetToken(res.data.reset_token);
        }
      } else {
        setForgotMsg({ message: res.error || 'Failed to generate reset request.', status: 'ERROR' });
      }
    } catch (err: any) {
      setForgotMsg({ message: err.message || 'Error requesting reset', status: 'ERROR' });
    } finally {
      setForgotSubmitting(false);
    }
  };

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotSubmitting(true);
    setResetSuccess(null);
    try {
      const res = await authApi.resetPassword({ token: resetToken, new_password: newPassword });
      if (res.success) {
        setResetSuccess('Password reset successfully! You can now log in with your new passcode.');
        setTimeout(() => {
          setShowForgotModal(false);
          setResetSuccess(null);
          setForgotMsg(null);
          setPassword('');
        }, 2000);
      } else {
        setForgotMsg({ message: res.error || 'Password reset failed.', status: 'ERROR' });
      }
    } catch (err: any) {
      setForgotMsg({ message: err.message || 'Reset submission failed.', status: 'ERROR' });
    } finally {
      setForgotSubmitting(false);
    }
  };

  return (
    <div className="h-full w-full flex items-center justify-center bg-graphite telemetry-grid p-6 relative">
      <div className="w-full max-w-md bg-panel border border-white/[0.08] rounded-xl p-8 shadow-2xl relative">
        {/* Glow accent */}
        <div className="absolute -top-px left-10 right-10 h-px bg-gradient-to-r from-transparent via-accent to-transparent"></div>

        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
              <span className="material-symbols-outlined text-accent text-[20px]">lock</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white tracking-wide uppercase">AERION COMMAND</h1>
              <p className="text-xs text-muted font-mono">
                {authMode === 'login' ? 'OPERATOR AUTHENTICATION' : 'CREATE OPERATOR ACCOUNT'}
              </p>
            </div>
          </div>

          <div className="flex rounded bg-elevated/70 border border-white/[0.06] p-0.5 text-[10px] font-mono">
            <button
              onClick={() => setAuthMode('login')}
              className={`px-2 py-1 rounded transition-colors ${authMode === 'login' ? 'bg-accent/20 text-accent font-medium' : 'text-muted hover:text-white'}`}
            >
              LOGIN
            </button>
            <button
              onClick={() => setAuthMode('register')}
              className={`px-2 py-1 rounded transition-colors ${authMode === 'register' ? 'bg-accent/20 text-accent font-medium' : 'text-muted hover:text-white'}`}
            >
              REGISTER
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-status-critical/10 border border-status-critical/20 text-status-critical text-xs font-mono">
            {error}
          </div>
        )}

        {localMessage && (
          <div className="mb-4 p-3 rounded bg-accent/10 border border-accent/20 text-accent text-xs font-mono">
            {localMessage}
          </div>
        )}

        {/* 1. Google Single Sign-On (Login Mode) */}
        {authMode === 'login' && (
          <div className="mb-5 space-y-2">
            <label className="block text-[11px] font-mono uppercase tracking-wider text-muted mb-1.5">
              Single Sign-On (Google Workspace)
            </label>
            <div
              ref={googleBtnRef}
              className="w-full min-h-[44px] flex items-center justify-center rounded overflow-hidden border border-white/[0.08] bg-[#131314]"
            >
              {googleLoading && (
                <div className="flex items-center gap-2 text-xs font-mono text-muted py-2">
                  <span className="animate-spin material-symbols-outlined text-[16px]">progress_activity</span>
                  Verifying Google Credentials...
                </div>
              )}
            </div>
            {googleConfigError && (
              <div className="p-2.5 bg-status-warning/10 border border-status-warning/30 rounded text-[11px] font-mono text-status-warning space-y-1">
                <div className="flex items-center gap-1.5 font-bold">
                  <span className="material-symbols-outlined text-[14px]">warning</span>
                  <span>{googleConfigError}</span>
                </div>
                <p className="text-[10px] text-faint leading-tight">
                  Add <code className="bg-graphite px-1 rounded text-paper">{window.location.origin}</code> under Authorized JavaScript Origins in Google Cloud Console OAuth 2.0 Client credentials.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Divider */}
        {authMode === 'login' && (
          <div className="relative my-6 flex items-center justify-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/[0.08]"></div>
            </div>
            <span className="relative bg-panel px-3 text-[10px] font-mono text-muted uppercase tracking-widest">
              OR OPERATOR PASSCODE
            </span>
          </div>
        )}

        {/* 2. Standard Passcode Login / Register Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {authMode === 'register' && (
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-muted mb-1.5">
                Organization / Unit Name
              </label>
              <input
                type="text"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Border Guard Sector 4"
                className="w-full h-10 px-3 bg-graphite border border-white/[0.08] rounded text-sm text-paper font-mono focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
              />
            </div>
          )}

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-muted mb-1.5">
              Operator Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@aerion.gov"
              className="w-full h-10 px-3 bg-graphite border border-white/[0.08] rounded text-sm text-paper font-mono focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-[11px] font-mono uppercase tracking-wider text-muted">
                Passcode {authMode === 'register' && '(min. 8 characters)'}
              </label>
              {authMode === 'login' && (
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  className="text-[10px] font-mono text-accent hover:underline"
                >
                  Forgot passcode?
                </button>
              )}
            </div>
            <input
              type="password"
              required
              minLength={authMode === 'register' ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full h-10 px-3 bg-graphite border border-white/[0.08] rounded text-sm text-paper font-mono focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting || googleLoading}
            className="w-full h-10 mt-2 bg-accent/10 hover:bg-accent/20 border border-accent/30 hover:border-accent text-accent font-medium rounded transition-all text-xs font-mono tracking-wider uppercase flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSubmitting ? (
              <span className="animate-spin material-symbols-outlined text-[16px]">progress_activity</span>
            ) : (
              <span className="material-symbols-outlined text-[16px]">
                {authMode === 'login' ? 'login' : 'how_to_reg'}
              </span>
            )}
            {authMode === 'login' ? 'Authenticate Session' : 'Register Operator Account'}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-white/[0.06] text-center">
          <p className="text-[11px] text-faint font-mono">
            RESTRICTED GOVERNMENT & DISASTER OPERATIONAL TERMINAL
          </p>
        </div>
      </div>

      {/* Forgot / Reset Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-panel border border-white/[0.1] rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative font-mono text-xs">
            <div className="flex justify-between items-center border-b border-white/[0.08] pb-3">
              <h2 className="text-white font-semibold text-sm uppercase flex items-center gap-2">
                <span className="material-symbols-outlined text-accent text-[18px]">lock_reset</span>
                Reset Operator Passcode
              </h2>
              <button
                onClick={() => setShowForgotModal(false)}
                className="text-muted hover:text-white"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            {resetSuccess && (
              <div className="p-3 bg-status-success/10 border border-status-success/20 text-status-success rounded">
                {resetSuccess}
              </div>
            )}

            {forgotMsg && !resetSuccess && (
              <div className="p-3 bg-white/[0.03] border border-white/[0.08] rounded space-y-2">
                <p className="text-paper">{forgotMsg.message}</p>
                <div className="text-[10px] text-faint">
                  DELIVERY STATUS: <span className="text-status-warning">{forgotMsg.status}</span>
                </div>
                {forgotMsg.token && (
                  <div className="p-2 bg-graphite rounded border border-accent/20">
                    <span className="text-accent text-[10px] block mb-1">LOCAL DEV SIMULATION TOKEN:</span>
                    <code className="text-[11px] text-paper break-all">{forgotMsg.token}</code>
                  </div>
                )}
              </div>
            )}

            {!forgotMsg?.token ? (
              <form onSubmit={handleForgotSubmit} className="space-y-3">
                <p className="text-muted text-[11px]">
                  Enter your registered operator email to initiate single-use token verification.
                </p>
                <div>
                  <label className="block text-muted text-[10px] uppercase mb-1">Operator Email</label>
                  <input
                    type="email"
                    required
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="operator@aerion.gov"
                    className="w-full h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper focus:outline-none focus:border-accent"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(false)}
                    className="px-3 py-1.5 bg-elevated hover:bg-elevated/80 rounded text-muted"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={forgotSubmitting}
                    className="px-3 py-1.5 bg-accent/20 hover:bg-accent/30 text-accent border border-accent/30 rounded"
                  >
                    {forgotSubmitting ? 'Requesting...' : 'Generate Reset Token'}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleResetSubmit} className="space-y-3">
                <div>
                  <label className="block text-muted text-[10px] uppercase mb-1">Reset Token</label>
                  <input
                    type="text"
                    required
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    className="w-full h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper font-mono text-[11px]"
                  />
                </div>
                <div>
                  <label className="block text-muted text-[10px] uppercase mb-1">New Passcode (min 8 chars)</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper font-mono text-[11px]"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setForgotMsg(null)}
                    className="px-3 py-1.5 bg-elevated hover:bg-elevated/80 rounded text-muted"
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={forgotSubmitting}
                    className="px-3 py-1.5 bg-accent/20 hover:bg-accent/30 text-accent border border-accent/30 rounded"
                  >
                    {forgotSubmitting ? 'Updating...' : 'Set New Passcode'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};


