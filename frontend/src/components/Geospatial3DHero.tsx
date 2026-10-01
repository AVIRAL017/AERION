import React, { useState, useRef, useEffect } from 'react';

export const Geospatial3DHero: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ x: 0, y: 0, normX: 0, normY: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current || reducedMotion) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const normX = x / (rect.width / 2);
    const normY = y / (rect.height / 2);
    setCoords({ x, y, normX, normY });
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setCoords({ x: 0, y: 0, normX: 0, normY: 0 });
  };

  const handleMouseEnter = () => {
    if (!reducedMotion) setIsHovered(true);
  };

  // Subtle rotation angles bounded between -8deg and +8deg (clamped to 0 if reduced motion)
  const rotX = reducedMotion ? 0 : -coords.normY * 7;
  const rotY = reducedMotion ? 0 : coords.normX * 8;
  const lightX = reducedMotion ? 50 : 50 + coords.normX * 25;
  const lightY = reducedMotion ? 50 : 50 + coords.normY * 25;

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="relative w-full h-full min-h-[500px] flex flex-col justify-between p-8 overflow-hidden select-none"
      style={{ perspective: '1100px' }}
    >
      {/* Dynamic Layered Lighting Aura */}
      <div
        className="absolute inset-0 pointer-events-none transition-all duration-300 ease-out"
        style={{
          background: `radial-gradient(circle at ${lightX}% ${lightY}%, rgba(2, 132, 199, 0.12) 0%, rgba(14, 165, 233, 0.05) 40%, transparent 70%)`,
        }}
      />

      {/* Top Telemetry Header */}
      <div className="relative z-20 flex items-center justify-between font-mono text-[11px] text-slate-500 border-b border-slate-200/80 pb-3">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-slate-800 font-bold tracking-wider">AERION SPATIAL AI CORE</span>
        </div>
        <div className="flex items-center gap-4 text-[10px]">
          <span>GRID: WGS84 EPSG:4326</span>
          <span className="hidden sm:inline">AZ: {(180 + rotY * 4).toFixed(1)}°</span>
          <span className="hidden sm:inline">EL: {(45 + rotX * 2).toFixed(1)}°</span>
        </div>
      </div>

      {/* 3D Interactive Spatial Coordinate Plane */}
      <div
        className="relative flex-1 flex items-center justify-center my-4"
        style={{
          transformStyle: 'preserve-3d',
          transform: `rotateX(${rotX}deg) rotateY(${rotY}deg)`,
          transition: isHovered ? 'transform 0.1s ease-out' : 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Layer 0: Concentric Tactical Orbital Rings (Base Plane) */}
        <div
          className="absolute w-72 h-72 sm:w-88 sm:h-88 rounded-full border border-sky-300/40 flex items-center justify-center"
          style={{
            transform: 'translateZ(0px)',
            boxShadow: '0 0 40px rgba(2, 132, 199, 0.08), inset 0 0 30px rgba(2, 132, 199, 0.04)',
          }}
        >
          {/* Inner Orbital Ring */}
          <div className="w-56 h-56 sm:w-68 sm:h-68 rounded-full border border-dashed border-sky-400/50 flex items-center justify-center animate-[spin_60s_linear_infinite] motion-reduce:animate-none">
            <div className="w-40 h-40 rounded-full border border-slate-300/60"></div>
          </div>

          {/* Coordinate Crosshairs */}
          <div className="absolute w-full h-px bg-gradient-to-r from-transparent via-sky-400/50 to-transparent"></div>
          <div className="absolute h-full w-px bg-gradient-to-b from-transparent via-sky-400/50 to-transparent"></div>
        </div>

        {/* Layer 1: Topological Contour Grid (Depth: 20px) */}
        <div
          className="absolute w-64 h-64 rounded-2xl border border-slate-200/90 bg-white/60 backdrop-blur-xs flex flex-col justify-between p-3.5"
          style={{
            transform: 'translateZ(20px)',
            boxShadow: '0 12px 28px -6px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(226, 232, 240, 0.8)',
          }}
        >
          <div className="flex justify-between items-center text-[9px] font-mono text-slate-500 font-semibold">
            <span>SECTOR 04-ALPHA</span>
            <span className="text-accent font-bold">RECON ACTIVE</span>
          </div>

          {/* Simulated Elevation Vector Waves */}
          <div className="space-y-1.5 opacity-70 my-auto">
            <div className="h-1 bg-gradient-to-r from-sky-400 to-indigo-500 rounded-full w-full"></div>
            <div className="h-1 bg-gradient-to-r from-sky-300 to-indigo-400 rounded-full w-4/5"></div>
            <div className="h-1 bg-gradient-to-r from-sky-400 to-sky-600 rounded-full w-11/12"></div>
            <div className="h-1 bg-gradient-to-r from-indigo-300 to-sky-400 rounded-full w-3/4"></div>
          </div>

          <div className="flex justify-between items-center text-[9px] font-mono text-slate-400">
            <span>FOV: 84.5° AGL</span>
            <span>ALT: 420M</span>
          </div>
        </div>

        {/* Layer 2: Floating Depth Telemetry Nodes (Depth: 45px - 70px) */}
        {/* Floating Node A: Drone Ingestion */}
        <div
          className="absolute -top-4 -left-6 sm:left-4 px-3 py-2 rounded-xl bg-white border border-slate-200/90 flex items-center gap-2"
          style={{
            transform: 'translateZ(55px)',
            boxShadow: '0 16px 32px -8px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(2, 132, 199, 0.15)',
          }}
        >
          <div className="w-6 h-6 rounded-lg bg-sky-100 flex items-center justify-center text-accent">
            <span className="material-symbols-outlined text-[14px]">flight</span>
          </div>
          <div className="font-mono">
            <span className="text-[10px] text-slate-800 font-bold block leading-none">VISDRONE YOLOv8</span>
            <span className="text-[8px] text-emerald-600 font-semibold">FROZEN WEIGHTS VERIFIED</span>
          </div>
        </div>

        {/* Floating Node B: Damage Siamese Model */}
        <div
          className="absolute -bottom-6 -right-4 sm:right-6 px-3 py-2 rounded-xl bg-white border border-slate-200/90 flex items-center gap-2"
          style={{
            transform: 'translateZ(65px)',
            boxShadow: '0 18px 36px -10px rgba(15, 23, 42, 0.14), 0 0 0 1px rgba(2, 132, 199, 0.2)',
          }}
        >
          <div className="w-6 h-6 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-600">
            <span className="material-symbols-outlined text-[14px]">layers</span>
          </div>
          <div className="font-mono">
            <span className="text-[10px] text-slate-800 font-bold block leading-none">SIAMESE RESNET-50</span>
            <span className="text-[8px] text-slate-500">BI-TEMPORAL SCENE ALIGNMENT</span>
          </div>
        </div>

        {/* Floating Node C: Coordinates Reticle */}
        <div
          className="absolute top-1/2 -right-10 hidden sm:flex px-2.5 py-1.5 rounded-lg bg-slate-900 text-white font-mono text-[9px] items-center gap-1.5"
          style={{
            transform: 'translateZ(40px)',
            boxShadow: '0 12px 24px -4px rgba(15, 23, 42, 0.25)',
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-ping"></span>
          <span>LAT 32.65°N LON 74.85°E</span>
        </div>
      </div>

      {/* Bottom Architectural Spec Footer */}
      <div className="relative z-20 pt-3 border-t border-slate-200/80 grid grid-cols-2 sm:grid-cols-4 gap-3 text-[10px] font-mono text-slate-500">
        <div>
          <span className="text-slate-400 block text-[9px]">INFERENCE ENGINE</span>
          <span className="text-slate-800 font-bold">TENSORRT / ONNX</span>
        </div>
        <div>
          <span className="text-slate-400 block text-[9px]">SPATIAL ENGINE</span>
          <span className="text-slate-800 font-bold">POSTGIS EPSG:4326</span>
        </div>
        <div>
          <span className="text-slate-400 block text-[9px]">ZERO-FABRICATION</span>
          <span className="text-emerald-700 font-bold">STRICTLY ENFORCED</span>
        </div>
        <div>
          <span className="text-slate-400 block text-[9px]">TENANT ISOLATION</span>
          <span className="text-accent font-bold">ORGANIZATION SCOPED</span>
        </div>
      </div>
    </div>
  );
};
