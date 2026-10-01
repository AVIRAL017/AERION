import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export const AppLayout: React.FC = () => {
  const location = useLocation();

  return (
    <div className="bg-graphite text-paper antialiased overflow-hidden select-none h-screen w-screen flex flex-col font-sans text-[13px] tracking-normal">
      {/* Top Navigation Header */}
      <Header />

      {/* Main Viewport Shell */}
      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar />
        <main className="flex-1 flex overflow-hidden relative pb-14 md:pb-0 bg-graphite">
          <div key={location.pathname} className="flex-1 flex flex-col h-full w-full overflow-hidden page-transition-container">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

