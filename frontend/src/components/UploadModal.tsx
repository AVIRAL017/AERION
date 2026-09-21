import React, { useState, useRef, useEffect } from 'react';
import { analysisApi } from '../api';
import { normalizeVideoAnalysisResponse } from '../api/videoResultAdapter';
import { AERIONAnalysisResultData } from '../types';

export type UploadMode = 'drone_image' | 'satellite_image' | 'damage_pair' | 'border_video';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultMode?: UploadMode;
  onAnalysisSuccess: (result: AERIONAnalysisResultData, sourceMeta?: { preUrl?: string; postUrl?: string; imageUrl?: string; videoUrl?: string }) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  defaultMode = 'drone_image',
  onAnalysisSuccess,
}) => {
  const [mode, setMode] = useState<UploadMode>(defaultMode);
  
  // Single image / video state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  
  // Damage pair state
  const [preFile, setPreFile] = useState<File | null>(null);
  const [postFile, setPostFile] = useState<File | null>(null);
  const [prePreview, setPrePreview] = useState<string | null>(null);
  const [postPreview, setPostPreview] = useState<string | null>(null);

  // Pre-analysis pair validation state (non-authoritative UI advisory)
  const [pairValidationStatus, setPairValidationStatus] = useState<{
    isValidating: boolean;
    isCompatible: boolean | null;
    status: string | null;
    reason: string | null;
  }>({
    isValidating: false,
    isCompatible: null,
    status: null,
    reason: null,
  });

  // Parameter options
  const [droneModel, setDroneModel] = useState<'visdrone_only' | 'unified'>('visdrone_only');
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.25);
  const [maxFrames, setMaxFrames] = useState<number>(30);
  const [frameStride, setFrameStride] = useState<number>(5);

  // Upload/Processing state
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  // Pre-flight pair compatibility check whenever both T0 and T1 are selected
  useEffect(() => {
    if (mode !== 'damage_pair' || !preFile || !postFile) {
      setPairValidationStatus({ isValidating: false, isCompatible: null, status: null, reason: null });
      return;
    }

    let isMounted = true;
    const runValidation = async () => {
      setPairValidationStatus(prev => ({ ...prev, isValidating: true }));
      try {
        const [b64Pre, b64Post] = await Promise.all([
          fileToBase64(preFile),
          fileToBase64(postFile),
        ]);
        const res = await analysisApi.validateDamagePair({
          before_base64: b64Pre,
          after_base64: b64Post,
        });
        if (!isMounted) return;
        if (res.success && res.data) {
          setPairValidationStatus({
            isValidating: false,
            isCompatible: Boolean(res.data.is_compatible),
            status: res.data.status,
            reason: res.data.rejection_reason || null,
          });
        } else {
          setPairValidationStatus({
            isValidating: false,
            isCompatible: false,
            status: 'PAIR_MISMATCH',
            reason: (res.error as any)?.message || 'Scene correspondence check failed.',
          });
        }
      } catch (err: any) {
        if (!isMounted) return;
        setPairValidationStatus({
          isValidating: false,
          isCompatible: false,
          status: 'VALIDATION_ERROR',
          reason: err.message || 'Validation request failed.',
        });
      }
    };

    runValidation();
    return () => {
      isMounted = false;
    };
  }, [preFile, postFile, mode]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const preInputRef = useRef<HTMLInputElement>(null);
  const postInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const MAX_IMAGE_SIZE_MB = 15;
  const MAX_VIDEO_SIZE_MB = 25;

  const validateFile = (file: File, isVideo: boolean = false): boolean => {
    setFileError(null);
    const maxLimitMb = isVideo ? MAX_VIDEO_SIZE_MB : MAX_IMAGE_SIZE_MB;
    const maxBytes = maxLimitMb * 1024 * 1024;
    if (file.size > maxBytes) {
      const providedMb = (file.size / (1024 * 1024)).toFixed(1);
      if (isVideo) {
        setFileError(`File size exceeds 25MB limit (provided: ${providedMb}MB). Please provide a bounded clip.`);
      } else {
        setFileError(`File size exceeds ${maxLimitMb}MB limit (provided: ${providedMb}MB).`);
      }
      return false;
    }

    if (isVideo) {
      if (!file.type.startsWith('video/') && !file.name.match(/\.(mp4|avi|mov|mkv)$/i)) {
        setFileError('Invalid video format. Supported: MP4, AVI, MOV, MKV.');
        return false;
      }
    } else {
      if (!file.type.startsWith('image/') && !file.name.match(/\.(jpg|jpeg|png|bmp|tif|tiff)$/i)) {
        setFileError('Invalid image format. Supported: JPG, PNG, BMP, TIFF.');
        return false;
      }
    }
    return true;
  };

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const res = reader.result as string;
        // Strip data:image/...;base64, or data:video/...;base64, prefix
        const base64Content = res.includes(',') ? res.split(',')[1] : res;
        resolve(base64Content);
      };
      reader.onerror = (err) => reject(err);
      reader.readAsDataURL(file);
    });
  };

  const handleSingleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file, mode === 'border_video')) {
        setSelectedFile(file);
        if (mode !== 'border_video') {
          const url = URL.createObjectURL(file);
          setFilePreview(url);
        } else {
          setFilePreview(file.name);
        }
      }
    }
  };

  const handlePreFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file, false)) {
        setPreFile(file);
        setPrePreview(URL.createObjectURL(file));
      }
    }
  };

  const handlePostFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file, false)) {
        setPostFile(file);
        setPostPreview(URL.createObjectURL(file));
      }
    }
  };

  const handleExecute = async () => {
    setErrorMessage(null);
    setFileError(null);

    if (mode === 'damage_pair') {
      if (!preFile || !postFile) {
        setFileError('Both pre-disaster and post-disaster images are required.');
        return;
      }
    } else {
      if (!selectedFile) {
        setFileError('Please select a file to analyze.');
        return;
      }
    }

    setIsProcessing(true);
    setStatusMessage('ENCODING ASSET PAYLOAD...');

    try {
      if (mode === 'drone_image') {
        const b64 = await fileToBase64(selectedFile!);
        setStatusMessage('TRANSMITTING TO PERCEPTION INFERENCE ENGINE (YOLOv8)...');
        const resp = await analysisApi.analyzeImage({
          image_base64: b64,
          source_type: 'drone',
          mode: 'border',
          drone_model: droneModel,
          confidence_threshold: confidenceThreshold,
          run_intelligence: true,
        });

        if (resp.success && resp.data) {
          setStatusMessage('INFERENCE COMPLETE. RENDERING TELEMETRY...');
          onAnalysisSuccess(resp.data, { imageUrl: filePreview || undefined });
          onClose();
        } else {
          throw new Error(typeof resp.error === 'string' ? resp.error : (resp.error as any)?.message || 'Inference execution failed.');
        }

      } else if (mode === 'satellite_image') {
        const b64 = await fileToBase64(selectedFile!);
        setStatusMessage('TRANSMITTING TO SATELLITE OBB DETECTOR (DOTA)...');
        const resp = await analysisApi.analyzeImage({
          image_base64: b64,
          source_type: 'satellite',
          mode: 'border',
          run_intelligence: true,
        });

        if (resp.success && resp.data) {
          setStatusMessage('OBB INFERENCE COMPLETE. RENDERING...');
          onAnalysisSuccess(resp.data, { imageUrl: filePreview || undefined });
          onClose();
        } else {
          throw new Error(typeof resp.error === 'string' ? resp.error : (resp.error as any)?.message || 'Satellite analysis failed.');
        }

      } else if (mode === 'damage_pair') {
        const [beforeB64, afterB64] = await Promise.all([
          fileToBase64(preFile!),
          fileToBase64(postFile!),
        ]);
        setStatusMessage('TRANSMITTING TO BI-TEMPORAL SIAMESE RESNET-18 MODEL...');
        const resp = await analysisApi.analyzeDamage({
          before_base64: beforeB64,
          after_base64: afterB64,
          run_intelligence: true,
        });

        if (resp.success && resp.data) {
          if (resp.data.pair_validation && resp.data.pair_validation.is_compatible === false) {
            setStatusMessage('BI-TEMPORAL PAIR REJECTED. DAMAGE INFERENCE HALTED.');
          } else {
            setStatusMessage('DAMAGE MAP COMPUTED. RENDERING...');
          }
          onAnalysisSuccess(resp.data, {
            preUrl: prePreview || undefined,
            postUrl: postPreview || undefined,
          });
          onClose();
        } else {
          throw new Error(typeof resp.error === 'string' ? resp.error : (resp.error as any)?.message || 'Damage assessment failed.');
        }

      } else if (mode === 'border_video') {
        const videoB64 = await fileToBase64(selectedFile!);
        setStatusMessage(`SUBMITTING VIDEO ANALYSIS JOB (STRIDE=${frameStride}, MAX=${maxFrames})...`);
        
        // Submit asynchronous job with idempotency key
        const idempotencyKey = `video_${Date.now()}_${selectedFile?.name || 'clip'}`;
        const submitResp = await analysisApi.submitBorderJob({
          video_base64: videoB64,
          frame_stride: frameStride,
          max_frames: maxFrames,
          generate_annotated_video: true,
          idempotency_key: idempotencyKey,
        });

        if (!submitResp.success || !submitResp.data?.job_id) {
          // If asynchronous job route fails, fallback to direct streaming video analysis
          setStatusMessage('FALLBACK: EXECUTING DIRECT STREAMING INFERENCE...');
          const directResp = await analysisApi.analyzeBorderVideo({
            video_base64: videoB64,
            frame_stride: frameStride,
            max_frames: maxFrames,
          });
          if (directResp.success && directResp.data) {
            const normalized = normalizeVideoAnalysisResponse(directResp.data);
            const rawVideoUrl = selectedFile ? URL.createObjectURL(selectedFile) : undefined;
            onAnalysisSuccess(normalized, { imageUrl: undefined, videoUrl: rawVideoUrl });
            onClose();
            return;
          } else {
            throw new Error(typeof directResp.error === 'string' ? directResp.error : (directResp.error as any)?.message || 'Video analysis failed.');
          }
        }

        const jobId = submitResp.data.job_id;
        setStatusMessage(`JOB ${jobId.substring(0, 8)} SUBMITTED. QUEUED FOR PIPELINE EXECUTION...`);

        // Poll job status until completion or failure
        const maxPollAttempts = 120; // 120 * 1s = 2 minutes max
        let attempts = 0;
        let jobCompleted = false;

        while (attempts < maxPollAttempts && !jobCompleted) {
          await new Promise((res) => setTimeout(res, 1000));
          attempts++;

          try {
            const statusResp = await analysisApi.getJobStatus(jobId);
            if (statusResp.success && statusResp.data) {
              const job = statusResp.data;
              const stage = job.current_stage || job.status || 'PROCESSING';
              const pct = typeof job.progress_percent === 'number' ? job.progress_percent : 0;
              setProgressPercent(pct);
              setStatusMessage(`[${pct}%] ${stage.toUpperCase()}...`);

              if (job.status === 'COMPLETED' || job.status === 'COMPLETED_WITH_LIMITATIONS' || job.status === 'completed') {
                jobCompleted = true;
                const resultData = job.result || {};
                const normalized = normalizeVideoAnalysisResponse(resultData, job.analysis_id || jobId);
                const rawVideoUrl = selectedFile ? URL.createObjectURL(selectedFile) : undefined;
                onAnalysisSuccess(normalized, {
                  imageUrl: undefined,
                  videoUrl: rawVideoUrl,
                });
                onClose();
                return;
              } else if (job.status === 'FAILED' || job.status === 'PROCESSING_FAILED' || job.status === 'CANCELLED' || job.status === 'failed') {
                throw new Error(job.error || `Analysis job failed with status: ${job.status}`);
              }
            }
          } catch (pollErr: any) {
            if (pollErr.message && pollErr.message.includes('Analysis job failed')) {
              throw pollErr;
            }
            // Transient network retry
          }
        }

        if (!jobCompleted) {
          throw new Error('Video analysis timed out waiting for pipeline completion. Job may still be running in background.');
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Operation failed during backend execution.');
    } finally {
      setIsProcessing(false);
      setProgressPercent(0);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl bg-panel border border-white/[0.12] rounded-lg shadow-2xl overflow-hidden flex flex-col font-mono text-xs">
        {/* Modal Header */}
        <div className="h-12 px-5 flex items-center justify-between border-b border-white/[0.08] bg-[#0B0F14]">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-accent text-[20px]">upload_file</span>
            <span className="text-paper font-medium tracking-wider uppercase text-sm">
              INGEST OPERATIONAL ASSET
            </span>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="text-muted hover:text-paper transition-colors disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 flex flex-col gap-5 overflow-y-auto max-h-[75vh] custom-scrollbar">
          {/* Mode Selector Tabs */}
          <div className="grid grid-cols-4 gap-2 border-b border-white/[0.06] pb-4">
            <button
              onClick={() => { setMode('drone_image'); setSelectedFile(null); setFilePreview(null); }}
              disabled={isProcessing}
              className={`py-2 px-3 rounded flex flex-col items-center gap-1 border transition-all ${
                mode === 'drone_image'
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-white/[0.06] bg-elevated/40 text-muted hover:text-paper'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">flight</span>
              <span className="text-[10px] tracking-wide">DRONE AERIAL</span>
            </button>

            <button
              onClick={() => { setMode('satellite_image'); setSelectedFile(null); setFilePreview(null); }}
              disabled={isProcessing}
              className={`py-2 px-3 rounded flex flex-col items-center gap-1 border transition-all ${
                mode === 'satellite_image'
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-white/[0.06] bg-elevated/40 text-muted hover:text-paper'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">satellite_alt</span>
              <span className="text-[10px] tracking-wide">SATELLITE OBB</span>
            </button>

            <button
              onClick={() => { setMode('damage_pair'); }}
              disabled={isProcessing}
              className={`py-2 px-3 rounded flex flex-col items-center gap-1 border transition-all ${
                mode === 'damage_pair'
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-white/[0.06] bg-elevated/40 text-muted hover:text-paper'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">compare</span>
              <span className="text-[10px] tracking-wide">DAMAGE PAIR</span>
            </button>

            <button
              onClick={() => { setMode('border_video'); setSelectedFile(null); setFilePreview(null); }}
              disabled={isProcessing}
              className={`py-2 px-3 rounded flex flex-col items-center gap-1 border transition-all ${
                mode === 'border_video'
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-white/[0.06] bg-elevated/40 text-muted hover:text-paper'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">videocam</span>
              <span className="text-[10px] tracking-wide">VIDEO ANALYSIS</span>
            </button>
          </div>

          {/* Mode Description */}
          <div className="bg-[#07090C] p-3 rounded border border-white/[0.04] text-[11px] text-muted flex items-start gap-2">
            <span className="material-symbols-outlined text-accent text-[16px] mt-0.5">info</span>
            <div>
              {mode === 'drone_image' && 'Inference via frozen VisDrone YOLOv8 or Unified Drone detector. Produces real bounding boxes, confidence, and tactical classifications.'}
              {mode === 'satellite_image' && 'Inference via frozen DOTA OBB Oriented Bounding Box detector. Preserves exact 4-corner polygon geometry.'}
              {mode === 'damage_pair' && 'Inference via frozen Siamese ResNet-18 change detection network. Computes pixel-level damage ratio and status.'}
              {mode === 'border_video' && 'Asynchronous frame-by-frame analysis with ByteTrack multi-target state estimation. Optimized for bounded recorded video files.'}
            </div>
          </div>

          {/* Upload Inputs Area */}
          {mode === 'damage_pair' ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                {/* Pre-disaster box */}
                <div className="flex flex-col gap-2">
                  <span className="text-[11px] text-muted uppercase">PRE-DISASTER BASELINE (T0)</span>
                  <input
                    type="file"
                    ref={preInputRef}
                    onChange={handlePreFileChange}
                    accept="image/*"
                    className="hidden"
                  />
                  <div
                    onClick={() => !isProcessing && preInputRef.current?.click()}
                    className="h-36 border border-dashed border-white/[0.15] rounded flex flex-col items-center justify-center p-3 cursor-pointer hover:border-accent/60 bg-elevated/20 transition-all overflow-hidden relative"
                  >
                    {prePreview ? (
                      <img src={prePreview} alt="Pre-Disaster" className="w-full h-full object-cover" />
                    ) : (
                      <div className="flex flex-col items-center text-center gap-1 text-faint">
                        <span className="material-symbols-outlined text-[24px]">image</span>
                        <span className="text-[10px]">SELECT T0 IMAGE</span>
                        <span className="text-[9px] text-muted">Max 15MB (JPG/PNG)</span>
                      </div>
                    )}
                  </div>
                  {preFile && <span className="text-[10px] text-paper truncate">{preFile.name}</span>}
                </div>

                {/* Post-disaster box */}
                <div className="flex flex-col gap-2">
                  <span className="text-[11px] text-muted uppercase">POST-DISASTER SCENE (T1)</span>
                  <input
                    type="file"
                    ref={postInputRef}
                    onChange={handlePostFileChange}
                    accept="image/*"
                    className="hidden"
                  />
                  <div
                    onClick={() => !isProcessing && postInputRef.current?.click()}
                    className="h-36 border border-dashed border-white/[0.15] rounded flex flex-col items-center justify-center p-3 cursor-pointer hover:border-accent/60 bg-elevated/20 transition-all overflow-hidden relative"
                  >
                    {postPreview ? (
                      <img src={postPreview} alt="Post-Disaster" className="w-full h-full object-cover" />
                    ) : (
                      <div className="flex flex-col items-center text-center gap-1 text-faint">
                        <span className="material-symbols-outlined text-[24px]">image</span>
                        <span className="text-[10px]">SELECT T1 IMAGE</span>
                        <span className="text-[9px] text-muted">Max 15MB (JPG/PNG)</span>
                      </div>
                    )}
                  </div>
                  {postFile && <span className="text-[10px] text-paper truncate">{postFile.name}</span>}
                </div>
              </div>

              {/* Bi-Temporal Pair Preflight Validation Card */}
              {preFile && postFile && (
                <div className={`p-2.5 rounded border text-[11px] flex flex-col gap-1 transition-all ${
                  pairValidationStatus.isValidating
                    ? 'bg-elevated/40 border-white/[0.1] text-muted'
                    : pairValidationStatus.isCompatible === true
                    ? 'bg-status-success/10 border-status-success/30 text-status-success'
                    : pairValidationStatus.isCompatible === false
                    ? 'bg-status-critical/10 border-status-critical/30 text-status-critical'
                    : 'bg-elevated/40 border-white/[0.1] text-muted'
                }`}>
                  <div className="flex items-center justify-between font-mono font-bold tracking-wider">
                    <div className="flex items-center gap-1.5">
                      <span className={`material-symbols-outlined text-[16px] ${pairValidationStatus.isValidating ? 'animate-spin' : ''}`}>
                        {pairValidationStatus.isValidating ? 'sync' : pairValidationStatus.isCompatible ? 'check_circle' : 'cancel'}
                      </span>
                      <span>PAIR VALIDATION: {pairValidationStatus.isValidating ? 'EVALUATING SCENE CORRESPONDENCE...' : pairValidationStatus.isCompatible ? 'STRUCTURALLY_COMPATIBLE' : (pairValidationStatus.status || 'PAIR_MISMATCH')}</span>
                    </div>
                  </div>
                  {pairValidationStatus.isValidating ? (
                    <span className="text-[10px] text-muted">Analyzing geometric keypoint correspondence, phase correlation & reliable GPS...</span>
                  ) : pairValidationStatus.isCompatible === true ? (
                    <span className="text-[10px] text-status-success/80">✓ Same-scene evidence confirmed. Valid bi-temporal pair for change detection.</span>
                  ) : pairValidationStatus.isCompatible === false ? (
                    <div className="flex flex-col gap-0.5 text-[10px]">
                      <span className="font-semibold text-status-critical">✕ Incompatible imagery pair: {pairValidationStatus.reason || 'Insufficient scene correspondence'}.</span>
                      <span className="text-muted">Siamese change detection will be halted server-side to prevent false damage attribution.</span>
                    </div>
                  ) : null}
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col gap-2">
              <span className="text-[11px] text-muted uppercase">
                {mode === 'border_video' ? 'SELECT SURVEILLANCE FOOTAGE' : 'SELECT IMAGERY ASSET'}
              </span>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleSingleFileChange}
                accept={mode === 'border_video' ? 'video/*' : 'image/*'}
                className="hidden"
              />
              <div
                onClick={() => !isProcessing && fileInputRef.current?.click()}
                className="h-44 border border-dashed border-white/[0.15] rounded flex flex-col items-center justify-center p-4 cursor-pointer hover:border-accent/60 bg-elevated/20 transition-all overflow-hidden relative"
              >
                {filePreview && mode !== 'border_video' ? (
                  <img src={filePreview} alt="Selected" className="w-full h-full object-contain" />
                ) : selectedFile && mode === 'border_video' ? (
                  <div className="flex flex-col items-center gap-2 text-accent">
                    <span className="material-symbols-outlined text-[32px]">videocam</span>
                    <span className="text-paper text-xs">{selectedFile.name}</span>
                    <span className="text-[10px] text-muted">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-center gap-2 text-faint">
                    <span className="material-symbols-outlined text-[32px]">
                      {mode === 'border_video' ? 'movie' : 'add_photo_alternate'}
                    </span>
                    <span className="text-xs text-paper">CLICK TO CHOOSE FILE</span>
                    <span className="text-[10px] text-muted">
                      {mode === 'border_video' ? 'MP4 / AVI (Max 25MB)' : 'JPG / PNG / TIFF (Max 15MB)'}
                    </span>
                  </div>
                )}
              </div>
              {selectedFile && mode !== 'border_video' && (
                <span className="text-[10px] text-paper truncate">{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
              )}
            </div>
          )}

          {/* Model & Runtime Parameters */}
          {mode === 'drone_image' && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-white/[0.06]">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted uppercase">DRONE DETECTOR MODEL</label>
                <select
                  value={droneModel}
                  onChange={(e) => setDroneModel(e.target.value as any)}
                  disabled={isProcessing}
                  className="bg-elevated border border-white/[0.1] rounded px-2 py-1 text-paper text-xs outline-none"
                >
                  <option value="visdrone_only">VisDrone YOLOv8 (Frozen baseline)</option>
                  <option value="unified">Unified Drone 20ep (Multi-dataset)</option>
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted uppercase">CONFIDENCE THRESHOLD ({confidenceThreshold.toFixed(2)})</label>
                <input
                  type="range"
                  min="0.10"
                  max="0.80"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  disabled={isProcessing}
                  className="accent-accent"
                />
              </div>
            </div>
          )}

          {mode === 'border_video' && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-white/[0.06]">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted uppercase">FRAME STRIDE: {frameStride}</label>
                <input
                  type="range"
                  min="1"
                  max="15"
                  step="1"
                  value={frameStride}
                  onChange={(e) => setFrameStride(parseInt(e.target.value))}
                  disabled={isProcessing}
                  className="accent-accent"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted uppercase">MAX FRAMES TO PROCESS: {maxFrames}</label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="10"
                  value={maxFrames}
                  onChange={(e) => setMaxFrames(parseInt(e.target.value))}
                  disabled={isProcessing}
                  className="accent-accent"
                />
              </div>
            </div>
          )}

          {/* Error and Status Displays */}
          {fileError && (
            <div className="p-3 rounded bg-status-critical/10 border border-status-critical/30 text-status-critical text-[11px] flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">warning</span>
              <span>{fileError}</span>
            </div>
          )}

          {errorMessage && (
            <div className="p-3 rounded bg-status-critical/10 border border-status-critical/30 text-status-critical text-[11px] flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">error</span>
              <span>{errorMessage}</span>
            </div>
          )}

          {isProcessing && (
            <div className="p-3 rounded bg-status-ai/10 border border-status-ai/20 text-status-ai text-[11px] space-y-2">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
                <span className="font-semibold tracking-wide">{statusMessage}</span>
              </div>
              {progressPercent > 0 && (
                <div className="w-full bg-graphite rounded-full h-1.5 overflow-hidden border border-white/[0.08]">
                  <div
                    className="bg-accent h-full transition-all duration-300 ease-out"
                    style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="h-14 px-6 flex items-center justify-between border-t border-white/[0.08] bg-[#0B0F14]">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-1.5 rounded border border-white/[0.1] text-muted hover:text-paper transition-all disabled:opacity-40"
          >
            CANCEL
          </button>

          <button
            onClick={handleExecute}
            disabled={isProcessing}
            className="px-5 py-1.5 rounded bg-accent text-graphite font-bold tracking-wider hover:bg-accent/90 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {isProcessing ? (
              <>
                <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
                <span>PROCESSING...</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[16px]">play_arrow</span>
                <span>EXECUTE INFERENCE</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
