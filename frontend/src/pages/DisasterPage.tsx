import React, { useEffect, useState, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { situationsApi, analysisApi, externalApi, sheltersApi } from '../api';
import { DamageSummary, AERIONAnalysisResultData, Situation, LocationProvenance } from '../types';
import { UploadModal } from '../components/UploadModal';
import { OperatorLocationModal } from '../components/OperatorLocationModal';
import { AnalysisHistoryModal } from '../components/AnalysisHistoryModal';
import { downloadAuthenticatedArtifact } from '../utils/download';
import { API_BASE } from '../api/client';

// Custom Map Marker Icons for Leaflet
const createOriginIcon = () => {
  return L.divIcon({
    className: 'aerion-origin-pin',
    html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
      <div style="background:#EF4444;width:16px;height:16px;border-radius:50%;border:2px solid #FFFFFF;box-shadow:0 0 12px rgba(239,68,68,0.9);display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px;font-weight:bold;">!</div>
      <div style="width:2px;height:12px;background:#EF4444;"></div>
    </div>`,
    iconSize: [24, 28],
    iconAnchor: [12, 28],
  });
};

const createShelterIcon = (isSelected: boolean) => {
  const bg = isSelected ? '#38D5F5' : '#10B981';
  return L.divIcon({
    className: 'aerion-shelter-pin',
    html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
      <div style="background:${bg};width:14px;height:14px;border-radius:3px;border:2px solid #FFFFFF;box-shadow:0 0 10px ${bg};"></div>
      <div style="width:2px;height:10px;background:${bg};"></div>
    </div>`,
    iconSize: [20, 24],
    iconAnchor: [10, 24],
  });
};

export const DisasterPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sliderPosition, setSliderPosition] = useState<number>(50);
  const [situation, setSituation] = useState<Situation | null>(null);
  const [damage, setDamage] = useState<DamageSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState<boolean>(false);
  const [operatorLocation, setOperatorLocation] = useState<LocationProvenance | null>(null);
  const [weatherData, setWeatherData] = useState<any | null>(null);
  const [weatherLoading, setWeatherLoading] = useState<boolean>(false);
  const [activeAnalysisResult, setActiveAnalysisResult] = useState<AERIONAnalysisResultData | null>(null);
  const [customPreUrl, setCustomPreUrl] = useState<string | null>(null);
  const [customPostUrl, setCustomPostUrl] = useState<string | null>(null);
  const [showDamageOverlay, setShowDamageOverlay] = useState<boolean>(true);
  const [displayMode, setDisplayMode] = useState<'split' | 'side-by-side' | 'pre' | 'post' | 'damage'>('split');
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [isDownloadingReport, setIsDownloadingReport] = useState<boolean>(false);

  // Section 3: Inline Geo-Context Search State
  const [geoSearchQuery, setGeoSearchQuery] = useState<string>('');
  const [isGeoSearching, setIsGeoSearching] = useState<boolean>(false);
  const [geoSearchResults, setGeoSearchResults] = useState<any[]>([]);
  const [geoSearchError, setGeoSearchError] = useState<string | null>(null);

  // Section 4: Verified Shelters State
  const [searchRadiusKm, setSearchRadiusKm] = useState<number | null>(100);
  const [shelterCandidates, setShelterCandidates] = useState<any[]>([]);
  const [selectedShelter, setSelectedShelter] = useState<any | null>(null);
  const [sheltersLoading, setSheltersLoading] = useState<boolean>(false);
  const [shelterError, setShelterError] = useState<string | null>(null);

  // Section 5: Route to Shelter via OpenRouteService State
  const [routeData, setRouteData] = useState<any | null>(null);
  const [routeLoading, setRouteLoading] = useState<boolean>(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [activeGeoJson, setActiveGeoJson] = useState<any | null>(null);

  // Map Refs for Route Leaflet Map
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.GeoJSON | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Quick preset locations for rapid disaster incident selection
  const locationPresets = [
    { label: 'Chamoli / Joshimath', lat: 30.5574, lon: 79.5670 },
    { label: 'Kedarnath Valley', lat: 30.7352, lon: 79.0669 },
    { label: 'Uttarkashi', lat: 30.7268, lon: 78.4354 },
    { label: 'Wayanad Sector', lat: 11.6854, lon: 76.1320 },
    { label: 'Silchar Riverine', lat: 24.8333, lon: 92.7789 },
    { label: 'New Delhi (HQ)', lat: 28.6139, lon: 77.2090 },
  ];

  // Initial Load: Fetch active situation
  useEffect(() => {
    const fetchDisasterData = async () => {
      setIsLoading(true);
      try {
        const listRes = await situationsApi.list();
        if (listRes.success && listRes.data && listRes.data.length > 0) {
          const active = listRes.data.find(s => s.situation_type === 'DISASTER_RESPONSE') || listRes.data[0];
          setSituation(active);
          if (active.damage) {
            setDamage(active.damage);
          }
          if (active.latitude && active.longitude && !operatorLocation) {
            setOperatorLocation({
              latitude: active.latitude,
              longitude: active.longitude,
              label: active.location_name || 'Active Disaster Zone',
              location_source: 'OPERATOR_PROVIDED',
              location_precision: 'APPROXIMATE',
              location_method: 'MANUAL_COORDINATES',
            });
          }
        }
      } catch {
        // Fallback state
      } finally {
        setIsLoading(false);
      }
    };
    fetchDisasterData();
  }, []);

  // Restore analysis from URL search parameter (e.g. ?analysis_id=UUID)
  useEffect(() => {
    const analysisIdParam = searchParams.get('analysis_id');
    if (!analysisIdParam) return;

    const restoreAnalysis = async () => {
      try {
        const resp = await analysisApi.getById(analysisIdParam);
        if (resp.success && resp.data) {
          const data = resp.data;
          setActiveAnalysisResult(data);
          const isRejected = Boolean(
            (data.pair_validation && data.pair_validation.is_compatible === false) ||
            data.status === 'PAIR_MISMATCH' ||
            data.overall_status === 'PAIR_VALIDATION_FAILED'
          );
          if (isRejected) {
            setDamage(null);
          } else {
            if (data.location_context && !operatorLocation) {
              setOperatorLocation(data.location_context);
            }
            if (data.damage_analysis) {
              const dmg = data.damage_analysis;
              const percentage = dmg.damage_percentage || (dmg.damage_ratio ? dmg.damage_ratio * 100 : 0);
              let classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC' = 'NO_DAMAGE';
              if (percentage >= 50) classification = 'CATASTROPHIC';
              else if (percentage >= 25) classification = 'SEVERE';
              else if (percentage >= 10) classification = 'MODERATE';
              else if (percentage > 0) classification = 'MINOR';

              setDamage({
                damage_percentage: percentage,
                damaged_pixels: dmg.damage_pixels || 0,
                total_pixels: dmg.total_pixels || 0,
                mean_damage_probability: dmg.probability_mean || 0,
                classification,
              });
            }
          }
        }
      } catch (err) {
        console.warn(`Could not restore disaster analysis ${analysisIdParam}:`, err);
      }
    };

    restoreAnalysis();
  }, [searchParams]);

  // Fetch live weather when valid operator location is provided
  useEffect(() => {
    if (!operatorLocation || typeof operatorLocation.latitude !== 'number' || typeof operatorLocation.longitude !== 'number') {
      setWeatherData(null);
      return;
    }

    const fetchWeather = async () => {
      setWeatherLoading(true);
      try {
        const resp = await externalApi.getWeather(operatorLocation.latitude, operatorLocation.longitude);
        if (resp.success && resp.data) {
          setWeatherData(resp.data);
        } else {
          setWeatherData({ status: 'UNAVAILABLE' });
        }
      } catch {
        setWeatherData({ status: 'UNAVAILABLE' });
      } finally {
        setWeatherLoading(false);
      }
    };

    fetchWeather();
  }, [operatorLocation]);

  // Query real PostGIS shelters when operatorLocation or searchRadiusKm changes
  useEffect(() => {
    if (!operatorLocation || typeof operatorLocation.latitude !== 'number' || typeof operatorLocation.longitude !== 'number') {
      setShelterCandidates([]);
      setSelectedShelter(null);
      return;
    }

    const fetchShelters = async () => {
      setSheltersLoading(true);
      setShelterError(null);
      try {
        const params: any = {
          latitude: operatorLocation.latitude,
          longitude: operatorLocation.longitude,
        };
        if (searchRadiusKm !== null) {
          params.radius_km = searchRadiusKm;
        }
        const resp = await sheltersApi.list(params);
        const list = Array.isArray(resp.data)
          ? resp.data
          : (resp.data?.shelters || resp.shelters || []);

        setShelterCandidates(list);
        if (list.length > 0) {
          // Default select the nearest shelter
          setSelectedShelter(list[0]);
        } else {
          setSelectedShelter(null);
        }
      } catch (err: any) {
        setShelterError(err.message || 'Failed to query verified shelters from PostGIS.');
        setShelterCandidates([]);
        setSelectedShelter(null);
      } finally {
        setSheltersLoading(false);
      }
    };

    fetchShelters();
  }, [operatorLocation, searchRadiusKm]);

  // Calculate actual road route via OpenRouteService when location & selected shelter are ready
  useEffect(() => {
    if (!operatorLocation || !selectedShelter) {
      setRouteData(null);
      setActiveGeoJson(null);
      setRouteError(null);
      return;
    }

    const shelterLat = selectedShelter.latitude ?? selectedShelter.location?.latitude;
    const shelterLon = selectedShelter.longitude ?? selectedShelter.location?.longitude;

    if (typeof shelterLat !== 'number' || typeof shelterLon !== 'number') {
      setRouteData(null);
      setActiveGeoJson(null);
      return;
    }

    const fetchRoute = async () => {
      setRouteLoading(true);
      setRouteError(null);
      try {
        const resp = await externalApi.getRoute(
          operatorLocation.latitude,
          operatorLocation.longitude,
          shelterLat,
          shelterLon,
          'driving-car'
        );

        if (resp.success && resp.data && resp.data.status === 'AVAILABLE') {
          const rec = resp.data;
          setRouteData(rec);
          setActiveGeoJson(rec.geometry_geojson || null);
        } else {
          setRouteData(null);
          setActiveGeoJson(null);
          const warn = resp.data?.warnings?.[0] || 'Route unavailable — no valid route returned by routing provider.';
          setRouteError(warn);
        }
      } catch (err: any) {
        setRouteData(null);
        setActiveGeoJson(null);
        setRouteError(err.message || 'Route unavailable — routing query failed or provider offline.');
      } finally {
        setRouteLoading(false);
      }
    };

    fetchRoute();
  }, [operatorLocation, selectedShelter]);

  // Initialize and maintain inline Leaflet Route Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const initialLat = operatorLocation?.latitude || 28.6139;
      const initialLon = operatorLocation?.longitude || 77.2090;

      const map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLon],
        zoom: 7,
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '© OpenStreetMap contributors | AERION Real Road Routing',
      }).addTo(map);

      const markersGroup = L.layerGroup().addTo(map);
      markersLayerRef.current = markersGroup;
      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    // Clear existing markers and route polyline
    markersGroup.clearLayers();
    if (routeLayerRef.current) {
      map.removeLayer(routeLayerRef.current);
      routeLayerRef.current = null;
    }

    const bounds = L.latLngBounds([]);

    // 0. If no operator location is provided, visibly render the configured synthetic Demo AOI Polygon
    if (!operatorLocation || typeof operatorLocation.latitude !== 'number') {
      const demoLatLngs: [number, number][] = [
        [32.70, 74.80],
        [32.75, 74.90],
        [32.65, 74.95],
        [32.55, 74.88],
        [32.60, 74.78],
      ];
      const demoPoly = L.polygon(demoLatLngs, {
        color: '#F59E0B',
        weight: 2,
        dashArray: '6, 6',
        fillColor: '#F59E0B',
        fillOpacity: 0.18,
      }).addTo(markersGroup);

      demoPoly.bindPopup(
        `<div style="font-family:monospace;font-size:11px;">
          <b style="color:#F59E0B;">DEMO AOI (SYNTHETIC)</b><br/>
          <span style="color:#EF4444;font-size:9px;font-weight:bold;">NON-AUTHORITATIVE TEST BOUNDARY</span><br/>
          <span style="color:#64748B;font-size:9px;">Search or pick an incident site in Step 1 to anchor real operations.</span>
        </div>`
      );

      map.fitBounds(demoPoly.getBounds(), { padding: [35, 35] });
      return;
    }

    // 1. Plot Origin (Disaster Site)
    if (operatorLocation && typeof operatorLocation.latitude === 'number' && typeof operatorLocation.longitude === 'number') {
      const originLatLng: [number, number] = [operatorLocation.latitude, operatorLocation.longitude];
      L.marker(originLatLng, { icon: createOriginIcon() })
        .bindPopup(`<b>Disaster Incident Site</b><br/>${operatorLocation.label || 'Origin Coordinates'}`)
        .addTo(markersGroup);
      bounds.extend(originLatLng);
    }

    // 2. Plot Shelters
    shelterCandidates.forEach((s) => {
      const sLat = s.latitude ?? s.location?.latitude;
      const sLon = s.longitude ?? s.location?.longitude;
      if (typeof sLat === 'number' && typeof sLon === 'number') {
        const isSel = (selectedShelter?.id || selectedShelter?.shelter_id) === (s.id || s.shelter_id);
        const occ = s.capacity_occupied ?? s.current_occupancy ?? 0;
        const cap = s.capacity_total ?? s.capacity ?? 'N/A';
        const shelterMarker = L.marker([sLat, sLon], { icon: createShelterIcon(isSel) })
          .bindPopup(`<b>${s.name}</b><br/>${s.shelter_type || 'Shelter'}<br/>Capacity: ${occ}/${cap}`)
          .addTo(markersGroup);

        shelterMarker.on('click', () => {
          setSelectedShelter(s);
        });

        bounds.extend([sLat, sLon]);
      }
    });

    // 3. Render Real Road Polyline via GeoJSON
    if (activeGeoJson) {
      try {
        const geoLayer = L.geoJSON(activeGeoJson, {
          style: {
            color: '#38D5F5',
            weight: 4,
            opacity: 0.9,
          },
        }).addTo(map);
        routeLayerRef.current = geoLayer as any;
        map.fitBounds(geoLayer.getBounds(), { padding: [25, 25] });
      } catch (e) {
        console.warn('Could not parse route GeoJSON:', e);
      }
    } else if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
    }
  }, [operatorLocation, shelterCandidates, selectedShelter, activeGeoJson]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    setSliderPosition((x / rect.width) * 100);
  };

  const handleSearchPlaces = async () => {
    if (!geoSearchQuery.trim()) return;
    setIsGeoSearching(true);
    setGeoSearchError(null);
    try {
      const res = await externalApi.forwardGeocode(geoSearchQuery.trim(), 5);
      const resultsArray = Array.isArray(res.data)
        ? res.data
        : (res.data && Array.isArray((res.data as any).results) ? (res.data as any).results : []);

      if (res.success && resultsArray.length > 0) {
        setGeoSearchResults(resultsArray);
      } else {
        setGeoSearchResults([]);
        setGeoSearchError('No matching places found. Try a city or district name.');
      }
    } catch {
      setGeoSearchError('Geocoding service unavailable.');
    } finally {
      setIsGeoSearching(false);
    }
  };

  const handleSelectPlace = (place: any) => {
    setOperatorLocation({
      latitude: Number(place.latitude),
      longitude: Number(place.longitude),
      label: place.display_name || place.locality || geoSearchQuery,
      location_source: 'OPERATOR_PROVIDED',
      location_precision: 'APPROXIMATE',
      location_method: 'PLACE_SEARCH',
    });
    setGeoSearchResults([]);
    setGeoSearchQuery('');
    setGeoSearchError(null);
  };

  const handleApplyPreset = (p: typeof locationPresets[0]) => {
    setOperatorLocation({
      latitude: p.lat,
      longitude: p.lon,
      label: p.label,
      location_source: 'OPERATOR_PROVIDED',
      location_precision: 'APPROXIMATE',
      location_method: 'MANUAL_COORDINATES',
    });
    setGeoSearchResults([]);
    setGeoSearchError(null);
  };

  const handleDownloadPdfReport = async () => {
    const sitId = situation?.id || '00000000-0000-0000-0000-000000000002';
    setIsDownloadingReport(true);
    try {
      const url = situationsApi.downloadReportUrl(
        sitId,
        'pdf',
        operatorLocation,
        activeAnalysisResult?.analysis_id,
        searchRadiusKm || undefined
      );
      await downloadAuthenticatedArtifact(
        url,
        `AERION_Disaster_Report_${activeAnalysisResult?.analysis_id ? activeAnalysisResult.analysis_id.substring(0, 8) : 'sit'}.pdf`
      );
    } catch (e: any) {
      alert(e.message || 'Report download failed');
    } finally {
      setIsDownloadingReport(false);
    }
  };

  // Safety invariant: Check if current bi-temporal pair was rejected by canonical validator
  const isPairRejected = Boolean(
    (activeAnalysisResult?.pair_validation && activeAnalysisResult.pair_validation.is_compatible === false) ||
    activeAnalysisResult?.status === 'PAIR_MISMATCH' ||
    activeAnalysisResult?.overall_status === 'PAIR_VALIDATION_FAILED'
  );

  // Step 4: Calculate evidence-backed risk score from verified inputs
  const getRiskAssessment = () => {
    const hasCoords = Boolean(operatorLocation && typeof operatorLocation.latitude === 'number');
    const hasWeather = Boolean(weatherData && weatherData.status !== 'UNAVAILABLE' && (typeof weatherData.temperature_c === 'number' || typeof weatherData.temperature_celsius === 'number'));
    const hasDamage = Boolean((activeAnalysisResult?.damage_analysis && typeof activeAnalysisResult.damage_analysis.damage_percentage === 'number') || (damage && typeof damage.damage_percentage === 'number'));
    const currentDmgPct = activeAnalysisResult?.damage_analysis?.damage_percentage ?? damage?.damage_percentage ?? 0;

    // Safety Invariant: Incompatible bi-temporal pairs NEVER generate operational risk
    if (isPairRejected) {
      return {
        status: 'NOT_AVAILABLE',
        mode: 'REJECTED_PAIR',
        score: null,
        level: 'UNAVAILABLE',
        title: 'RISK: NOT AVAILABLE — DAMAGE PAIR INVALID',
        badge: 'PAIR VALIDATION FAILED',
        inputs: {
          coordinates: hasCoords,
          weather: hasWeather,
          damage: false,
        },
        reason: 'Bi-temporal damage pair failed scene compatibility validation. Operational risk score cannot be calculated for an invalid pair.',
      };
    }

    // CASE A: User Incident Location Provided
    if (hasCoords) {
      if (!hasDamage) {
        return {
          status: 'INSUFFICIENT_EVIDENCE',
          mode: 'REAL_LOCATION',
          score: null,
          level: 'UNAVAILABLE',
          title: 'RISK: INSUFFICIENT EVIDENCE / UNAVAILABLE',
          badge: 'UNAVAILABLE',
          inputs: {
            coordinates: true,
            weather: hasWeather,
            damage: false,
          },
          reason: 'Incident location verified. Requires AI-verified damage perception metrics from Step 3 to calculate operational risk.',
        };
      }

      const dmgFactor = Math.min(100, currentDmgPct);
      const windMps = weatherData?.wind_speed_mps || 0;
      const precipMm = weatherData?.precipitation_mm_hr || 0;
      const weatherSeverity = Math.min(100, windMps * 3.5 + precipMm * 5.0);
      const contextVulnerability = 20.0;

      const compositeScore = (dmgFactor * 0.60) + (weatherSeverity * 0.25) + (contextVulnerability * 0.15);
      const roundedScore = Math.round(compositeScore * 10) / 10;

      let level = 'LOW';
      if (roundedScore >= 70) level = 'CRITICAL';
      else if (roundedScore >= 45) level = 'HIGH';
      else if (roundedScore >= 25) level = 'MODERATE';

      return {
        status: 'CALCULATED',
        mode: 'REAL_LOCATION',
        score: roundedScore,
        level,
        title: 'REAL LOCATION RISK',
        badge: 'EVIDENCE-BACKED',
        inputs: {
          coordinates: true,
          weather: hasWeather,
          damage: true,
        },
        formula: '60% Damage Perception + 25% Meteorological Severity + 15% Terrain Baseline',
      };
    }

    // CASE B: No User Location (Synthetic Demo AOI Active)
    if (!hasDamage) {
      return {
        status: 'INSUFFICIENT_EVIDENCE',
        mode: 'DEMO_CONTEXT',
        score: null,
        level: 'UNAVAILABLE',
        title: 'INSUFFICIENT EVIDENCE / DEMO CONTEXT ONLY',
        badge: 'DEMO CONTEXT ONLY',
        inputs: {
          coordinates: false,
          weather: false,
          damage: false,
        },
        reason: 'No user location designated (synthetic Demo AOI active) and AI damage perception metrics are missing. Designate incident coordinates in Step 1 or upload damage pair in Step 3.',
      };
    }

    // Real damage metrics exist, but location is unanchored demo context
    const dmgFactor = Math.min(100, currentDmgPct);
    const demoWeatherSeverity = 15.0; // Baseline synthetic meteorology
    const demoContextVulnerability = 20.0;
    const compositeScore = (dmgFactor * 0.60) + (demoWeatherSeverity * 0.25) + (demoContextVulnerability * 0.15);
    const roundedScore = Math.round(compositeScore * 10) / 10;

    let level = 'LOW';
    if (roundedScore >= 70) level = 'CRITICAL';
    else if (roundedScore >= 45) level = 'HIGH';
    else if (roundedScore >= 25) level = 'MODERATE';

    return {
      status: 'DEMO_CONTEXT',
      mode: 'DEMO_CONTEXT',
      score: roundedScore,
      level,
      title: 'DEMO CONTEXT ASSESSMENT',
      badge: 'SYNTHETIC / NON-AUTHORITATIVE',
      inputs: {
        coordinates: false,
        weather: false,
        damage: true,
      },
      formula: '60% Real Damage Perception + 25% Demo Meteorological Baseline + 15% Terrain Baseline',
      disclaimer: 'SYNTHETIC / NON-AUTHORITATIVE: Calculated using synthetic Demo AOI baseline parameters. Not an authoritative ground assessment. Designate operational coordinates in Step 1 to ground real location risk.',
    };
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-graphite font-mono text-xs text-muted">
        <span className="material-symbols-outlined text-accent animate-spin mr-2">progress_activity</span>
        SYNCHRONIZING BI-TEMPORAL DISASTER WORKSPACE...
      </div>
    );
  }

  // Determine current pre/post image display
  const preImgUrl = customPreUrl || damage?.pre_image_url;
  const postImgUrl = customPostUrl || damage?.post_image_url;

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-graphite">
      {/* ============================================================ */}
      {/* 1. CENTRAL BI-TEMPORAL SPLIT-CURTAIN WORKSPACE                  */}
      {/* ============================================================ */}
      <section className="flex-1 relative flex flex-col border-r border-white/[0.06] overflow-hidden">
        {/* Workspace Toolbar */}
        <div className="h-11 px-5 flex items-center justify-between border-b border-white/[0.06] bg-panel/80 backdrop-blur z-20">
          <div className="flex items-center gap-3 font-mono text-[11px]">
            <span className="text-muted uppercase">MODE:</span>
            <span className="text-paper font-medium">DISASTER RESPONSE</span>
            <span className={`px-2 py-0.5 rounded text-[10px] ${
              isPairRejected
                ? 'bg-status-critical/15 text-status-critical border border-status-critical/30 font-bold'
                : activeAnalysisResult
                ? 'bg-status-success/15 text-status-success border border-status-success/30'
                : 'bg-accent/10 text-accent border border-accent/20'
            }`}>
              {isPairRejected ? 'PAIR REJECTED // INFERENCE HALTED' : activeAnalysisResult ? 'SIAMESE INFERENCE VERIFIED' : 'SIAMESE FUSED'}
            </span>

            {/* History Drawer Trigger */}
            <button
              onClick={() => setIsHistoryOpen(true)}
              className="px-2.5 py-1 rounded bg-elevated/80 border border-white/[0.1] text-muted hover:text-accent hover:border-accent/40 text-[10px] font-mono flex items-center gap-1 transition-all"
              title="View past analysis history and reopen analyses"
            >
              <span className="material-symbols-outlined text-[13px]">history</span>
              <span>HISTORY</span>
            </button>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px]">
            {/* View Mode Switcher */}
            {preImgUrl && postImgUrl && (
              <div className="flex items-center rounded bg-elevated/70 border border-white/[0.1] p-0.5">
                <button
                  onClick={() => setDisplayMode('split')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'split' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  SPLIT SLIDER
                </button>
                <button
                  onClick={() => setDisplayMode('side-by-side')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'side-by-side' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  SIDE-BY-SIDE
                </button>
                <button
                  onClick={() => setDisplayMode('pre')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'pre' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  PRE (T0)
                </button>
                <button
                  onClick={() => setDisplayMode('post')}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                    displayMode === 'post' ? 'bg-accent text-graphite font-bold shadow' : 'text-muted hover:text-paper'
                  }`}
                >
                  POST (T1)
                </button>
                {activeAnalysisResult?.damage_mask_base64 && (
                  <button
                    onClick={() => setDisplayMode('damage')}
                    className={`px-2 py-0.5 rounded text-[10px] transition-all cursor-pointer ${
                      displayMode === 'damage' ? 'bg-status-critical text-white font-bold shadow' : 'text-muted hover:text-paper'
                    }`}
                  >
                    DAMAGE MASK
                  </button>
                )}
              </div>
            )}

            {!isPairRejected && activeAnalysisResult?.damage_mask_base64 && (displayMode === 'split' || displayMode === 'side-by-side' || displayMode === 'post') && (
              <button
                onClick={() => setShowDamageOverlay(!showDamageOverlay)}
                className={`px-2.5 py-1 rounded border text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer ${
                  showDamageOverlay
                    ? 'bg-status-critical/20 border-status-critical text-status-critical'
                    : 'bg-elevated border-white/[0.1] text-muted hover:text-paper'
                }`}
              >
                <span className="material-symbols-outlined text-[13px]">layers</span>
                <span>OVERLAY: {showDamageOverlay ? 'ON' : 'OFF'}</span>
              </button>
            )}
            {displayMode === 'split' && (
              <span className="text-muted mr-2">SPLIT: {Math.round(sliderPosition)}%</span>
            )}
            <button
              onClick={() => setIsUploadOpen(true)}
              className="px-3 py-1 rounded bg-accent text-graphite font-bold text-[10px] hover:bg-accent/90 transition-all flex items-center gap-1.5 cursor-pointer shadow"
            >
              <span className="material-symbols-outlined text-[14px]">compare</span>
              <span>INGEST DAMAGE PAIR</span>
            </button>
          </div>
        </div>

        {/* Bi-Temporal Split View Canvas */}
        <div
          ref={containerRef}
          onMouseMove={displayMode === 'split' ? handleMouseMove : undefined}
          className={`flex-1 relative bg-[#07090C] telemetry-grid overflow-hidden select-none ${displayMode === 'split' ? 'cursor-ew-resize' : ''}`}
        >
          {preImgUrl && postImgUrl ? (
            <div className="relative w-full h-full">
              {displayMode === 'pre' && (
                <img
                  src={preImgUrl}
                  alt="Pre-Disaster Baseline"
                  className="w-full h-full object-cover"
                />
              )}

              {displayMode === 'post' && (
                <div className="relative w-full h-full">
                  <img
                    src={postImgUrl}
                    alt="Post-Disaster Observation"
                    className="w-full h-full object-cover"
                  />
                  {showDamageOverlay && !isPairRejected && activeAnalysisResult?.damage_mask_base64 && (
                    <img
                      src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                      alt="Translucent Damage Overlay"
                      className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-75 pointer-events-none"
                    />
                  )}
                </div>
              )}

              {displayMode === 'damage' && activeAnalysisResult?.damage_mask_base64 && (
                <img
                  src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                  alt="Siamese Damage Mask"
                  className="w-full h-full object-cover"
                />
              )}

              {displayMode === 'side-by-side' && (
                <div className="w-full h-full grid grid-cols-2 gap-2 p-2">
                  <div className="relative w-full h-full border border-white/[0.08] rounded overflow-hidden flex flex-col">
                    <div className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded bg-graphite/80 border border-white/[0.1] text-[9px] font-mono text-muted">
                      PRE-DISASTER (T0)
                    </div>
                    <img
                      src={preImgUrl}
                      alt="Pre-Disaster Baseline"
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <div className="relative w-full h-full border border-white/[0.08] rounded overflow-hidden flex flex-col">
                    <div className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded bg-graphite/80 border border-white/[0.1] text-[9px] font-mono text-accent">
                      POST-DISASTER (T1) {showDamageOverlay && activeAnalysisResult?.damage_mask_base64 ? '+ OVERLAY' : ''}
                    </div>
                    <img
                      src={postImgUrl}
                      alt="Post-Disaster Observation"
                      className="w-full h-full object-cover"
                    />
                    {showDamageOverlay && !isPairRejected && activeAnalysisResult?.damage_mask_base64 && (
                      <img
                        src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                        alt="Translucent Damage Overlay"
                        className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-75 pointer-events-none"
                      />
                    )}
                  </div>
                </div>
              )}

              {displayMode === 'split' && (
                <>
                  <div className="absolute inset-0 w-full h-full">
                    <img
                      src={postImgUrl}
                      alt="Post-Disaster Observation"
                      className="w-full h-full object-cover pointer-events-none"
                    />
                    {showDamageOverlay && !isPairRejected && activeAnalysisResult?.damage_mask_base64 && (
                      <img
                        src={`data:image/jpeg;base64,${activeAnalysisResult.damage_mask_base64}`}
                        alt="Translucent Damage Overlay"
                        className="absolute inset-0 w-full h-full object-cover mix-blend-screen opacity-75 pointer-events-none"
                      />
                    )}
                  </div>

                  <div
                    className="slider-curtain"
                    style={{ width: `${sliderPosition}%` }}
                  >
                    <img
                      src={preImgUrl}
                      alt="Pre-Disaster Baseline"
                      className="slider-inner object-cover"
                    />
                  </div>

                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-accent z-30 pointer-events-none shadow-[0_0_10px_#38D5F5]"
                    style={{ left: `${sliderPosition}%` }}
                  >
                    <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-graphite border-2 border-accent flex items-center justify-center text-accent text-[10px] font-mono">
                      ⇆
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-elevated/70 border border-white/[0.08] flex items-center justify-center text-faint mb-3">
                <span className="material-symbols-outlined text-[24px]">satellite_alt</span>
              </div>
              <h3 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
                DAMAGE ANALYSIS UNAVAILABLE
              </h3>
              <p className="text-[11px] text-faint mt-1 max-w-sm">
                Awaiting bi-temporal satellite pair (pre-disaster baseline + post-disaster scene).
              </p>
              <button
                onClick={() => setIsUploadOpen(true)}
                className="mt-4 px-3 py-1.5 rounded bg-accent/15 border border-accent/40 text-accent text-xs font-mono hover:bg-accent/25 transition-all flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-[15px]">compare</span>
                <span>INGEST DAMAGE PAIR</span>
              </button>
            </div>
          )}

          {/* Overlays & Evidence Download */}
          <div className="absolute bottom-4 left-4 z-20 pointer-events-none">
            <span className="px-2 py-1 rounded bg-graphite/80 border border-white/[0.08] text-[10px] font-mono text-muted">
              PRE-DISASTER BASELINE (T0)
            </span>
          </div>
          <div className="absolute bottom-4 right-4 z-20 flex items-center gap-2">
            <span className="px-2 py-1 rounded bg-graphite/80 border border-white/[0.08] text-[10px] font-mono text-accent">
              {showDamageOverlay && activeAnalysisResult?.damage_mask_base64
                ? 'POST-DISASTER WITH DAMAGE OVERLAY (T1)'
                : 'POST-DISASTER OBSERVATION (T1)'}
            </span>
            {activeAnalysisResult?.damage_artifact && (
              <button
                disabled={isDownloading}
                onClick={async () => {
                  const artKey = activeAnalysisResult.damage_artifact?.artifact_key;
                  if (!artKey) return;
                  setIsDownloading(true);
                  try {
                    await downloadAuthenticatedArtifact(
                      `${API_BASE}/evidence/${artKey}`,
                      `AERION_${activeAnalysisResult.analysis_id.substring(0, 8)}_damage_mask.jpg`
                    );
                  } catch (e: any) {
                    alert(e.message || 'Download failed');
                  } finally {
                    setIsDownloading(false);
                  }
                }}
                className="px-2 py-1 rounded bg-accent text-graphite hover:bg-accent/90 disabled:opacity-50 text-[10px] font-mono font-bold flex items-center gap-1 shadow transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">download</span>
                <span>{isDownloading ? 'DOWNLOADING...' : 'DOWNLOAD DAMAGE MASK'}</span>
              </button>
            )}
            {postImgUrl && (
              <a
                href={postImgUrl}
                download={`AERION_${activeAnalysisResult?.analysis_id?.substring(0, 8) || 'disaster'}_post_original.jpg`}
                className="px-2 py-1 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-[10px] font-mono flex items-center gap-1 shadow transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[12px]">download</span>
                <span>DOWNLOAD POST IMAGE</span>
              </a>
            )}
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 1–7. COMPREHENSIVE RIGHT INTELLIGENCE PANEL (7-STEP WORKFLOW) */}
      {/* ============================================================ */}
      <aside className="w-[440px] flex-shrink-0 bg-panel flex flex-col overflow-y-auto custom-scrollbar border-l border-white/[0.06]">
        {/* Panel Header */}
        <div className="p-4 border-b border-white/[0.06] bg-graphite/40">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-medium tracking-wider text-muted uppercase">
              DISASTER RESPONSE INTELLIGENCE
            </h2>
            <span className="text-[10px] font-mono text-accent">7-STEP LINEAR WORKFLOW</span>
          </div>
          <span className="text-[10px] text-faint font-mono block mt-1">
            LOCATION → ENVIRONMENT → DAMAGE → RISK → SHELTERS → ROUTE → REPORT
          </span>
        </div>

        {/* ------------------------------------------------------------ */}
        {/* STEP 1: INCIDENT / LOCATION                                  */}
        {/* ------------------------------------------------------------ */}
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
              1. INCIDENT / LOCATION
            </span>
            {operatorLocation ? (
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-status-ai/15 text-status-ai border border-status-ai/30 font-semibold">
                {operatorLocation.location_precision || 'APPROXIMATE'}
              </span>
            ) : (
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-status-warning/15 text-status-warning border border-status-warning/30 font-semibold">
                DEMO AOI ACTIVE
              </span>
            )}
          </div>

          {/* Search Input for Places */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={geoSearchQuery}
                  onChange={(e) => setGeoSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchPlaces()}
                  placeholder="Search city, district, or place..."
                  className="w-full px-2.5 py-1.5 bg-graphite border border-white/[0.1] rounded text-xs font-mono text-paper placeholder-faint focus:border-accent focus:outline-none"
                />
                {isGeoSearching && (
                  <span className="material-symbols-outlined text-[14px] text-accent animate-spin absolute right-2 top-2">
                    progress_activity
                  </span>
                )}
              </div>
              <button
                onClick={handleSearchPlaces}
                disabled={isGeoSearching || !geoSearchQuery.trim()}
                className="px-2.5 py-1.5 bg-accent text-graphite font-mono font-bold text-xs rounded hover:bg-accent/90 disabled:opacity-50 transition-all cursor-pointer"
              >
                FIND
              </button>
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="p-1.5 bg-elevated border border-white/[0.1] text-muted hover:text-accent hover:border-accent rounded transition-all cursor-pointer"
                title="Open Interactive Coordinate & Map Selection Modal"
              >
                <span className="material-symbols-outlined text-[16px]">map</span>
              </button>
            </div>

            {/* Geocode Search Results Dropdown */}
            {geoSearchResults.length > 0 && (
              <div className="p-1 bg-graphite border border-accent/40 rounded space-y-1 font-mono text-[11px] shadow-xl max-h-36 overflow-y-auto">
                {geoSearchResults.map((place, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectPlace(place)}
                    className="p-1.5 hover:bg-white/[0.08] rounded cursor-pointer transition-all flex items-start justify-between"
                  >
                    <span className="text-paper truncate mr-2">{place.display_name || place.locality}</span>
                    <span className="text-accent text-[9px] whitespace-nowrap">
                      [{Number(place.latitude).toFixed(2)}, {Number(place.longitude).toFixed(2)}]
                    </span>
                  </div>
                ))}
              </div>
            )}
            {geoSearchError && (
              <p className="text-[10px] font-mono text-status-warning">{geoSearchError}</p>
            )}

            {/* Curated Fallback Reference Presets */}
            <div className="flex flex-wrap gap-1 pt-1">
              <span className="text-[9px] font-mono text-faint self-center mr-1">PRESETS:</span>
              {locationPresets.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => handleApplyPreset(p)}
                  className="px-1.5 py-0.5 rounded bg-elevated/70 hover:bg-accent/15 border border-white/[0.08] hover:border-accent/40 text-[9px] font-mono text-muted hover:text-accent transition-all cursor-pointer"
                >
                  {p.label.split('/')[0].trim()}
                </button>
              ))}
            </div>
          </div>

          {/* Active Geo-Context Summary Card or Demo Notice */}
          {operatorLocation ? (
            <div className="p-2.5 bg-graphite/60 border border-status-ai/30 rounded font-mono text-[11px] space-y-1.5">
              <div className="flex items-center justify-between text-paper font-semibold">
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-status-ai text-[14px]">pin_drop</span>
                  <span className="truncate max-w-[240px]">{operatorLocation.label || 'Designated Incident Site'}</span>
                </span>
                <span className="text-accent text-[10px]">
                  {operatorLocation.latitude.toFixed(4)}°N, {operatorLocation.longitude.toFixed(4)}°E
                </span>
              </div>
              <div className="flex items-center justify-between text-[9px] text-faint">
                <span>METHOD: {operatorLocation.location_method || 'COORDINATE_INPUT'}</span>
                <span>SRC: {operatorLocation.location_source || 'OPERATOR_SPECIFIED'}</span>
              </div>
            </div>
          ) : (
            <div className="p-2.5 bg-status-warning/10 border border-status-warning/30 rounded font-mono text-[10px] space-y-1 text-status-warning">
              <div className="font-bold flex items-center gap-1">
                <span className="material-symbols-outlined text-[13px]">pentagon</span>
                <span>DEMO AOI (SYNTHETIC / NON-AUTHORITATIVE)</span>
              </div>
              <p className="text-faint text-[9px] leading-tight">
                No verified location designated. Displaying synthetic demonstration polygon on map. Search above or click presets to set verified operational incident coordinates.
              </p>
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------ */}
        {/* STEP 2: ENVIRONMENT (METEOROLOGICAL CONDITIONS)              */}
        {/* ------------------------------------------------------------ */}
        <div className="p-4 border-b border-white/[0.06] space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
              2. ENVIRONMENT (METEOROLOGY)
            </span>
            <span className="text-[9px] font-mono text-faint">OPEN-METEO WMO</span>
          </div>

          {weatherLoading ? (
            <div className="p-2 bg-graphite/40 rounded text-[10px] font-mono text-muted flex items-center gap-1.5">
              <span className="material-symbols-outlined text-accent animate-spin text-[13px]">progress_activity</span>
              <span>QUERYING OPEN-METEO WEATHER OBSERVATIONS...</span>
            </div>
          ) : operatorLocation && weatherData && weatherData.status !== 'UNAVAILABLE' ? (
            <div className="p-2.5 bg-graphite/40 border border-white/[0.06] rounded font-mono text-[10px] space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <span className="text-faint block text-[9px]">CONDITIONS:</span>
                  <span className="text-paper font-semibold">{weatherData.conditions || weatherData.condition_description || 'CLEAR'}</span>
                </div>
                <div>
                  <span className="text-faint block text-[9px]">TEMPERATURE:</span>
                  <span className="text-accent font-semibold">{weatherData.temperature_c ?? weatherData.temperature_celsius ?? '--'} °C</span>
                </div>
                <div>
                  <span className="text-faint block text-[9px]">FLIGHT SUITABILITY:</span>
                  <span className={`font-semibold ${weatherData.flight_suitability === 'OPTIMAL' ? 'text-status-success' : 'text-status-warning'}`}>
                    {weatherData.flight_suitability || 'OPTIMAL'}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/[0.04]">
                <div>
                  <span className="text-faint block text-[9px]">WIND SPEED:</span>
                  <span className="text-paper font-semibold">{weatherData.wind_speed_mps ? `${weatherData.wind_speed_mps} m/s` : '--'}</span>
                </div>
                <div>
                  <span className="text-faint block text-[9px]">PRECIPITATION:</span>
                  <span className="text-paper font-semibold">{weatherData.precipitation_mm_hr !== undefined ? `${weatherData.precipitation_mm_hr} mm/h` : '0 mm/h'}</span>
                </div>
                <div>
                  <span className="text-faint block text-[9px]">PROVIDER:</span>
                  <span className="text-muted font-semibold">Open-Meteo</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-2.5 bg-graphite/30 border border-white/[0.04] rounded text-center font-mono text-[10px] text-faint">
              ENVIRONMENT: UNAVAILABLE — Requires verified incident coordinates from Step 1.
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------ */}
        {/* STEP 3: DAMAGE / AI EVIDENCE (BI-TEMPORAL CD)                */}
        {/* ------------------------------------------------------------ */}
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
              3. DAMAGE / AI EVIDENCE
            </span>
            <span className="text-[9px] font-mono text-faint">SIAMESE CD // THRESHOLD 0.50</span>
          </div>

          <div>
            {isPairRejected ? (
              <div className="p-3 bg-status-critical/10 border border-status-critical/40 rounded space-y-2 font-mono">
                <div className="flex items-center gap-2 text-status-critical font-bold text-xs">
                  <span className="material-symbols-outlined text-[16px]">gpp_bad</span>
                  <span>BI-TEMPORAL PAIR REJECTED</span>
                </div>
                <p className="text-[11px] text-paper leading-tight">
                  {activeAnalysisResult?.pair_validation?.rejection_reason || 'Imagery pair failed scene correspondence. Siamese change detection halted.'}
                </p>
                <div className="p-2 bg-graphite/60 rounded border border-white/[0.06] text-[10px] space-y-1">
                  <div className="flex justify-between text-muted">
                    <span>STATUS:</span>
                    <span className="font-bold text-status-critical">{activeAnalysisResult?.pair_validation?.status || 'PAIR_MISMATCH'}</span>
                  </div>
                  <div className="flex justify-between text-muted">
                    <span>INFERENCE GATE:</span>
                    <span className="font-bold text-status-critical">HALTED (0 PIXELS EVALUATED)</span>
                  </div>
                  {activeAnalysisResult?.pair_validation?.metrics && (
                    <>
                      <div className="flex justify-between text-muted">
                        <span>KEYPOINT INLIERS:</span>
                        <span className="text-paper">{activeAnalysisResult.pair_validation.metrics.inliers ?? 'N/A'}</span>
                      </div>
                      <div className="flex justify-between text-muted">
                        <span>PATCH CORRELATION (NCC):</span>
                        <span className="text-paper">
                          {typeof activeAnalysisResult.pair_validation.metrics.median_patch_corr === 'number'
                            ? activeAnalysisResult.pair_validation.metrics.median_patch_corr.toFixed(3)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between text-muted">
                        <span>FOURIER PHASE SHIFT:</span>
                        <span className="text-paper">
                          {typeof activeAnalysisResult.pair_validation.metrics.phase_shift === 'number'
                            ? `${activeAnalysisResult.pair_validation.metrics.phase_shift.toFixed(1)} px`
                            : 'N/A'}
                        </span>
                      </div>
                    </>
                  )}
                  {typeof activeAnalysisResult?.pair_validation?.validation_latency_ms === 'number' && (
                    <div className="flex justify-between text-muted">
                      <span>VALIDATION LATENCY:</span>
                      <span className="text-accent">{activeAnalysisResult.pair_validation.validation_latency_ms.toFixed(1)} ms</span>
                    </div>
                  )}
                </div>
              </div>
            ) : activeAnalysisResult?.damage_analysis ? (
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-mono font-bold text-status-critical">
                  {activeAnalysisResult.damage_analysis.damage_percentage.toFixed(1)}%
                </span>
                <span className="text-xs font-mono text-accent uppercase font-bold">
                  {activeAnalysisResult.damage_analysis.damage_percentage > 50
                    ? 'CATASTROPHIC'
                    : activeAnalysisResult.damage_analysis.damage_percentage > 25
                    ? 'SEVERE'
                    : activeAnalysisResult.damage_analysis.damage_percentage > 10
                    ? 'MODERATE'
                    : activeAnalysisResult.damage_analysis.damage_percentage > 0
                    ? 'MINOR'
                    : 'NO_DAMAGE'}
                </span>
              </div>
            ) : damage ? (
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-mono font-bold text-status-critical">
                  {damage.damage_percentage.toFixed(1)}%
                </span>
                <span className="text-xs font-mono text-muted uppercase">
                  {damage.classification}
                </span>
              </div>
            ) : (
              <div className="p-3 bg-graphite/60 border border-white/[0.04] rounded text-center">
                <span className="text-[11px] font-mono text-faint">
                  DAMAGE ANALYSIS UNAVAILABLE — INGEST SCENE PAIR
                </span>
              </div>
            )}
          </div>

          {!isPairRejected && activeAnalysisResult?.damage_analysis && (
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
              <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint block">DAMAGED PIXELS:</span>
                <span className="text-paper font-semibold">{activeAnalysisResult.damage_analysis.damage_pixels.toLocaleString()}</span>
              </div>
              <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint block">TOTAL PIXELS:</span>
                <span className="text-paper font-semibold">{activeAnalysisResult.damage_analysis.total_pixels.toLocaleString()}</span>
              </div>
              <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint block">SCENE-WIDE MEAN PROB:</span>
                <span className="text-accent font-semibold">{(activeAnalysisResult.damage_analysis.probability_mean * 100).toFixed(1)}%</span>
              </div>
              <div className="p-2 bg-graphite/40 rounded border border-white/[0.04]">
                <span className="text-faint block">DAMAGE RATIO:</span>
                <span className="text-paper font-semibold">{activeAnalysisResult.damage_analysis.damage_ratio.toFixed(4)}</span>
              </div>
            </div>
          )}

          {!isPairRejected && activeAnalysisResult?.pair_validation && (
            <div className="p-2.5 bg-graphite/50 border border-white/[0.06] rounded font-mono text-[10px] space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-faint">PAIR COMPATIBILITY:</span>
                <span className="px-1.5 py-0.2 rounded font-bold bg-accent/15 text-accent border border-accent/30">
                  {activeAnalysisResult.pair_validation.status}
                </span>
              </div>
              {activeAnalysisResult.pair_validation.warnings?.slice(0, 2).map((w: string, idx: number) => (
                <p key={idx} className="text-status-warning leading-tight">⚠ {w}</p>
              ))}
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------ */}
        {/* STEP 4: RISK / SITUATION ASSESSMENT                          */}
        {/* ------------------------------------------------------------ */}
        {(() => {
          const risk = getRiskAssessment();
          return (
            <div className="p-4 border-b border-white/[0.06] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
                  4. RISK / SITUATION
                </span>
                <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold ${
                  risk.status === 'CALCULATED'
                    ? risk.level === 'CRITICAL'
                      ? 'bg-status-critical/15 text-status-critical border border-status-critical/30'
                      : 'bg-accent/15 text-accent border border-accent/30'
                    : risk.status === 'DEMO_CONTEXT'
                    ? 'bg-status-warning/15 text-status-warning border border-status-warning/30'
                    : 'bg-elevated text-faint border border-white/[0.1]'
                }`}>
                  {risk.badge || risk.status}
                </span>
              </div>

              {risk.status === 'CALCULATED' ? (
                <div className="p-2.5 bg-graphite/60 border border-accent/30 rounded font-mono space-y-2">
                  <div className="flex items-center justify-between text-[10px] text-accent font-bold">
                    <span>{risk.title}</span>
                    <span className="text-status-success text-[9px]">● VERIFIED GROUND CONTEXT</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <div>
                      <span className="text-2xl font-bold text-accent">{risk.score}</span>
                      <span className="text-xs text-muted"> / 100</span>
                    </div>
                    <span className={`text-xs font-bold ${risk.level === 'CRITICAL' ? 'text-status-critical' : risk.level === 'HIGH' ? 'text-status-warning' : 'text-accent'}`}>
                      {risk.level} VULNERABILITY
                    </span>
                  </div>
                  <div className="text-[9px] text-faint border-t border-white/[0.04] pt-1.5 leading-tight">
                    <span className="text-muted block font-semibold mb-0.5">WEIGHTING FORMULA:</span>
                    <span>{risk.formula}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 pt-1 text-[9px] border-t border-white/[0.04]">
                    <span className="text-status-success">● COORDS: VERIFIED</span>
                    <span className={risk.inputs.weather ? 'text-status-success' : 'text-faint'}>● WEATHER: {risk.inputs.weather ? 'LIVE' : 'OPTIONAL'}</span>
                    <span className="text-status-success">● DAMAGE: VERIFIED</span>
                  </div>
                </div>
              ) : risk.status === 'DEMO_CONTEXT' ? (
                <div className="p-2.5 bg-graphite/60 border border-status-warning/40 rounded font-mono space-y-2">
                  <div className="flex items-center justify-between text-[10px] text-status-warning font-bold">
                    <span>{risk.title}</span>
                    <span className="text-status-warning text-[9px]">● DEMO CONTEXT</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <div>
                      <span className="text-2xl font-bold text-status-warning">{risk.score}</span>
                      <span className="text-xs text-muted"> / 100</span>
                    </div>
                    <span className="text-xs font-bold text-status-warning">
                      {risk.level} VULNERABILITY (DEMO)
                    </span>
                  </div>
                  <p className="text-[9px] text-status-warning leading-tight border-t border-white/[0.04] pt-1.5">
                    ⚠ {risk.disclaimer}
                  </p>
                  <div className="text-[9px] text-faint leading-tight">
                    <span className="text-muted block font-semibold mb-0.5">WEIGHTING FORMULA:</span>
                    <span>{risk.formula}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 pt-1 text-[9px] border-t border-white/[0.04]">
                    <span className="text-status-warning">● COORDS: DEMO AOI</span>
                    <span className="text-faint">● WEATHER: BASELINE</span>
                    <span className="text-status-success">● DAMAGE: VERIFIED</span>
                  </div>
                </div>
              ) : (
                <div className="p-2.5 bg-graphite/30 border border-white/[0.06] rounded font-mono text-[10px] space-y-1.5">
                  <div className="text-status-warning font-semibold flex items-center gap-1">
                    <span className="material-symbols-outlined text-[13px]">info</span>
                    <span>{risk.title}</span>
                  </div>
                  <p className="text-faint text-[9px] leading-tight">
                    {risk.reason}
                  </p>
                  <div className="grid grid-cols-3 gap-1 pt-1 text-[9px]">
                    <span className={risk.inputs.coordinates ? 'text-status-success' : 'text-faint'}>
                      ● COORDS: {risk.inputs.coordinates ? 'OK' : 'MISSING'}
                    </span>
                    <span className={risk.inputs.weather ? 'text-status-success' : 'text-faint'}>
                      ● WEATHER: {risk.inputs.weather ? 'OK' : 'OPTIONAL'}
                    </span>
                    <span className={risk.inputs.damage ? 'text-status-success' : 'text-faint'}>
                      ● DAMAGE: {risk.inputs.damage ? 'OK' : 'MISSING'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* ------------------------------------------------------------ */}
        {/* STEP 5: VERIFIED SHELTER INVENTORY (POSTGIS)                 */}
        {/* ------------------------------------------------------------ */}
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
              5. VERIFIED SHELTERS
            </span>
            <span className="text-[9px] font-mono text-accent">
              {shelterCandidates.length > 0 ? `${shelterCandidates.length} IN RANGE` : 'POSTGIS REGISTRY'}
            </span>
          </div>

          {/* Search Radius Selector */}
          <div className="flex items-center justify-between font-mono text-[10px]">
            <span className="text-faint">RADIUS:</span>
            <div className="flex items-center gap-1 bg-graphite p-0.5 rounded border border-white/[0.08]">
              {[25, 50, 100, 250, null].map((rad, idx) => (
                <button
                  key={idx}
                  onClick={() => setSearchRadiusKm(rad)}
                  className={`px-1.5 py-0.5 rounded text-[9px] transition-all cursor-pointer ${
                    searchRadiusKm === rad
                      ? 'bg-accent text-graphite font-bold shadow'
                      : 'text-muted hover:text-paper'
                  }`}
                >
                  {rad === null ? 'ALL' : `${rad} km`}
                </button>
              ))}
            </div>
          </div>

          {/* Shelters List or Explicit Empty State */}
          {sheltersLoading ? (
            <div className="p-4 bg-graphite/40 rounded text-center font-mono text-[11px] text-muted flex items-center justify-center gap-2">
              <span className="material-symbols-outlined text-accent animate-spin text-[16px]">progress_activity</span>
              <span>QUERYING POSTGIS GEODETIC SHELTERS...</span>
            </div>
          ) : shelterCandidates.length > 0 ? (
            <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
              {shelterCandidates.map((s) => {
                const sId = s.id || s.shelter_id;
                const isSelected = (selectedShelter?.id || selectedShelter?.shelter_id) === sId;
                const dist = s.distance_km !== undefined ? s.distance_km : null;
                const occ = s.capacity_occupied ?? s.current_occupancy ?? 0;
                const cap = s.capacity_total ?? s.capacity ?? 'N/A';
                return (
                  <div
                    key={sId}
                    onClick={() => setSelectedShelter(s)}
                    className={`p-2 rounded border font-mono text-[11px] transition-all cursor-pointer flex items-center justify-between ${
                      isSelected
                        ? 'bg-accent/15 border-accent text-paper'
                        : 'bg-graphite/50 border-white/[0.06] text-muted hover:border-white/[0.2] hover:text-paper'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <div className={`w-3 h-3 rounded-full flex items-center justify-center text-[8px] font-bold ${
                        isSelected ? 'bg-accent text-graphite' : 'bg-white/[0.1] text-faint'
                      }`}>
                        {isSelected ? '✓' : ''}
                      </div>
                      <div className="truncate">
                        <span className="font-semibold block truncate">{s.name}</span>
                        <span className="text-[9px] text-faint block">{s.shelter_type || 'COMMUNITY_SHELTER'} • {s.district_code || s.state_code || 'REGIONAL'}</span>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0 ml-2">
                      <span className="text-accent font-bold block text-[10px]">
                        {dist !== null ? `${dist.toFixed(1)} km` : 'COORDINATES SET'}
                      </span>
                      <span className={`text-[9px] px-1 rounded ${s.operational_status === 'CONFIRMED_OPERATIONAL' || s.operational_status === 'OPEN' ? 'text-status-success bg-status-success/10' : 'text-faint'}`}>
                        {s.operational_status || 'OPEN'} ({occ}/{cap})
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-3 bg-graphite/40 border border-status-warning/30 rounded font-mono text-[10px] space-y-1 text-center">
              <span className="text-status-warning font-semibold block">
                NO VERIFIED SHELTERS AVAILABLE
              </span>
              <p className="text-faint leading-tight text-[9px]">
                {shelterError || `No verified emergency shelters registered within ${searchRadiusKm ? `${searchRadiusKm} km` : 'PostGIS database'}. Zero-fabrication policy active.`} Expand radius to 250 km or ALL to search regional facilities.
              </p>
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------ */}
        {/* STEP 6: EVACUATION ROUTE & INTEGRATED MAP                    */}
        {/* ------------------------------------------------------------ */}
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
              6. EVACUATION ROUTE
            </span>
            <span className="text-[9px] font-mono text-accent">
              OPENROUTESERVICE
            </span>
          </div>

          {/* Route Status Card */}
          {routeLoading ? (
            <div className="p-3 bg-graphite/40 rounded text-[11px] font-mono text-muted flex items-center justify-center gap-2">
              <span className="material-symbols-outlined text-accent animate-spin text-[16px]">progress_activity</span>
              <span>CALCULATING REAL ROAD GRAPH TRAJECTORY...</span>
            </div>
          ) : selectedShelter && routeData && routeData.status === 'AVAILABLE' ? (
            <div className="p-2.5 bg-graphite/60 border border-accent/40 rounded font-mono text-[11px] space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-paper font-bold flex items-center gap-1">
                  <span className="material-symbols-outlined text-accent text-[14px]">alt_route</span>
                  <span>{selectedShelter.name} Corridor</span>
                </span>
                <span className="px-1.5 py-0.2 rounded bg-status-success/15 text-status-success border border-status-success/30 text-[9px] font-bold">
                  VIABLE ROAD
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-[10px] pt-1 border-t border-white/[0.04]">
                <div>
                  <span className="text-faint block">DISTANCE:</span>
                  <span className="text-accent font-semibold">
                    {routeData.total_distance_meters ? `${(routeData.total_distance_meters / 1000).toFixed(1)} km` : '--'}
                  </span>
                </div>
                <div>
                  <span className="text-faint block">DURATION:</span>
                  <span className="text-paper font-semibold">
                    {routeData.total_duration_seconds ? `${Math.round(routeData.total_duration_seconds / 60)} min` : '--'}
                  </span>
                </div>
                <div>
                  <span className="text-faint block">PROVIDER:</span>
                  <span className="text-paper font-semibold">{routeData.provider_name || 'OpenRouteService'}</span>
                </div>
              </div>
            </div>
          ) : routeError ? (
            <div className="p-2.5 bg-graphite/40 border border-status-warning/30 rounded font-mono text-[10px] space-y-1">
              <div className="flex items-center gap-1 text-status-warning font-bold">
                <span className="material-symbols-outlined text-[14px]">warning</span>
                <span>Route unavailable — no valid route returned by routing provider.</span>
              </div>
              <p className="text-faint leading-tight text-[9px]">
                Road network graph could not connect the incident site to the destination facility. Strictly zero straight-line distance rendered.
              </p>
            </div>
          ) : (
            <div className="p-2.5 bg-graphite/30 border border-white/[0.06] rounded font-mono text-[10px] space-y-1 text-center">
              <span className="text-status-warning font-semibold block">
                NO VERIFIED SHELTER DESTINATION AVAILABLE
              </span>
              <p className="text-faint text-[9px] leading-tight">
                Evacuation route calculation requires a verified shelter destination. No straight-line or synthetic route will be generated.
              </p>
            </div>
          )}

          {/* Integrated Leaflet Route Map */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[9px] font-mono text-faint">
              <span>INTEGRATED GEOSPATIAL MAP</span>
              <span className="text-accent">
                {operatorLocation ? '● INCIDENT (RED) | ■ SHELTER (GREEN/CYAN)' : 'AMBER DASH: DEMO AOI (SYNTHETIC)'}
              </span>
            </div>
            <div
              ref={mapContainerRef}
              className="w-full h-52 rounded border border-white/[0.1] bg-[#07090C] overflow-hidden z-0"
            />
          </div>
        </div>

        {/* ------------------------------------------------------------ */}
        {/* STEP 7: OPERATIONAL SITUATION REPORT                         */}
        {/* ------------------------------------------------------------ */}
        <div className="p-4 space-y-3 bg-graphite/20">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block font-bold">
              7. OPERATIONAL REPORT
            </span>
            <span className="text-[9px] font-mono text-status-ai">DATA PARITY GUARANTEE</span>
          </div>

          <p className="text-[11px] text-muted font-mono leading-relaxed">
            Generate an authoritative, tamper-evident operational PDF report combining Siamese damage perception, geocoded context, PostGIS shelters inventory, and road evacuation corridors.
          </p>

          <div className="flex items-center gap-2 font-mono">
            <button
              onClick={handleDownloadPdfReport}
              disabled={isDownloadingReport}
              className="flex-1 px-3 py-2 rounded bg-accent text-graphite font-bold text-xs hover:bg-accent/90 disabled:opacity-50 transition-all flex items-center justify-center gap-1.5 shadow cursor-pointer"
            >
              <span className="material-symbols-outlined text-[15px]">picture_as_pdf</span>
              <span>{isDownloadingReport ? 'GENERATING PDF...' : 'DOWNLOAD OPERATIONAL REPORT (PDF)'}</span>
            </button>

            <Link
              to={`/situations/${situation?.id || '00000000-0000-0000-0000-000000000002'}/report${
                activeAnalysisResult?.analysis_id ? `?analysis_id=${encodeURIComponent(activeAnalysisResult.analysis_id)}` : ''
              }`}
              className="px-3 py-2 rounded bg-elevated border border-white/[0.1] text-paper hover:text-accent hover:border-accent text-xs flex items-center gap-1 transition-all cursor-pointer"
              title="Open Interactive Situation Report view"
            >
              <span className="material-symbols-outlined text-[15px]">open_in_new</span>
              <span>VIEW REPORT</span>
            </Link>
          </div>

          <div className="p-2 bg-panel/60 border border-white/[0.04] rounded text-[10px] font-mono text-faint leading-tight">
            * Human Verification Statement: This report is generated deterministically by AERION AI Perception Services and incorporates exact data parity with the 6 operational steps above.
          </div>
        </div>
      </aside>

      {/* Upload Damage Pair Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        defaultMode="damage_pair"
        onAnalysisSuccess={(res, meta) => {
          setActiveAnalysisResult(res);
          if (meta?.preUrl) setCustomPreUrl(meta.preUrl);
          if (meta?.postUrl) setCustomPostUrl(meta.postUrl);
          const isRejected = Boolean(
            (res.pair_validation && res.pair_validation.is_compatible === false) ||
            res.status === 'PAIR_MISMATCH' ||
            res.overall_status === 'PAIR_VALIDATION_FAILED'
          );
          if (isRejected) {
            // Stale State Clearing: Clear all previous damage metrics and reports on rejected pair
            setDamage(null);
          } else if (res.damage_analysis) {
            const dmg = res.damage_analysis;
            const percentage = dmg.damage_percentage !== undefined ? dmg.damage_percentage : (dmg.damage_ratio ? dmg.damage_ratio * 100 : 0);
            let classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC' = 'NO_DAMAGE';
            if (percentage >= 50) classification = 'CATASTROPHIC';
            else if (percentage >= 25) classification = 'SEVERE';
            else if (percentage >= 10) classification = 'MODERATE';
            else if (percentage > 0) classification = 'MINOR';

            setDamage({
              damage_percentage: percentage,
              damaged_pixels: dmg.damage_pixels || 0,
              total_pixels: dmg.total_pixels || 0,
              mean_damage_probability: dmg.probability_mean || 0,
              classification,
            });
          }
          if (res.analysis_id) {
            setSearchParams({ analysis_id: res.analysis_id });
          }
        }}
      />

      {/* Analysis History Modal */}
      <AnalysisHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        currentMode="disaster"
        onSelectAnalysis={async (item) => {
          const targetId = item.analysis_id || item.job_id;
          if (targetId) {
            setSearchParams({ analysis_id: targetId });
            try {
              const resp = await analysisApi.getById(targetId);
              if (resp.success && resp.data) {
                setActiveAnalysisResult(resp.data);
                const isRejected = Boolean(
                  (resp.data.pair_validation && resp.data.pair_validation.is_compatible === false) ||
                  resp.data.status === 'PAIR_MISMATCH' ||
                  resp.data.overall_status === 'PAIR_VALIDATION_FAILED'
                );
                if (isRejected) {
                  setDamage(null);
                } else {
                  if (resp.data.location_context && !operatorLocation) {
                    setOperatorLocation(resp.data.location_context);
                  }
                  if (resp.data.damage_analysis) {
                    const dmg = resp.data.damage_analysis;
                    const percentage = dmg.damage_percentage || (dmg.damage_ratio ? dmg.damage_ratio * 100 : 0);
                    let classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC' = 'NO_DAMAGE';
                    if (percentage >= 50) classification = 'CATASTROPHIC';
                    else if (percentage >= 25) classification = 'SEVERE';
                    else if (percentage >= 10) classification = 'MODERATE';
                    else if (percentage > 0) classification = 'MINOR';

                    setDamage({
                      damage_percentage: percentage,
                      damaged_pixels: dmg.damage_pixels || 0,
                      total_pixels: dmg.total_pixels || 0,
                      mean_damage_probability: dmg.probability_mean || 0,
                      classification,
                    });
                  }
                }
              }
            } catch (err) {
              console.warn('Could not reopen disaster analysis:', err);
            }
          }
        }}
      />

      {/* Operator Location Modal */}
      <OperatorLocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        existingLocation={operatorLocation}
        onConfirmLocation={(loc) => {
          setOperatorLocation(loc);
        }}
      />
    </div>
  );
};
