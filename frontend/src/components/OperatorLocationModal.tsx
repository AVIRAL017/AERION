import React, { useState } from 'react';
import { LocationProvenance } from '../types';
import { externalApi } from '../api';

interface OperatorLocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmLocation: (location: LocationProvenance) => void;
  existingLocation?: LocationProvenance | null;
}

type TabMode = 'MANUAL' | 'SEARCH' | 'MAP';

export const OperatorLocationModal: React.FC<OperatorLocationModalProps> = ({
  isOpen,
  onClose,
  onConfirmLocation,
  existingLocation,
}) => {
  const [activeTab, setActiveTab] = useState<TabMode>('MANUAL');
  
  // Coordinates & Label
  const [latStr, setLatStr] = useState<string>(existingLocation?.latitude ? String(existingLocation.latitude) : '');
  const [lonStr, setLonStr] = useState<string>(existingLocation?.longitude ? String(existingLocation.longitude) : '');
  const [label, setLabel] = useState<string>(existingLocation?.label || '');
  const [locationMethod, setLocationMethod] = useState<'MANUAL_COORDINATES' | 'PLACE_SEARCH' | 'MAP_SELECTION'>('MANUAL_COORDINATES');
  
  // Place Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Map Selection State (Interactive pin placement with Pan & Zoom)
  const [selectedMapPin, setSelectedMapPin] = useState<{ x: number; y: number; lat: number; lon: number; name: string } | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hasMovedDuringDrag, setHasMovedDuringDrag] = useState<boolean>(false);

  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  // Preset operational reference sectors
  const presets = [
    { label: 'Western Desert Sector (Rajasthan)', lat: 26.9124, lon: 70.9022 },
    { label: 'Northern Perimeter (Jammu)', lat: 32.7266, lon: 74.8570 },
    { label: 'Eastern Riverine Sector (Assam/Dhubri)', lat: 26.0207, lon: 89.9744 },
    { label: 'Disaster Zone (Chamoli / Joshimath)', lat: 30.5574, lon: 79.5670 },
  ];

  // Map reference sectors with normalized canvas coordinates
  const mapSectors = [
    { name: 'Northern Perimeter (Jammu)', lat: 32.7266, lon: 74.8570, x: 28, y: 18 },
    { name: 'Western Desert (Rajasthan)', lat: 26.9124, lon: 70.9022, x: 20, y: 40 },
    { name: 'Central Sector (Delhi NCR)', lat: 28.6139, lon: 77.2090, x: 38, y: 35 },
    { name: 'Eastern Riverine (Assam/Dhubri)', lat: 26.0207, lon: 89.9744, x: 82, y: 38 },
    { name: 'Himalayan Ridge (Chamoli)', lat: 30.5574, lon: 79.5670, x: 44, y: 26 },
  ];

  const handleApplyPreset = (p: typeof presets[0]) => {
    setLatStr(String(p.lat));
    setLonStr(String(p.lon));
    setLabel(p.label);
    setLocationMethod('MANUAL_COORDINATES');
    setError(null);
  };

  const handleSearchPlaces = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      const res = await externalApi.forwardGeocode(searchQuery.trim(), 5);
      // Backend returns ResponseEnvelope[List[NormalizedGeocodeResult]], so res.data is directly the array
      const resultsArray = Array.isArray(res.data)
        ? res.data
        : (res.data && Array.isArray(res.data.results) ? res.data.results : []);

      if (res.success && resultsArray.length > 0) {
        setSearchResults(resultsArray);
      } else {
        setSearchResults([]);
        setSearchError('No matching geographic places found. Try another place name.');
      }
    } catch {
      setSearchError('Geocoding service unavailable. Please enter coordinates manually.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectSearchResult = (result: any) => {
    setLatStr(String(result.latitude));
    setLonStr(String(result.longitude));
    setLabel(result.display_name || result.name || searchQuery);
    setLocationMethod('PLACE_SEARCH');
    setError(null);
  };

  const handleZoomIn = () => setZoomLevel((z) => Math.min(3.0, Number((z + 0.25).toFixed(2))));
  const handleZoomOut = () => setZoomLevel((z) => Math.max(1.0, Number((z - 0.25).toFixed(2))));
  const handleResetZoom = () => {
    setZoomLevel(1.0);
    setPanOffset({ x: 0, y: 0 });
  };

  const handleClearMapPin = () => {
    setSelectedMapPin(null);
    setLatStr('');
    setLonStr('');
    setLabel('');
    setError(null);
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsPanning(true);
    setHasMovedDuringDrag(false);
    setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isPanning) return;
    setHasMovedDuringDrag(true);
    setPanOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleMapCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // If user dragged more than a click threshold, ignore click
    if (hasMovedDuringDrag) {
      setHasMovedDuringDrag(false);
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left - panOffset.x;
    const clickY = e.clientY - rect.top - panOffset.y;
    
    // Scale normalized by zoom
    const effectiveWidth = rect.width * zoomLevel;
    const effectiveHeight = rect.height * zoomLevel;

    const percentX = Math.max(0, Math.min(100, (clickX / effectiveWidth) * 100));
    const percentY = Math.max(0, Math.min(100, (clickY / effectiveHeight) * 100));

    // Approximate linear interpolation across Northern/Western India bounding box:
    // Lon range: approx 68°E (left) to 92°E (right)
    // Lat range: approx 36°N (top) to 20°N (bottom)
    const interpLon = Number((68.0 + (percentX / 100) * (92.0 - 68.0)).toFixed(4));
    const interpLat = Number((36.0 - (percentY / 100) * (36.0 - 20.0)).toFixed(4));

    setSelectedMapPin({
      x: percentX,
      y: percentY,
      lat: interpLat,
      lon: interpLon,
      name: `Map Pin [${interpLat.toFixed(2)}°N, ${interpLon.toFixed(2)}°E]`,
    });
    setLatStr(String(interpLat));
    setLonStr(String(interpLon));
    setLabel(`Selected Map Point [${interpLat}, ${interpLon}]`);
    setLocationMethod('MAP_SELECTION');
    setError(null);
  };

  const handleConfirm = () => {
    setError(null);
    const lat = parseFloat(latStr.trim());
    const lon = parseFloat(lonStr.trim());

    if (isNaN(lat) || isNaN(lon)) {
      setError('Latitude and longitude must be valid numerical values.');
      return;
    }

    if (lat < -90 || lat > 90) {
      setError('Latitude must be between -90.0 and +90.0 degrees.');
      return;
    }

    if (lon < -180 || lon > 180) {
      setError('Longitude must be between -180.0 and +180.0 degrees.');
      return;
    }

    const locRecord: LocationProvenance = {
      latitude: lat,
      longitude: lon,
      location_source: 'OPERATOR_PROVIDED',
      location_precision: 'APPROXIMATE',
      location_method: locationMethod,
      label: label.trim() || `Coordinates [${lat.toFixed(4)}, ${lon.toFixed(4)}]`,
      confirmed_at_utc: new Date().toISOString(),
    };

    onConfirmLocation(locRecord);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono">
      <div className="w-full max-w-xl bg-panel border border-white/[0.12] rounded-lg shadow-2xl overflow-hidden flex flex-col text-xs">
        {/* Header */}
        <div className="h-12 px-5 flex items-center justify-between border-b border-white/[0.08] bg-[#0B0F14]">
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-accent text-[20px]">pin_drop</span>
            <span className="text-paper font-medium tracking-wider uppercase text-sm">
              OPERATOR APPROXIMATE LOCATION
            </span>
          </div>
          <button onClick={onClose} className="text-muted hover:text-paper transition-colors">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-white/[0.08] bg-[#0E131A] px-4 pt-2 gap-2">
          <button
            onClick={() => setActiveTab('MANUAL')}
            className={`pb-2 px-3 text-[11px] font-mono uppercase tracking-wider transition-all flex items-center gap-1.5 border-b-2 ${
              activeTab === 'MANUAL'
                ? 'border-accent text-accent font-bold'
                : 'border-transparent text-muted hover:text-paper'
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">edit</span>
            <span>MANUAL COORDINATES</span>
          </button>

          <button
            onClick={() => setActiveTab('SEARCH')}
            className={`pb-2 px-3 text-[11px] font-mono uppercase tracking-wider transition-all flex items-center gap-1.5 border-b-2 ${
              activeTab === 'SEARCH'
                ? 'border-accent text-accent font-bold'
                : 'border-transparent text-muted hover:text-paper'
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">search</span>
            <span>PLACE SEARCH</span>
          </button>

          <button
            onClick={() => setActiveTab('MAP')}
            className={`pb-2 px-3 text-[11px] font-mono uppercase tracking-wider transition-all flex items-center gap-1.5 border-b-2 ${
              activeTab === 'MAP'
                ? 'border-accent text-accent font-bold'
                : 'border-transparent text-muted hover:text-paper'
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">map</span>
            <span>SELECT ON MAP</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
          <div className="p-3 bg-accent/5 border border-accent/20 rounded text-paper text-[11px] leading-relaxed">
            <div className="flex items-center gap-1.5 text-accent font-bold mb-1 uppercase tracking-wide">
              <span className="material-symbols-outlined text-[15px]">info</span>
              <span>EVIDENCE PROVENANCE GUARANTEE</span>
            </div>
            This asset lacks embedded GPS. You may supply approximate coordinates to unlock real meteorological observations and geospatial boundary resolution.
            <strong className="block text-accent mt-1">
              PROVENANCE IS STRICTLY RECORDED AS &quot;OPERATOR_PROVIDED (APPROXIMATE)&quot; VIA {locationMethod}. NEVER FALSELY CLAIMED AS ASSET SENSOR GPS.
            </strong>
          </div>

          {/* TAB 1: MANUAL COORDINATES */}
          {activeTab === 'MANUAL' && (
            <div className="space-y-4">
              <div>
                <span className="text-[10px] text-muted uppercase tracking-wider block mb-2">
                  OPERATIONAL REFERENCE PRESETS
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {presets.map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleApplyPreset(p)}
                      className="p-2 text-left bg-elevated/40 hover:bg-accent/15 border border-white/[0.06] hover:border-accent/40 rounded transition-all group"
                    >
                      <span className="text-paper group-hover:text-accent font-medium block truncate text-[11px]">
                        {p.label}
                      </span>
                      <span className="text-faint text-[9px] block">
                        {p.lat.toFixed(4)}, {p.lon.toFixed(4)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: PLACE SEARCH */}
          {activeTab === 'SEARCH' && (
            <div className="space-y-3">
              <div>
                <label className="block text-[10px] text-muted uppercase tracking-wider mb-1">
                  SEARCH PLACE, CITY, DISTRICT OR SECTOR
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSearchPlaces(); }}
                    placeholder="e.g. Firozpur, Punjab or Joshimath"
                    className="flex-1 h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper text-xs focus:outline-none focus:border-accent/50"
                  />
                  <button
                    type="button"
                    onClick={handleSearchPlaces}
                    disabled={isSearching}
                    className="px-4 h-9 bg-elevated hover:bg-accent/20 border border-white/[0.1] text-accent text-xs rounded transition-all flex items-center gap-1"
                  >
                    {isSearching ? (
                      <span className="material-symbols-outlined text-[15px] animate-spin">progress_activity</span>
                    ) : (
                      <span className="material-symbols-outlined text-[15px]">search</span>
                    )}
                    <span>SEARCH</span>
                  </button>
                </div>
              </div>

              {searchError && (
                <div className="p-2.5 bg-status-warning/10 border border-status-warning/25 rounded text-status-warning text-[11px]">
                  {searchError}
                </div>
              )}

              {searchResults.length > 0 && (
                <div className="space-y-1.5 max-h-40 overflow-y-auto custom-scrollbar">
                  <span className="text-[10px] text-muted uppercase tracking-wider block">
                    MATCHING GEOGRAPHIC LOCATIONS
                  </span>
                  {searchResults.map((r, i) => (
                    <div
                      key={i}
                      onClick={() => handleSelectSearchResult(r)}
                      className="p-2 rounded bg-elevated/30 border border-white/[0.06] hover:border-accent/50 hover:bg-accent/10 cursor-pointer transition-all flex items-center justify-between"
                    >
                      <div className="truncate pr-2">
                        <span className="text-paper text-[11px] font-medium block truncate">
                          {r.display_name || r.name}
                        </span>
                        <span className="text-faint text-[9px]">
                          LAT: {r.latitude.toFixed(4)}, LON: {r.longitude.toFixed(4)}
                        </span>
                      </div>
                      <span className="px-1.5 py-0.5 rounded text-[9px] bg-accent/20 text-accent font-mono">
                        SELECT
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: SELECT ON MAP */}
          {activeTab === 'MAP' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted uppercase tracking-wider block">
                    PAN & ZOOM MAP SELECTION
                  </span>
                  <span className="px-1.5 py-0.2 rounded bg-elevated border border-white/[0.08] text-[9px] text-accent">
                    ZOOM: {zoomLevel.toFixed(2)}x
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={handleZoomIn}
                    className="w-6 h-6 rounded bg-elevated hover:bg-accent/20 border border-white/[0.1] text-paper flex items-center justify-center text-xs font-bold"
                    title="Zoom In"
                  >
                    +
                  </button>
                  <button
                    type="button"
                    onClick={handleZoomOut}
                    className="w-6 h-6 rounded bg-elevated hover:bg-accent/20 border border-white/[0.1] text-paper flex items-center justify-center text-xs font-bold"
                    title="Zoom Out"
                  >
                    -
                  </button>
                  <button
                    type="button"
                    onClick={handleResetZoom}
                    className="px-2 h-6 rounded bg-elevated hover:bg-accent/20 border border-white/[0.1] text-muted hover:text-paper text-[9px]"
                    title="Reset Zoom & Pan"
                  >
                    RESET
                  </button>
                  {selectedMapPin && (
                    <button
                      type="button"
                      onClick={handleClearMapPin}
                      className="px-2 h-6 rounded bg-status-critical/15 hover:bg-status-critical/30 border border-status-critical/30 text-status-critical text-[9px]"
                      title="Clear Selection Pin"
                    >
                      CLEAR PIN
                    </button>
                  )}
                </div>
              </div>

              <div
                onClick={handleMapCanvasClick}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                className="relative w-full h-56 bg-[#070A0E] border border-white/[0.12] rounded-lg overflow-hidden cursor-crosshair select-none telemetry-grid"
              >
                {/* Pan/Zoom Content Layer */}
                <div
                  className="w-full h-full relative transition-transform duration-75 origin-top-left"
                  style={{
                    transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                  }}
                >
                  {/* Sector reference anchors */}
                  {mapSectors.map((s, i) => (
                    <div
                      key={i}
                      onClick={(e) => {
                        e.stopPropagation();
                        setLatStr(String(s.lat));
                        setLonStr(String(s.lon));
                        setLabel(s.name);
                        setSelectedMapPin({ x: s.x, y: s.y, lat: s.lat, lon: s.lon, name: s.name });
                        setLocationMethod('MAP_SELECTION');
                        setError(null);
                      }}
                      className="absolute transform -translate-x-1/2 -translate-y-1/2 p-1 group z-10 cursor-pointer"
                      style={{ left: `${s.x}%`, top: `${s.y}%` }}
                      title={s.name}
                    >
                      <span className="w-2.5 h-2.5 rounded-full bg-accent/70 border border-white block group-hover:scale-125 transition-transform animate-pulse"></span>
                      <span className="absolute left-3 top-0 text-[8px] font-mono text-muted group-hover:text-accent whitespace-nowrap bg-black/80 px-1 rounded pointer-events-none">
                        {s.name}
                      </span>
                    </div>
                  ))}

                  {/* Operator active pin */}
                  {selectedMapPin && (
                    <div
                      className="absolute transform -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20"
                      style={{ left: `${selectedMapPin.x}%`, top: `${selectedMapPin.y}%` }}
                    >
                      <span className="material-symbols-outlined text-status-critical text-[24px] -mt-3 -ml-0.5 animate-bounce drop-shadow-md">
                        location_on
                      </span>
                    </div>
                  )}
                </div>

                {/* Bottom Overlay Info */}
                <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none">
                  <div className="bg-graphite/90 border border-white/[0.08] px-2 py-0.5 rounded text-[9px] text-faint">
                    DRAG TO PAN • CLICK TO PIN • SCROLL / +/- TO ZOOM
                  </div>
                  {selectedMapPin && (
                    <div className="bg-status-critical/15 border border-status-critical/30 px-2 py-0.5 rounded text-[9px] text-status-critical font-mono font-bold">
                      PIN: {selectedMapPin.lat.toFixed(4)}°N, {selectedMapPin.lon.toFixed(4)}°E
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Active Coordinate Inputs & Resolved Selection Preview */}
          <div className="space-y-3 pt-3 border-t border-white/[0.06]">
            <div>
              <label className="block text-[10px] text-muted uppercase tracking-wider mb-1">
                SECTOR / LOCATION LABEL
              </label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. Firozpur Border Sector Forward Post"
                className="w-full h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper text-xs focus:outline-none focus:border-accent/50"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] text-muted uppercase tracking-wider mb-1">
                  LATITUDE (-90.0 TO +90.0) *
                </label>
                <input
                  type="number"
                  step="any"
                  value={latStr}
                  onChange={(e) => {
                    setLatStr(e.target.value);
                    setLocationMethod('MANUAL_COORDINATES');
                  }}
                  placeholder="26.9124"
                  className="w-full h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper text-xs focus:outline-none focus:border-accent/50"
                />
              </div>

              <div>
                <label className="block text-[10px] text-muted uppercase tracking-wider mb-1">
                  LONGITUDE (-180.0 TO +180.0) *
                </label>
                <input
                  type="number"
                  step="any"
                  value={lonStr}
                  onChange={(e) => {
                    setLonStr(e.target.value);
                    setLocationMethod('MANUAL_COORDINATES');
                  }}
                  placeholder="70.9022"
                  className="w-full h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper text-xs focus:outline-none focus:border-accent/50"
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-status-critical/10 border border-status-critical/30 rounded text-status-critical text-[11px] flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">error</span>
              <span>{error}</span>
            </div>
          )}

          {/* Confirmation Provenance Badge */}
          <div className="p-3 bg-graphite/40 border border-white/[0.04] rounded grid grid-cols-3 gap-2 text-[10px] text-muted">
            <div>
              <span className="text-faint block text-[9px]">SOURCE:</span>
              <strong className="text-paper">OPERATOR-PROVIDED</strong>
            </div>
            <div>
              <span className="text-faint block text-[9px]">PRECISION:</span>
              <strong className="text-status-warning">APPROXIMATE</strong>
            </div>
            <div>
              <span className="text-faint block text-[9px]">METHOD:</span>
              <strong className="text-accent">{locationMethod}</strong>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="h-14 px-6 flex items-center justify-between border-t border-white/[0.08] bg-[#0B0F14]">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded border border-white/[0.1] text-muted hover:text-paper transition-all text-xs"
          >
            CANCEL
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            className="px-5 py-1.5 rounded bg-accent text-graphite font-bold tracking-wider hover:bg-accent/90 transition-all flex items-center gap-2 text-xs"
          >
            <span className="material-symbols-outlined text-[16px]">check_circle</span>
            <span>CONFIRM APPROXIMATE LOCATION</span>
          </button>
        </div>
      </div>
    </div>
  );
};
