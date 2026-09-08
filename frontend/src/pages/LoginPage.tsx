import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, error } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    const ok = await login({ username: email, password });
    setIsSubmitting(false);
    if (ok) {
      navigate('/border');
    }
  };

  return (
    <div className="h-full w-full flex items-center justify-center bg-graphite telemetry-grid p-6">
      <div className="w-full max-w-md bg-panel border border-white/[0.08] rounded-xl p-8 shadow-2xl relative">
        {/* Glow accent */}
        <div className="absolute -top-px left-10 right-10 h-px bg-gradient-to-r from-transparent via-accent to-transparent"></div>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
            <span className="material-symbols-outlined text-accent text-[20px]">lock</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white tracking-wide uppercase">AERION COMMAND</h1>
            <p className="text-xs text-muted font-mono">OPERATOR AUTHENTICATION</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded bg-status-critical/10 border border-status-critical/20 text-status-critical text-xs font-mono">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
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
            <label className="block text-[11px] font-mono uppercase tracking-wider text-muted mb-1.5">
              Passcode
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full h-10 px-3 bg-graphite border border-white/[0.08] rounded text-sm text-paper font-mono focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full h-10 mt-2 bg-accent/10 hover:bg-accent/20 border border-accent/30 hover:border-accent text-accent font-medium rounded transition-all text-xs font-mono tracking-wider uppercase flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {isSubmitting ? (
              <span className="animate-spin material-symbols-outlined text-[16px]">progress_activity</span>
            ) : (
              <span className="material-symbols-outlined text-[16px]">login</span>
            )}
            Authenticate Session
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-white/[0.06] text-center">
          <p className="text-[11px] text-faint font-mono">
            RESTRICTED GOVERNMENT & DISASTER OPERATIONAL TERMINAL
          </p>
        </div>
      </div>
    </div>
  );
};
