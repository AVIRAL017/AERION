import React from 'react';
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  icon: string;
  label: string;
  badge?: string;
}

const navItems: NavItem[] = [
  { to: '/image', icon: 'image_search', label: 'Image Perception' },
  { to: '/border', icon: 'radar', label: 'Border Surveillance' },
  { to: '/disaster', icon: 'layers', label: 'Disaster Workspace' },
  { to: '/usage', icon: 'data_usage', label: 'Usage & Metering' },
  { to: '/status', icon: 'monitor_heart', label: 'System Readiness' },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-16 flex-shrink-0 bg-graphite border-r border-white/[0.06] flex flex-col items-center py-5 justify-between z-40">
      {/* Upper Navigation Icons */}
      <div className="flex flex-col items-center gap-4 w-full">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={item.label}
            className={({ isActive }) =>
              `w-10 h-10 rounded-lg flex items-center justify-center transition-all relative group ${
                isActive
                  ? 'bg-accent/10 text-accent border border-accent/20'
                  : 'text-muted hover:text-paper hover:bg-elevated/60'
              }`
            }
          >
            <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
            {/* Tooltip on hover */}
            <span className="absolute left-14 bg-elevated border border-white/[0.08] text-[11px] font-mono text-paper px-2.5 py-1 rounded shadow-xl whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50">
              {item.label}
            </span>
          </NavLink>
        ))}
      </div>

      {/* Bottom Configuration / Help */}
      <div className="flex flex-col items-center gap-3 w-full">
        <NavLink
          to="/status"
          title="System Health"
          className={({ isActive }) =>
            `w-10 h-10 rounded-lg flex items-center justify-center text-muted hover:text-paper hover:bg-elevated/60 transition-colors ${
              isActive ? 'text-accent' : ''
            }`
          }
        >
          <span className="material-symbols-outlined text-[18px]">terminal</span>
        </NavLink>
      </div>
    </aside>
  );
};
