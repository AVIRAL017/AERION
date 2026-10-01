import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api';
import { Geospatial3DHero } from '../components/Geospatial3DHero';

const GOOGLE_CLIENT_ID =
  (import.meta as any).env?.VITE_GOOGLE_CLIENT_ID ||
  '491914857043-sqs1p7ntalt2irvr4vju0nav3ol4hnqd.apps.googleusercontent.com';

declare global {
  interface Window {
    __aerion_gsi_initialized?: boolean;
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
  const [searchParams] = useSearchParams();
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
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);

  // 3D Card Tilt State
  const cardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  const { login, loginWithGoogle, register, error } = useAuth();
  const navigate = useNavigate();
  const googleBtnRef = useRef<HTMLDivElement>(null);
  const handleGsiCallbackRef = useRef<(response: { credential?: string }) => void>(() => {});
  const handleGsiErrorRef = useRef<(err: any) => void>(() => {});

  // Automatic reset token detection from URL query parameters (e.g. /login?reset_token=xyz or /login?token=xyz)
  useEffect(() => {
    const urlResetToken = searchParams.get('reset_token') || searchParams.get('token');
    if (urlResetToken) {
      setResetToken(urlResetToken);
      setForgotMsg({
        message: 'Security token detected from verification link. Please enter your new passcode.',
        status: 'TOKEN_ACQUIRED',
        token: urlResetToken,
      });
      setShowForgotModal(true);
    }
  }, [searchParams]);

  // Escape key handler to close modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showForgotModal) {
        setShowForgotModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showForgotModal]);

  // Subtle 3D Card Hover Tilt Mechanics
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    // Bounded tilt angles for smooth dimensional depth without disorientation
    const rotX = -(y / (rect.height / 2)) * 4;
    const rotY = (x / (rect.width / 2)) * 4;
    setTilt({ x: rotX, y: rotY });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  useEffect(() => {
    handleGsiCallbackRef.current = async (response: { credential?: string }) => {
      if (response.credential) {
        setGoogleLoading(true);
        setGoogleConfigError(null);
        try {
          const ok = await loginWithGoogle(response.credential);
          setGoogleLoading(false);
          if (ok) {
            navigate('/border');
          }
        } catch (err: any) {
          setGoogleLoading(false);
          setGoogleConfigError(err.message || 'Google authentication failed.');
        }
      }
    };

    handleGsiErrorRef.current = (err: any) => {
      const isPopupClosed = err?.type === 'popup_closed' || err?.message?.includes('closed');
      if (isPopupClosed) {
        setGoogleConfigError('Google authentication was cancelled before completion.');
        return;
      }
      const msg =
        err?.type === 'origin_mismatch' || err?.message?.includes('origin_mismatch')
          ? `GOOGLE SIGN-IN UNAVAILABLE: Application origin (${window.location.origin}) is not registered under Authorized JavaScript Origins in Google Cloud Console.`
          : 'GOOGLE SIGN-IN UNAVAILABLE: OAuth provider configuration mismatch.';
      setGoogleConfigError(msg);
    };
  });

  useEffect(() => {
    const setupGsi = () => {
      try {
        if (!window.google?.accounts?.id) return;

        if (!window.__aerion_gsi_initialized) {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: (response: { credential?: string }) => {
              handleGsiCallbackRef.current(response);
            },
            auto_select: false,
            error_callback: (err: any) => {
              handleGsiErrorRef.current(err);
            },
          });
          window.__aerion_gsi_initialized = true;
        }

        if (googleBtnRef.current) {
          googleBtnRef.current.innerHTML = '';
          window.google.accounts.id.renderButton(googleBtnRef.current, {
            type: 'standard',
            theme: 'outline',
            size: 'large',
            text: authMode === 'register' ? 'signup_with' : 'signin_with',
            shape: 'rectangular',
            logo_alignment: 'left',
            width: Math.min(googleBtnRef.current.clientWidth || 380, 380),
          });
        }
      } catch (err: any) {
        setGoogleConfigError('GOOGLE SIGN-IN UNAVAILABLE: Google Identity Services could not initialize for this origin.');
      }
    };

    if (window.google?.accounts?.id) {
      setupGsi();
    } else {
      const interval = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(interval);
          setupGsi();
        }
      }, 150);
      return () => clearInterval(interval);
    }
  }, [authMode]);

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
    setResetError(null);
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
        setResetError(typeof res.error === 'string' ? res.error : (res.error as any)?.message || 'Failed to generate reset request.');
      }
    } catch (err: any) {
      setResetError(err.message || 'Error requesting reset');
    } finally {
      setForgotSubmitting(false);
    }
  };

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    setResetSuccess(null);

    if (newPassword.length < 8) {
      setResetError('Passcode must be at least 8 characters in length.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setResetError('Passcodes do not match. Please verify both fields.');
      return;
    }

    setForgotSubmitting(true);
    try {
      const res = await authApi.resetPassword({ token: resetToken, new_password: newPassword });
      if (res.success) {
        setResetSuccess('Passcode updated successfully! You may now sign in with your new credentials.');
        setTimeout(() => {
          setShowForgotModal(false);
          setResetSuccess(null);
          setForgotMsg(null);
          setPassword('');
          setNewPassword('');
          setConfirmPassword('');
        }, 1800);
      } else {
        setResetError(typeof res.error === 'string' ? res.error : (res.error as any)?.message || 'Passcode reset failed.');
      }
    } catch (err: any) {
      setResetError(err.message || 'Reset submission failed.');
    } finally {
      setForgotSubmitting(false);
    }
  };

  return (
    <div className="h-full w-full flex items-center justify-center bg-slate-50 spatial-grid p-4 sm:p-6 lg:p-10 relative perspective-1200 overflow-y-auto">
      <div className="w-full max-w-6xl flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-12 relative z-10 my-auto">
        {/* Left Column: Interactive 3D Geospatial Hero (Desktop/Tablet) */}
        <div className="hidden lg:flex flex-1 w-full max-w-lg card-3d bg-white/90 backdrop-blur-md border border-slate-200/90 rounded-2xl shadow-card overflow-hidden">
          <Geospatial3DHero />
        </div>

        {/* Right Column: Dimensional 3D Tilt Card */}
        <div
          ref={cardRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
            transition: tilt.x === 0 ? 'transform 0.4s ease-out' : 'none',
          }}
          className="w-full max-w-md bg-white border border-slate-200/90 rounded-2xl p-6 sm:p-8 shadow-floating relative transition-shadow duration-300"
        >
        {/* Subtle Spatial Horizon Line */}
        <div className="absolute -top-px left-8 right-8 h-[2px] bg-gradient-to-r from-transparent via-accent to-transparent opacity-80"></div>

        {/* Card Header & Switcher */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-accent/10 border border-accent/25 flex items-center justify-center text-accent shadow-sm">
              <span className="material-symbols-outlined text-[22px]">radar</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 tracking-wider uppercase font-sans">AERION COMMAND</h1>
              <p className="text-[11px] text-slate-500 font-mono">
                {authMode === 'login' ? 'OPERATOR AUTHENTICATION' : 'CREATE OPERATOR ACCOUNT'}
              </p>
            </div>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 font-mono text-[11px]">
            <button
              onClick={() => setAuthMode('login')}
              className={`px-3 py-1 rounded-md font-semibold transition-all ${
                authMode === 'login' ? 'bg-white text-slate-900 shadow-sm border border-slate-200/60' : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              LOGIN
            </button>
            <button
              onClick={() => setAuthMode('register')}
              className={`px-3 py-1 rounded-md font-semibold transition-all ${
                authMode === 'register' ? 'bg-white text-slate-900 shadow-sm border border-slate-200/60' : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              REGISTER
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs font-mono flex items-center gap-2">
            <span className="material-symbols-outlined text-[16px] text-red-600">error</span>
            <span>{error}</span>
          </div>
        )}

        {localMessage && (
          <div className="mb-4 p-3 rounded-lg bg-sky-50 border border-sky-200 text-sky-800 text-xs font-mono flex items-center gap-2">
            <span className="material-symbols-outlined text-[16px] text-accent">info</span>
            <span>{localMessage}</span>
          </div>
        )}

        {/* Google Authentication */}
        <div className="mb-5 space-y-2">
          <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-1.5 font-semibold">
            {authMode === 'login' ? 'Single Sign-On (Google Workspace)' : 'Continue with Google / Gmail'}
          </label>
          <div
            ref={googleBtnRef}
            className="w-full flex justify-center py-1 min-h-[44px] bg-slate-50 rounded-lg border border-slate-200 overflow-hidden"
          >
            {googleLoading && (
              <div className="flex items-center gap-2 text-slate-500 text-xs font-mono">
                <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
                <span>Authenticating with Google...</span>
              </div>
            )}
          </div>
          {googleConfigError && (
            <p className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 p-2 rounded font-mono leading-tight">
              {googleConfigError}
            </p>
          )}
        </div>

        {/* Divider */}
        <div className="relative my-5">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200"></div>
          </div>
          <div className="relative flex justify-center text-[10px] uppercase font-mono">
            <span className="bg-white px-2.5 text-slate-400 font-semibold tracking-wider">or operator credentials</span>
          </div>
        </div>

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {authMode === 'register' && (
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-600 mb-1 font-medium">
                Unit / Organization Name
              </label>
              <input
                type="text"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Tactical Response Wing"
                className="w-full h-10 px-3.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 font-sans focus:outline-none focus:bg-white focus:border-accent focus:ring-2 focus:ring-accent/15 transition-all"
              />
            </div>
          )}

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-600 mb-1 font-medium">
              Operator Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@aerion.local"
              className="w-full h-10 px-3.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 font-sans focus:outline-none focus:bg-white focus:border-accent focus:ring-2 focus:ring-accent/15 transition-all"
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-600 font-medium">
                Passcode
              </label>
              {authMode === 'login' && (
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  className="text-[11px] font-mono text-accent hover:text-sky-700 transition-colors font-medium"
                >
                  Forgot Passcode?
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
              className="w-full h-10 px-3.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 font-mono focus:outline-none focus:bg-white focus:border-accent focus:ring-2 focus:ring-accent/15 transition-all"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting || googleLoading}
            className="w-full h-10 mt-3 bg-accent hover:bg-sky-700 text-white font-semibold rounded-lg shadow-sm transition-all text-xs font-mono tracking-wider uppercase flex items-center justify-center gap-2 disabled:opacity-50 active:translate-y-[1px]"
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

        <div className="mt-6 pt-4 border-t border-slate-100 text-center">
          <p className="text-[10px] text-slate-400 font-mono tracking-wider">
            RESTRICTED GEOSPATIAL & DISASTER INTELLIGENCE TERMINAL
          </p>
        </div>
      </div>
    </div>

      {/* Forgot / Reset Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-floating relative font-mono text-xs animate-in fade-in zoom-in-95 duration-150">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <h2 className="text-slate-900 font-bold text-sm uppercase flex items-center gap-2">
                <span className="material-symbols-outlined text-accent text-[18px]">lock_reset</span>
                Reset Operator Passcode
              </h2>
              <button
                onClick={() => setShowForgotModal(false)}
                className="text-slate-400 hover:text-slate-700 transition-colors p-1"
                title="Close modal"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            {resetError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-red-600">error</span>
                <span>{resetError}</span>
              </div>
            )}

            {resetSuccess && (
              <div className="p-3 bg-green-50 border border-green-200 text-green-800 rounded-lg flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-green-600">check_circle</span>
                <span>{resetSuccess}</span>
              </div>
            )}

            {forgotMsg && !resetSuccess && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                <p className="text-slate-800 text-[11px] leading-relaxed">{forgotMsg.message}</p>
                <div className="text-[10px] text-slate-500 font-semibold">
                  DELIVERY STATUS: <span className="text-amber-600">{forgotMsg.status}</span>
                </div>
                {forgotMsg.token ? (
                  <div className="p-2.5 bg-sky-50/60 rounded-md border border-sky-200">
                    <span className="text-sky-800 text-[10px] font-bold block mb-1">LOCAL SIMULATION TOKEN (DEV / TEST):</span>
                    <code className="text-[11px] text-sky-950 font-mono break-all select-all font-semibold">
                      {forgotMsg.token}
                    </code>
                  </div>
                ) : (
                  <div className="p-2.5 bg-emerald-50/80 rounded-md border border-emerald-200 text-emerald-800 text-[10px] font-mono leading-relaxed">
                    <span className="font-bold block text-emerald-900 mb-0.5">SECURE CHANNEL DISPATCH (PRODUCTION):</span>
                    Verification instructions and one-time reset token have been dispatched to your registered operational inbox. In production, reset tokens are never exposed in client UI. Enter the received token below.
                  </div>
                )}
              </div>
            )}

            {!forgotMsg && !resetToken ? (
              <form onSubmit={handleForgotSubmit} className="space-y-3">
                <p className="text-slate-600 text-[11px] leading-relaxed">
                  Enter your registered operator email to initiate single-use token verification.
                </p>
                <div>
                  <label className="block text-slate-600 text-[10px] uppercase mb-1 font-semibold">Operator Email</label>
                  <input
                    type="email"
                    required
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="operator@aerion.local"
                    className="w-full h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:bg-white focus:border-accent focus:ring-2 focus:ring-accent/15 transition-all text-xs"
                  />
                </div>
                <div className="flex justify-end gap-2.5 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(false)}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={forgotSubmitting}
                    className="px-4 py-2 bg-accent hover:bg-sky-700 text-white font-semibold rounded-lg shadow-sm transition-all"
                  >
                    {forgotSubmitting ? 'Requesting...' : 'Generate Reset Token'}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleResetSubmit} className="space-y-3">
                <div>
                  <label className="block text-slate-600 text-[10px] uppercase mb-1 font-semibold">Reset Token</label>
                  <input
                    type="text"
                    required
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    placeholder="Paste one-time token from verification email"
                    className="w-full h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono text-[11px] focus:bg-white focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-slate-600 text-[10px] uppercase mb-1 font-semibold">New Passcode (min 8 chars)</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono text-[11px] focus:bg-white focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-slate-600 text-[10px] uppercase mb-1 font-semibold">Confirm New Passcode</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono text-[11px] focus:bg-white focus:border-accent"
                  />
                </div>
                <div className="flex justify-end gap-2.5 pt-2">
                  <button
                    type="button"
                    onClick={() => { setForgotMsg(null); setResetError(null); }}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 font-medium transition-colors"
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={forgotSubmitting}
                    className="px-4 py-2 bg-accent hover:bg-sky-700 text-white font-semibold rounded-lg shadow-sm transition-all"
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
