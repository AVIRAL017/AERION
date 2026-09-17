import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import { LocationProvenance } from '../types';
import { externalApi } from '../api';

interface OperatorLocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmLocation: (location: LocationProvenance) => void;
  existingLocation?: LocationProvenance | null;
}

type TabMode = 'MANUAL' | 'SEARCH' | 'MAP';

// Custom AERION tactical pin icon using Leaflet divIcon to ensure no asset bundling issues
const createAerionPinIcon = () => {
  return L.divIcon({
    className: 'aerion-leaflet-pin',
    html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
      <div style="background:#EF4444;width:14px;height:14px;border-radius:50%;border:2px solid #FFFFFF;box-shadow:0 0 10px rgba(239,68,68,0.8);"></div>
      <div style="width:2px;height:10px;background:#EF4444;"></div>
    </div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 24],
  });
};

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

  // Real Geographic Map Selection State (BUG-010 Remediation)
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const [selectedMapCoords, setSelectedMapCoords] = useState<{ lat: number; lon: number } | null>(
    existingLocation?.latitude && existingLocation?.longitude
      ? { lat: existingLocation.latitude, lon: existingLocation.longitude }
      : null
  );
  const [mapError, setMapError] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  // Preset operational reference sectors (manual fallback coordinates)
  const presets = [
    { label: 'Western Desert Sector (Rajasthan)', lat: 26.9124, lon: 70.9022 },
    { label: 'Northern Perimeter (Jammu)', lat: 32.7266, lon: 74.8570 },
    { label: 'Eastern Riverine Sector (Assam/Dhubri)', lat: 26.0207, lon: 89.9744 },
    { label: 'Disaster Zone (Chamoli / Joshimath)', lat: 30.5574, lon: 79.5670 },
  ];

  // Initialize and tear down real Leaflet map when MAP tab is active
  useEffect(() => {
    if (!isOpen || activeTab !== 'MAP') {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markerRef.current = null;
      }
      return;
    }

    // Delay slightly to ensure container is fully rendered in DOM
    const timer = setTimeout(() => {
      if (!mapContainerRef.current) return;

      try {
        if (mapInstanceRef.current) {
          mapInstanceRef.current.remove();
          mapInstanceRef.current = null;
        }

        const initialLat = selectedMapCoords?.lat || (latStr ? parseFloat(latStr) : 28.6139);
        const initialLon = selectedMapCoords?.lon || (lonStr ? parseFloat(lonStr) : 77.2090);
        const centerLat = isNaN(initialLat) ? 28.6139 : initialLat;
        const centerLon = isNaN(initialLon) ? 77.2090 : initialLon;

        const map = L.map(mapContainerRef.current, {
          center: [centerLat, centerLon],
          zoom: selectedMapCoords ? 8 : 4,
          minZoom: 2,
          maxZoom: 18,
          attributionControl: true,
        });

        // Genuine geographic tile layer using OpenStreetMap
        const tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
        });

        tileLayer.on('tileerror', () => {
          setMapError('Map tile service degraded or offline. Geographic coordinate calculation remains operational.');
        });

        tileLayer.addTo(map);

        // If existing coordinates exist, place the initial pin
        if (selectedMapCoords && !isNaN(selectedMapCoords.lat) && !isNaN(selectedMapCoords.lon)) {
          markerRef.current = L.marker([selectedMapCoords.lat, selectedMapCoords.lon], {
            icon: createAerionPinIcon(),
          }).addTo(map);
        }

        // Genuine map click handler: coordinates derived strictly from real geographic projection
        map.on('click', (e: L.LeafletMouseEvent) => {
          const lat = Number(e.latlng.lat.toFixed(4));
          const lon = Number(e.latlng.lng.toFixed(4));

          setSelectedMapCoords({ lat, lon });
          setLatStr(String(lat));
          setLonStr(String(lon));
          setLabel(`Operator Map Selection [${lat}°N, ${lon}°E]`);
          setLocationMethod('MAP_SELECTION');
          setError(null);
          setMapError(null);

          // Update or place marker on the real geographic coordinate
          if (markerRef.current) {
            markerRef.current.setLatLng([lat, lon]);
          } else {
            markerRef.current = L.marker([lat, lon], {
              icon: createAerionPinIcon(),
            }).addTo(map);
          }
        });

        mapInstanceRef.current = map;
        map.invalidateSize();
      } catch (err: any) {
        setMapError('LOCATION SELECTION UNAVAILABLE: Failed to initialize map engine.');
      }
    }, 50);

    return () => {
      clearTimeout(timer);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markerRef.current = null;
      }
    };
  }, [isOpen, activeTab]);

  const handleApplyPreset = (p: typeof presets[0]) => {
    setLatStr(String(p.lat));
    setLonStr(String(p.lon));
    setLabel(p.label);
    setLocationMethod('MANUAL_COORDINATES');
    setSelectedMapCoords({ lat: p.lat, lon: p.lon });
    setError(null);
  };

  const handleSearchPlaces = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      const res = await externalApi.forwardGeocode(searchQuery.trim(), 5);
      const resultsArray = Array.isArray(res.data)
        ? res.data
        : (res.data && Array.isArray((res.data as any).results) ? (res.data as any).results : []);

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
    setSelectedMapCoords({ lat: result.latitude, lon: result.longitude });
    setError(null);
  };

  const handleClearMapPin = () => {
    setSelectedMapCoords(null);
    if (markerRef.current && mapInstanceRef.current) {
      mapInstanceRef.current.removeLayer(markerRef.current);
      markerRef.current = null;
    }
    setLatStr('');
    setLonStr('');
    setLabel('');
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono">
      <div className="w-full max-w-xl bg-panel border border-white/[0.12] rounded-xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="h-12 px-6 flex items-center justify-between border-b border-white/[0.08] bg-elevated/40">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-accent text-[20px]">pin_drop</span>
            <h2 className="text-sm font-semibold text-paper tracking-wider uppercase">
              OPERATOR GEOGRAPHIC CONTEXT
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-paper text-sm p-1 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Warning Banner */}
        <div className="px-6 py-2.5 bg-status-warning/10 border-b border-status-warning/20 flex items-start gap-2.5">
          <span className="material-symbols-outlined text-status-warning text-[18px] shrink-0 mt-0.5">
            warning
          </span>
          <p className="text-[11px] text-paper/90 leading-tight">
            <strong>OPERATOR SENSITIVITY NOTICE:</strong> Approximate geographic context enriches weather, routing, and seismic awareness. All AI object perception (YOLO/Siamese) runs strictly standalone without location dependencies.
          </p>
        </div>

        {/* Modal Tabs */}
        <div className="flex border-b border-white/[0.08] bg-[#070A0E] text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('MANUAL')}
            className={`flex-1 py-3 px-4 text-center font-medium transition-colors border-b-2 flex items-center justify-center gap-2 ${
              activeTab === 'MANUAL'
                ? 'border-accent text-accent bg-accent/5'
                : 'border-transparent text-muted hover:text-paper hover:bg-white/[0.02]'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">edit_location</span>
            <span>MANUAL COORDINATES</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('SEARCH')}
            className={`flex-1 py-3 px-4 text-center font-medium transition-colors border-b-2 flex items-center justify-center gap-2 ${
              activeTab === 'SEARCH'
                ? 'border-accent text-accent bg-accent/5'
                : 'border-transparent text-muted hover:text-paper hover:bg-white/[0.02]'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">search</span>
            <span>PLACE SEARCH</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('MAP')}
            className={`flex-1 py-3 px-4 text-center font-medium transition-colors border-b-2 flex items-center justify-center gap-2 ${
              activeTab === 'MAP'
                ? 'border-accent text-accent bg-accent/5'
                : 'border-transparent text-muted hover:text-paper hover:bg-white/[0.02]'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">map</span>
            <span>SELECT ON MAP</span>
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {/* TAB 1: MANUAL COORDINATES */}
          {activeTab === 'MANUAL' && (
            <div className="space-y-4">
              <div>
                <span className="text-[10px] text-muted uppercase tracking-wider block mb-2">
                  OPERATIONAL REFERENCE PRESETS (CLICK TO LOAD)
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {presets.map((p, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => handleApplyPreset(p)}
                      className="p-2.5 rounded bg-elevated/40 border border-white/[0.06] hover:border-accent/40 hover:bg-accent/5 text-left transition-all group"
                    >
                      <span className="text-paper text-[11px] font-medium block truncate group-hover:text-accent">
                        {p.label}
                      </span>
                      <span className="text-faint text-[9px] font-mono block mt-0.5">
                        {p.lat.toFixed(4)}°N, {p.lon.toFixed(4)}°E
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
                  SEARCH GEOGRAPHIC PLACE OR SECTOR
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearchPlaces()}
                    placeholder="e.g. Jaisalmer, Barmer, Dhubri, Joshimath"
                    className="flex-1 h-9 px-3 bg-graphite border border-white/[0.08] rounded text-paper text-xs focus:outline-none focus:border-accent/50"
                  />
                  <button
                    type="button"
                    onClick={handleSearchPlaces}
                    disabled={isSearching || !searchQuery.trim()}
                    className="px-4 h-9 rounded bg-accent/20 border border-accent/40 text-accent text-xs font-semibold hover:bg-accent/30 transition-all disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {isSearching ? (
                      <span className="animate-spin material-symbols-outlined text-[15px]">progress_activity</span>
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

          {/* TAB 3: SELECT ON MAP (BUG-010 Real Geographic Map Interaction) */}
          {activeTab === 'MAP' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted uppercase tracking-wider block">
                    GENUINE GEOGRAPHIC MAP (WGS-84 PROJECTION)
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {selectedMapCoords && (
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

              {mapError && (
                <div className="p-2 bg-status-warning/15 border border-status-warning/30 rounded text-status-warning text-[10px] flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[14px]">warning</span>
                  <span>{mapError}</span>
                </div>
              )}

              {/* Real Leaflet Map Container */}
              <div
                ref={mapContainerRef}
                className="relative w-full h-64 bg-[#070A0E] border border-white/[0.12] rounded-lg overflow-hidden cursor-crosshair select-none z-10"
                style={{ minHeight: '256px' }}
              />

              <div className="flex items-center justify-between text-[9px] text-faint px-1">
                <span>CLICK MAP TO PLACE TACTICAL PIN • SCROLL / DRAG TO PAN & ZOOM</span>
                <span className="text-muted">
                  {selectedMapCoords
                    ? `SELECTED: ${selectedMapCoords.lat.toFixed(4)}°N, ${selectedMapCoords.lon.toFixed(4)}°E`
                    : 'NO POINT SELECTED'}
                </span>
              </div>

              {/* Explicit Disclaimer: Not an Authoritative Border (Requirement D) */}
              <div className="p-2 bg-black/40 border border-white/[0.06] rounded text-[9px] text-muted/80 leading-normal">
                <strong>DISCLAIMER:</strong> Operator map clicks generate contextual geographic reference points for weather/routing enrichment only. Selected points do not represent authoritative international border demarcations, Survey of India perimeters, or certified boundary intelligence.
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
