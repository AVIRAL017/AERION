import React from 'react';
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  icon: string;
  label: string;
  shortLabel: string;
}

const navItems: NavItem[] = [
  { to: '/border', icon: 'radar', label: 'Border Surveillance', shortLabel: 'Border' },
  { to: '/disaster', icon: 'layers', label: 'Disaster Workspace', shortLabel: 'Disaster' },
  { to: '/image', icon: 'image_search', label: 'Image Perception', shortLabel: 'Perception' },
  { to: '/usage', icon: 'data_usage', label: 'Usage & Metering', shortLabel: 'Usage' },
  { to: '/status', icon: 'monitor_heart', label: 'System Readiness', shortLabel: 'Readiness' },
];

export const Sidebar: React.FC = () => {
  return (
    <>
      {/* Desktop Left Rail Navigation (hidden on mobile/tablet < md) */}
      <aside className="hidden md:flex w-16 flex-shrink-0 bg-white border-r border-border flex-col items-center py-5 justify-between z-40 shadow-2xs">
        {/* Upper Navigation Icons */}
        <div className="flex flex-col items-center gap-3.5 w-full">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.label}
              className={({ isActive }) =>
                `w-10 h-10 rounded-lg flex items-center justify-center transition-all relative group ${
                  isActive
                    ? 'bg-accent text-white border border-accent shadow-md shadow-accent/20'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100/80 border border-transparent'
                }`
              }
            >
              <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
              {/* Tooltip on hover */}
              <span className="absolute left-14 bg-slate-900 text-white text-[11px] font-mono px-2.5 py-1 rounded shadow-xl whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50">
                {item.label}
              </span>
            </NavLink>
          ))}
        </div>

        {/* Bottom System Health & Settings */}
        <div className="flex flex-col items-center gap-2 w-full">
          <NavLink
            to="/status"
            title="System Readiness & Diagnostic CLI"
            className={({ isActive }) =>
              `w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                isActive ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-800 hover:bg-slate-100'
              }`
            }
          >
            <span className="material-symbols-outlined text-[18px]">terminal</span>
          </NavLink>
          <NavLink
            to="/settings"
            title="Operator Settings & Security"
            className={({ isActive }) =>
              `w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                isActive ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-800 hover:bg-slate-100'
              }`
            }
          >
            <span className="material-symbols-outlined text-[18px]">settings</span>
          </NavLink>
        </div>
      </aside>

      {/* Mobile Bottom Navigation Bar (visible only on screens < md) */}
      <nav
        aria-label="Mobile Navigation"
        className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-white/95 border-t border-border backdrop-blur-md flex items-center justify-around px-2 z-50 shadow-lg"
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center py-1 px-2.5 rounded-md min-w-[52px] min-h-[44px] transition-all ${
                isActive
                  ? 'text-accent font-semibold'
                  : 'text-slate-500 hover:text-slate-900'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                <span className="text-[9px] font-mono tracking-tight mt-0.5">{item.shortLabel}</span>
                {isActive && <span className="w-1 h-1 rounded-full bg-accent mt-0.5"></span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </>
  );
};
