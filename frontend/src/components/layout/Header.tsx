import React, { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { systemApi } from '../../api';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [utcTime, setUtcTime] = useState<string>('');
  const [isHealthy, setIsHealthy] = useState<boolean>(true);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState<boolean>(false);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(
        now.toTimeString().split(' ')[0]
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await systemApi.getHealth();
        setIsHealthy(res.success && res.data?.status === 'healthy');
      } catch {
        setIsHealthy(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleConfirmLogout = () => {
    setShowLogoutConfirm(false);
    logout();
    navigate('/login');
  };

  return (
    <>
      <header className="flex items-center justify-between px-3 sm:px-6 w-full h-14 min-h-[56px] flex-shrink-0 z-50 bg-white/95 border-b border-border shadow-sm backdrop-blur-md">
        {/* Brand & Mode Switcher */}
        <div className="flex items-center gap-3 sm:gap-6 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-accent/10 border border-accent/25 shadow-sm">
              <span className="material-symbols-outlined text-accent text-[18px]">radar</span>
            </div>
            <span className="font-bold text-sm tracking-wider uppercase text-slate-900 font-sans">AERION</span>
            <span className="font-mono text-[10px] text-slate-500 font-medium tracking-widest px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">
              4.2
            </span>
          </div>

          {/* Clean Desktop Mode Switcher */}
          <nav className="hidden md:flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider whitespace-nowrap">
            <NavLink
              to="/border"
              className={({ isActive }) =>
                isActive
                  ? 'text-accent font-semibold bg-accent-light/60 px-3 py-1.5 rounded-md border border-accent/20 flex items-center gap-1.5 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-3 py-1.5 rounded-md transition-colors'
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-accent' : 'bg-transparent'}`}></span>
                  Border Surveillance
                </>
              )}
            </NavLink>

            <NavLink
              to="/disaster"
              className={({ isActive }) =>
                isActive
                  ? 'text-accent font-semibold bg-accent-light/60 px-3 py-1.5 rounded-md border border-accent/20 flex items-center gap-1.5 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-3 py-1.5 rounded-md transition-colors'
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-accent' : 'bg-transparent'}`}></span>
                  Disaster Workspace
                </>
              )}
            </NavLink>

            <NavLink
              to="/image"
              className={({ isActive }) =>
                isActive
                  ? 'text-accent font-semibold bg-accent-light/60 px-3 py-1.5 rounded-md border border-accent/20 flex items-center gap-1.5 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-3 py-1.5 rounded-md transition-colors'
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-accent' : 'bg-transparent'}`}></span>
                  Image Perception
                </>
              )}
            </NavLink>

            <NavLink
              to="/account"
              className={({ isActive }) =>
                isActive
                  ? 'text-accent font-semibold bg-accent-light/60 px-3 py-1.5 rounded-md border border-accent/20 flex items-center gap-1.5 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-3 py-1.5 rounded-md transition-colors'
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-accent' : 'bg-transparent'}`}></span>
                  Operator Hub
                </>
              )}
            </NavLink>
          </nav>
        </div>

        {/* Center Search Input */}
        <div className="hidden xl:flex items-center bg-slate-50 border border-slate-200 rounded-md px-3 py-1.5 w-72 max-w-xs text-slate-600 focus-within:border-accent focus-within:bg-white focus-within:shadow-sm transition-all shrink min-w-0 mx-4">
          <span className="material-symbols-outlined text-[15px] mr-2 text-slate-400">search</span>
          <input
            className="bg-transparent text-[12px] text-slate-900 placeholder:text-slate-400 font-mono border-none p-0 focus:ring-0 w-full focus:outline-none"
            placeholder="Search coordinates, tracks, sectors..."
            type="text"
          />
          <span className="font-mono text-[10px] text-slate-500 bg-white border border-slate-200 px-1.5 py-0.5 rounded shadow-2xs">⌘K</span>
        </div>

        {/* Right: Operational Status, UTC Clock, Profile */}
        <div className="flex items-center gap-3 sm:gap-5 flex-shrink-0">
          <div className="flex items-center gap-1.5 text-[12px] text-slate-600 font-sans" title={isHealthy ? 'Operational' : 'Degraded'}>
            <span
              className={`w-2 h-2 rounded-full ${
                isHealthy ? 'bg-status-success' : 'bg-status-critical'
              }`}
            ></span>
            <span className="hidden sm:inline font-medium">{isHealthy ? 'Operational' : 'Degraded'}</span>
          </div>

          {/* UTC Time (hidden on mobile < sm) */}
          <div className="hidden sm:block font-mono text-[12px] text-slate-600 tracking-tight">
            {utcTime || '--:--:--'} <span className="text-slate-400 text-[10px]">UTC</span>
          </div>

          {/* User Profile */}
          <div className="flex items-center gap-2 sm:gap-3 pl-2 border-l border-slate-200">
            {user ? (
              <div className="flex items-center gap-2 sm:gap-3">
                <NavLink
                  to="/account"
                  className="flex items-center gap-2 hover:opacity-90 transition-opacity p-1 rounded-md hover:bg-slate-100"
                  title="View Operator Account & Settings"
                >
                  <div className="w-7 h-7 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center text-[11px] font-mono font-bold text-accent shadow-2xs overflow-hidden flex-shrink-0">
                    {user.avatar_url ? (
                      <img src={user.avatar_url} alt={user.display_name || 'Operator'} className="w-full h-full object-cover" />
                    ) : (
                      (user.display_name || user.email).substring(0, 2).toUpperCase()
                    )}
                  </div>
                  <div className="hidden md:flex flex-col text-left">
                    <span className="text-[12px] text-slate-900 leading-snug font-semibold">
                      {user.display_name || user.email.split('@')[0]}
                    </span>
                    <span className="text-[10px] text-slate-500 leading-none font-mono uppercase flex items-center gap-1">
                      {user.role} {user.auth_provider === 'google' && <span className="text-[9px] text-accent font-sans">• GOOGLE</span>}
                    </span>
                  </div>
                </NavLink>
                <button
                  onClick={() => setShowLogoutConfirm(true)}
                  title="Sign out"
                  className="p-1.5 rounded-md text-slate-500 hover:text-status-critical hover:bg-slate-100 transition-colors"
                >
                  <span className="material-symbols-outlined text-[17px]">logout</span>
                </button>
              </div>
            ) : (
              <NavLink
                to="/login"
                className="text-[12px] font-mono text-accent hover:underline flex items-center gap-1 font-semibold"
              >
                <span className="material-symbols-outlined text-[16px]">login</span>
                <span className="hidden xs:inline">Sign In</span>
              </NavLink>
            )}
          </div>
        </div>
      </header>

      {/* Logout Confirmation Dialog */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="logout-dialog-title"
            className="bg-white border border-slate-200 rounded-xl max-w-sm w-full p-6 space-y-4 shadow-floating font-mono text-xs"
          >
            <div className="flex items-center gap-3 text-status-warning">
              <span className="material-symbols-outlined text-[24px]">warning</span>
              <h3 id="logout-dialog-title" className="text-slate-900 font-bold text-sm uppercase">Confirm Sign Out</h3>
            </div>
            <p className="text-slate-600 text-[11px] leading-relaxed">
              Are you sure you want to end your operational command session? Any unsaved live tracking state will be terminated.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="px-3 py-1.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-mono transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmLogout}
                className="px-3 py-1.5 rounded bg-status-critical hover:bg-red-700 text-white font-mono shadow-sm transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
