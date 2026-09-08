import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export const AppLayout: React.FC = () => {
  return (
    <div className="bg-graphite text-paper antialiased overflow-hidden select-none h-screen w-screen flex flex-col font-sans text-[13px] tracking-normal">
      {/* Top Navigation */}
      <Header />

      {/* Main Viewport Shell */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex overflow-hidden relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
