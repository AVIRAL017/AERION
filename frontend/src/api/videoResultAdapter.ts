import { AERIONAnalysisResultData, RuntimeDetection, TacticalCrossingIndicator } from '../types';

/**
 * Normalizes the backend recorded-video analysis response into a runtime-safe
 * AERIONAnalysisResultData object that BorderPage can render without unhandled TypeErrors.
 *
 * Backend returns:
 * {
 *   processed_frames: number,
 *   total_video_frames: number,
 *   report: SituationReport / BorderSituationReport,
 *   annotated_video_artifact?: AnnotatedVideoArtifact,
 *   persistence?: any
 * }
 */
export function normalizeVideoAnalysisResponse(
  rawResponse: any,
  fallbackAnalysisId: string = 'video-analysis-job'
): AERIONAnalysisResultData {
  if (!rawResponse || typeof rawResponse !== 'object') {
    return createEmptyVideoResult(fallbackAnalysisId);
  }

  const report = rawResponse.report || rawResponse;
  const processedFrames = typeof rawResponse.processed_frames === 'number'
    ? rawResponse.processed_frames
    : (typeof report.processed_frames === 'number' ? report.processed_frames : 0);

  const totalFrames = typeof rawResponse.total_video_frames === 'number'
    ? rawResponse.total_video_frames
    : (typeof report.total_video_frames === 'number' ? report.total_video_frames : processedFrames);

  // Extract detections if available from rawResponse.all_detections or report observations
  const detections: RuntimeDetection[] = [];
  const rawDetections = rawResponse.all_detections || report.detections || [];
  if (Array.isArray(rawDetections)) {
    rawDetections.forEach((d: any) => {
      let bbox = d.bbox;
      if (Array.isArray(bbox) && bbox.length >= 4) {
        bbox = { x1: bbox[0], y1: bbox[1], x2: bbox[2], y2: bbox[3] };
      }
      detections.push({
        source: d.source || 'border_video',
        class_id: typeof d.class_id === 'number' ? d.class_id : 0,
        class_name: d.class_name || 'person',
        confidence: typeof d.confidence === 'number' ? d.confidence : 1.0,
        bbox: bbox || null,
        obb_points: d.obb_points || null,
        track_id: d.track_id !== undefined ? d.track_id : null,
        frame_number: d.frame_number !== undefined ? d.frame_number : null,
      });
    });
  }

  // Extract structured tracks
  const tracks: any[] = [];
  const rawTracks = rawResponse.tracks || report.tracks || [];
  if (Array.isArray(rawTracks)) {
    rawTracks.forEach((t: any) => {
      tracks.push(t);
    });
  }

  // Extract crossing indicators if present in report
  const rawIndicators = report.potential_unauthorized_crossing_indicators || [];
  const crossingIndicators: TacticalCrossingIndicator[] = Array.isArray(rawIndicators)
    ? rawIndicators.map((ind: any) => ({
        event_type: ind.event_type || 'POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR',
        detection_id: ind.detection_id,
        track_id: ind.track_id,
        class_name: ind.class_name || ind.target_class,
        confidence: typeof ind.confidence === 'number' ? ind.confidence : undefined,
        threat_level: ind.threat_level || ind.alert_level || 'MONITORING',
        terminology: ind.terminology || 'Potential Unauthorized Crossing Indicator',
        details: ind.details || ind.payload || {},
      }))
    : [];

  const analysisId = report.report_id || report.session_id || rawResponse.job_id || fallbackAnalysisId;

  // Scene summary from report detections_summary if available
  const detSummary = report.detections_summary || {};
  const totalObs = detSummary.total_observations || 0;

  return {
    project: report.project_id || '00000000-0000-0000-0000-000000000001',
    version: 'v1',
    analysis_id: String(analysisId),
    mode: 'border',
    source_type: 'RECORDED_FOOTAGE',
    image_width: null,
    image_height: null,
    frame_number: processedFrames,
    detections,
    tracks,
    border_analysis: [],
    damage_analysis: null,
    intelligence: [],
    summary: {
      critical: 0,
      high: 0,
      medium: crossingIndicators.length,
      low: totalObs,
    },
    overall_status: report.tactical_overview?.threat_level || 'COMPLETED',
    metadata: {
      processed_frames: processedFrames,
      total_video_frames: totalFrames,
      temporal_mode: 'RECORDED_FOOTAGE',
      tactical_overview: report.tactical_overview,
      sector_assessments: report.sector_assessments,
    },
    annotated_image_base64: null,
    annotated_video_artifact: rawResponse.annotated_video_artifact || report.annotated_video_artifact || null,
    processed_frames: processedFrames,
    total_video_frames: totalFrames,
    potential_unauthorized_crossing_indicators: crossingIndicators,
    report,
  };
}

function createEmptyVideoResult(id: string): AERIONAnalysisResultData {
  return {
    project: '00000000-0000-0000-0000-000000000001',
    version: 'v1',
    analysis_id: id,
    mode: 'border',
    source_type: 'RECORDED_FOOTAGE',
    image_width: null,
    image_height: null,
    frame_number: 0,
    detections: [],
    tracks: [],
    border_analysis: [],
    damage_analysis: null,
    intelligence: [],
    summary: { critical: 0, high: 0, medium: 0, low: 0 },
    overall_status: 'UNAVAILABLE',
    metadata: { temporal_mode: 'RECORDED_FOOTAGE' },
    annotated_image_base64: null,
    annotated_video_artifact: null,
    processed_frames: 0,
    total_video_frames: 0,
    potential_unauthorized_crossing_indicators: [],
    report: null,
  };
}
