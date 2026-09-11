import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { systemApi } from '../../api';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const [utcTime, setUtcTime] = useState<string>('');
  const [isHealthy, setIsHealthy] = useState<boolean>(true);

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

  return (
    <header className="flex items-center justify-between px-7 w-full h-15 flex-shrink-0 z-50 bg-[#0B0F14]/95 border-b border-white/[0.06] backdrop-blur-md">
      {/* Brand & Mode Switcher */}
      <div className="flex items-center gap-7">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded flex items-center justify-center bg-accent/10 border border-accent/20">
            <span className="material-symbols-outlined text-accent text-[17px]">radar</span>
          </div>
          <span className="font-semibold text-sm tracking-wider uppercase text-white font-sans">AERION</span>
          <span className="font-mono text-[10px] text-muted tracking-widest px-1.5 py-0.5 rounded bg-elevated/70 border border-white/[0.05]">
            4.2
          </span>
        </div>

        {/* Clean Mode Switcher */}
        <nav className="flex items-center gap-6 font-mono text-[11px] uppercase tracking-wider">
          <NavLink
            to="/border"
            className={({ isActive }) =>
              isActive
                ? "text-accent font-medium flex items-center gap-1.5 relative py-1 after:content-[''] after:absolute after:bottom-0 after:left-0 after:w-full after:h-[1.5px] after:bg-accent"
                : "text-muted hover:text-white transition-colors duration-150 py-1"
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span className="w-1.5 h-1.5 rounded-full bg-accent"></span>}
                Border Security
              </>
            )}
          </NavLink>

          <NavLink
            to="/disaster"
            className={({ isActive }) =>
              isActive
                ? "text-accent font-medium flex items-center gap-1.5 relative py-1 after:content-[''] after:absolute after:bottom-0 after:left-0 after:w-full after:h-[1.5px] after:bg-accent"
                : "text-muted hover:text-white transition-colors duration-150 py-1"
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span className="w-1.5 h-1.5 rounded-full bg-accent"></span>}
                Disaster Response
              </>
            )}
          </NavLink>
        </nav>
      </div>

      {/* Center Search Input */}
      <div className="hidden md:flex items-center bg-panel/70 border border-white/[0.06] rounded-md px-3 py-1.5 w-80 text-muted focus-within:border-accent/40 transition-colors">
        <span className="material-symbols-outlined text-[15px] mr-2 text-faint">search</span>
        <input
          className="bg-transparent text-[12px] text-paper placeholder:text-faint font-mono border-none p-0 focus:ring-0 w-full focus:outline-none"
          placeholder="Search coordinates, tracks, sectors..."
          type="text"
        />
        <span className="font-mono text-[10px] text-muted/50 bg-elevated px-1.5 py-0.5 rounded">⌘K</span>
      </div>

      {/* Right: Operational Status, UTC Clock, Profile */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 text-[12px] text-muted font-sans">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isHealthy ? 'bg-status-success animate-pulse' : 'bg-status-critical'
            }`}
          ></span>
          <span>{isHealthy ? 'Operational' : 'Degraded'}</span>
        </div>

        {/* UTC Time */}
        <div className="font-mono text-[12px] text-muted tracking-tight">
          {utcTime || '--:--:--'} <span className="text-muted/50 text-[10px]">UTC</span>
        </div>

        {/* User Profile */}
        <div className="flex items-center gap-3 pl-2 border-l border-white/[0.06]">
          {user ? (
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-full bg-elevated border border-white/[0.08] flex items-center justify-center text-[11px] font-mono text-accent">
                {(user.display_name || user.email).substring(0, 2).toUpperCase()}
              </div>
              <div className="flex flex-col text-left">
                <span className="text-[12px] text-paper leading-snug font-medium">
                  {user.display_name || user.email.split('@')[0]}
                </span>
                <span className="text-[10px] text-muted leading-none font-mono uppercase flex items-center gap-1">
                  {user.role} {user.auth_provider === 'google' && <span className="text-[9px] text-accent font-sans">• GOOGLE</span>}
                </span>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                className="ml-2 text-muted hover:text-status-critical transition-colors"
              >
                <span className="material-symbols-outlined text-[16px]">logout</span>
              </button>
            </div>
          ) : (
            <NavLink
              to="/login"
              className="text-[12px] font-mono text-accent hover:underline flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">login</span>
              Sign In
            </NavLink>
          )}
        </div>
      </div>
    </header>
  );
};
