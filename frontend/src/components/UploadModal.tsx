import React, { useState, useRef, useEffect, useCallback } from 'react';
import { analysisApi } from '../api';
import { normalizeVideoAnalysisResponse } from '../api/videoResultAdapter';
import { AERIONAnalysisResultData } from '../types';

export type UploadMode = 'drone_image' | 'satellite_image' | 'damage_pair' | 'border_video';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultMode?: UploadMode;
  onAnalysisSuccess: (result: AERIONAnalysisResultData, sourceMeta?: { preUrl?: string; postUrl?: string; imageUrl?: string; videoUrl?: string }) => void;
  onError?: (error: string) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  defaultMode = 'drone_image',
  onAnalysisSuccess,
  onError,
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

  // AbortController and active job tracking for safe interruption
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeJobIdRef = useRef<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const preInputRef = useRef<HTMLInputElement>(null);
  const postInputRef = useRef<HTMLInputElement>(null);

  // Safe Cancel and Close Handler
  const handleCancelOrClose = useCallback((isCloseAction: boolean) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (activeJobIdRef.current) {
      const jid = activeJobIdRef.current;
      activeJobIdRef.current = null;
      analysisApi.cancelJob(jid).catch((err) => {
        console.warn('Background job cancellation warning:', err);
      });
    }

    setIsProcessing(false);
    setProgressPercent(0);

    if (isCloseAction) {
      onClose();
    } else {
      setStatusMessage('');
      const cancelMsg = 'Operation was cancelled by user. Operational pipeline ready.';
      setErrorMessage(cancelMsg);
      onError?.(cancelMsg);
    }
  }, [onClose, onError]);

  // Fail-safe Escape key listener
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCancelOrClose(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleCancelOrClose]);

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
      if (pairValidationStatus.isCompatible === false || pairValidationStatus.status === 'PAIR_MISMATCH') {
        setFileError('Execution blocked: Bi-temporal imagery pair mismatch (PAIR_MISMATCH).');
        return;
      }
    } else {
      if (!selectedFile) {
        setFileError('Please select a file to analyze.');
        return;
      }
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsProcessing(true);
    setStatusMessage('ENCODING ASSET PAYLOAD...');

    try {
      if (mode === 'drone_image') {
        const b64 = await fileToBase64(selectedFile!);
        if (controller.signal.aborted) return;
        setStatusMessage('TRANSMITTING TO PERCEPTION INFERENCE ENGINE (YOLOv8)...');
        
        const resp = await analysisApi.analyzeImage({
          image_base64: b64,
          source_type: 'drone',
          mode: 'border',
          drone_model: droneModel,
          confidence_threshold: confidenceThreshold,
          run_intelligence: true,
        }, { signal: controller.signal });

        if (controller.signal.aborted) return;

        if (resp.success && resp.data) {
          setStatusMessage('INFERENCE COMPLETE. RENDERING TELEMETRY...');
          onAnalysisSuccess(resp.data, { imageUrl: filePreview || undefined });
          onClose();
        } else {
          throw new Error(typeof resp.error === 'string' ? resp.error : (resp.error as any)?.message || 'Inference execution failed.');
        }

      } else if (mode === 'satellite_image') {
        const b64 = await fileToBase64(selectedFile!);
        if (controller.signal.aborted) return;
        setStatusMessage('TRANSMITTING TO SATELLITE OBB DETECTOR (DOTA)...');
        
        const resp = await analysisApi.analyzeImage({
          image_base64: b64,
          source_type: 'satellite',
          mode: 'border',
          run_intelligence: true,
        }, { signal: controller.signal });

        if (controller.signal.aborted) return;

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
        if (controller.signal.aborted) return;
        setStatusMessage('TRANSMITTING TO BI-TEMPORAL SIAMESE RESNET-18 MODEL...');
        
        const resp = await analysisApi.analyzeDamage({
          before_base64: beforeB64,
          after_base64: afterB64,
          run_intelligence: true,
        }, { signal: controller.signal });

        if (controller.signal.aborted) return;

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
        if (controller.signal.aborted) return;
        setStatusMessage(`SUBMITTING VIDEO ANALYSIS JOB (STRIDE=${frameStride}, MAX=${maxFrames})...`);
        
        const idempotencyKey = `video_${Date.now()}_${selectedFile?.name || 'clip'}`;
        const submitResp = await analysisApi.submitBorderJob({
          video_base64: videoB64,
          frame_stride: frameStride,
          max_frames: maxFrames,
          generate_annotated_video: true,
          idempotency_key: idempotencyKey,
        }, { signal: controller.signal });

        if (controller.signal.aborted) return;

        if (!submitResp.success || !submitResp.data?.job_id) {
          // Fallback to direct analysis
          setStatusMessage('FALLBACK: EXECUTING DIRECT STREAMING INFERENCE...');
          const directResp = await analysisApi.analyzeBorderVideo({
            video_base64: videoB64,
            frame_stride: frameStride,
            max_frames: maxFrames,
          }, { signal: controller.signal });
          
          if (controller.signal.aborted) return;

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
        activeJobIdRef.current = jobId;
        setStatusMessage(`JOB ${jobId.substring(0, 8)} SUBMITTED. QUEUED FOR PIPELINE EXECUTION...`);

        // Poll job status with cancellation check
        const maxPollAttempts = 120;
        let attempts = 0;
        let jobCompleted = false;

        while (attempts < maxPollAttempts && !jobCompleted && !controller.signal.aborted) {
          await new Promise((res) => setTimeout(res, 1000));
          if (controller.signal.aborted) return;
          attempts++;

          try {
            const statusResp = await analysisApi.getJobStatus(jobId, { signal: controller.signal });
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
              } else if (job.status === 'CANCELLED' || job.status === 'cancelled') {
                throw new Error('Analysis job was cancelled.');
              } else if (job.status === 'FAILED' || job.status === 'PROCESSING_FAILED' || job.status === 'failed') {
                throw new Error(job.error || `Analysis job failed with status: ${job.status}`);
              }
            }
          } catch (pollErr: any) {
            if (controller.signal.aborted) return;
            if (pollErr.message && (pollErr.message.includes('failed') || pollErr.message.includes('cancelled'))) {
              throw pollErr;
            }
          }
        }

        if (!jobCompleted && !controller.signal.aborted) {
          throw new Error('Video analysis timed out waiting for pipeline completion. Job may still be running in background.');
        }
      }
    } catch (err: any) {
      const finalMsg =
        err.name === 'AbortError' || err.message?.includes('aborted') || controller.signal.aborted
          ? 'Operation was cancelled by user.'
          : (err.message || 'Operation failed during backend execution.');
      setErrorMessage(finalMsg);
      onError?.(finalMsg);
    } finally {
      setIsProcessing(false);
      setProgressPercent(0);
      abortControllerRef.current = null;
      activeJobIdRef.current = null;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          handleCancelOrClose(true);
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div className="w-full max-w-2xl bg-white border border-slate-200/80 rounded-xl shadow-floating overflow-hidden flex flex-col font-sans text-xs text-slate-800 animate-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="h-14 px-6 flex items-center justify-between border-b border-slate-200 bg-slate-50/80 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-sky-100 flex items-center justify-center text-accent">
              <span className="material-symbols-outlined text-[20px]">upload_file</span>
            </div>
            <div>
              <h2 id="upload-modal-title" className="text-slate-800 font-bold tracking-wide uppercase text-sm font-mono">
                INGEST OPERATIONAL ASSET
              </h2>
              <p className="text-[11px] text-slate-500 font-mono">
                ZERO-DEPENDENCY PERCEPTION & SITUATION TELEMETRY
              </p>
            </div>
          </div>
          <button
            onClick={() => handleCancelOrClose(true)}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Close modal (Escape)"
            aria-label="Close modal"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 flex flex-col gap-5 overflow-y-auto max-h-[75vh] custom-scrollbar bg-white">
          {/* Mode Selector Tabs */}
          <div className="grid grid-cols-4 gap-2.5 pb-2">
            <button
              onClick={() => { setMode('drone_image'); setSelectedFile(null); setFilePreview(null); }}
              disabled={isProcessing}
              className={`py-2.5 px-3 rounded-lg flex flex-col items-center gap-1.5 border transition-all ${
                mode === 'drone_image'
                  ? 'border-accent bg-sky-50/80 text-accent font-semibold shadow-sm'
                  : 'border-slate-200 bg-slate-50/60 text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              } disabled:opacity-50`}
            >
              <span className="material-symbols-outlined text-[20px]">flight</span>
              <span className="text-[10px] tracking-wide font-mono">DRONE AERIAL</span>
            </button>

            <button
              onClick={() => { setMode('satellite_image'); setSelectedFile(null); setFilePreview(null); }}
              disabled={isProcessing}
              className={`py-2.5 px-3 rounded-lg flex flex-col items-center gap-1.5 border transition-all ${
                mode === 'satellite_image'
                  ? 'border-accent bg-sky-50/80 text-accent font-semibold shadow-sm'
                  : 'border-slate-200 bg-slate-50/60 text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              } disabled:opacity-50`}
            >
              <span className="material-symbols-outlined text-[20px]">satellite_alt</span>
              <span className="text-[10px] tracking-wide font-mono">SATELLITE OBB</span>
            </button>

            <button
              onClick={() => { setMode('damage_pair'); }}
              disabled={isProcessing}
              className={`py-2.5 px-3 rounded-lg flex flex-col items-center gap-1.5 border transition-all ${
                mode === 'damage_pair'
                  ? 'border-accent bg-sky-50/80 text-accent font-semibold shadow-sm'
                  : 'border-slate-200 bg-slate-50/60 text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              } disabled:opacity-50`}
            >
              <span className="material-symbols-outlined text-[20px]">compare</span>
              <span className="text-[10px] tracking-wide font-mono">DAMAGE PAIR</span>
            </button>

            <button
              onClick={() => { setMode('border_video'); setSelectedFile(null); setFilePreview(null); }}
              disabled={isProcessing}
              className={`py-2.5 px-3 rounded-lg flex flex-col items-center gap-1.5 border transition-all ${
                mode === 'border_video'
                  ? 'border-accent bg-sky-50/80 text-accent font-semibold shadow-sm'
                  : 'border-slate-200 bg-slate-50/60 text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              } disabled:opacity-50`}
            >
              <span className="material-symbols-outlined text-[20px]">videocam</span>
              <span className="text-[10px] tracking-wide font-mono">VIDEO ANALYSIS</span>
            </button>
          </div>

          {/* Mode Description */}
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-[11px] text-slate-600 flex items-start gap-2.5">
            <span className="material-symbols-outlined text-accent text-[18px] mt-0.5 shrink-0">info</span>
            <div className="font-mono leading-relaxed">
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
                  <span className="text-[11px] font-mono text-slate-600 uppercase font-semibold">PRE-DISASTER BASELINE (T0)</span>
                  <input
                    type="file"
                    ref={preInputRef}
                    onChange={handlePreFileChange}
                    accept="image/*"
                    className="hidden"
                  />
                  <div
                    onClick={() => !isProcessing && preInputRef.current?.click()}
                    className="h-36 border-2 border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center p-3 cursor-pointer hover:border-accent bg-slate-50/60 hover:bg-slate-50 transition-all overflow-hidden relative shadow-sm"
                  >
                    {prePreview ? (
                      <img src={prePreview} alt="Pre-Disaster" className="w-full h-full object-cover rounded" />
                    ) : (
                      <div className="flex flex-col items-center text-center gap-1.5 text-slate-400">
                        <span className="material-symbols-outlined text-[28px] text-slate-400">image</span>
                        <span className="text-[11px] font-medium text-slate-600 font-mono">SELECT T0 IMAGE</span>
                        <span className="text-[10px] text-slate-400 font-mono">Max 15MB (JPG/PNG)</span>
                      </div>
                    )}
                  </div>
                  {preFile && <span className="text-[10px] text-slate-700 font-mono truncate">{preFile.name}</span>}
                </div>

                {/* Post-disaster box */}
                <div className="flex flex-col gap-2">
                  <span className="text-[11px] font-mono text-slate-600 uppercase font-semibold">POST-DISASTER SCENE (T1)</span>
                  <input
                    type="file"
                    ref={postInputRef}
                    onChange={handlePostFileChange}
                    accept="image/*"
                    className="hidden"
                  />
                  <div
                    onClick={() => !isProcessing && postInputRef.current?.click()}
                    className="h-36 border-2 border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center p-3 cursor-pointer hover:border-accent bg-slate-50/60 hover:bg-slate-50 transition-all overflow-hidden relative shadow-sm"
                  >
                    {postPreview ? (
                      <img src={postPreview} alt="Post-Disaster" className="w-full h-full object-cover rounded" />
                    ) : (
                      <div className="flex flex-col items-center text-center gap-1.5 text-slate-400">
                        <span className="material-symbols-outlined text-[28px] text-slate-400">image</span>
                        <span className="text-[11px] font-medium text-slate-600 font-mono">SELECT T1 IMAGE</span>
                        <span className="text-[10px] text-slate-400 font-mono">Max 15MB (JPG/PNG)</span>
                      </div>
                    )}
                  </div>
                  {postFile && <span className="text-[10px] text-slate-700 font-mono truncate">{postFile.name}</span>}
                </div>
              </div>

              {/* Bi-Temporal Pair Preflight Validation Card */}
              {preFile && postFile && (
                <div className={`p-3 rounded-lg border text-[11px] flex flex-col gap-1 transition-all ${
                  pairValidationStatus.isValidating
                    ? 'bg-slate-50 border-slate-200 text-slate-600'
                    : pairValidationStatus.isCompatible === true
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                    : pairValidationStatus.isCompatible === false
                    ? 'bg-rose-50 border-rose-300 text-rose-800'
                    : 'bg-slate-50 border-slate-200 text-slate-600'
                }`}>
                  <div className="flex items-center justify-between font-mono font-bold tracking-wider">
                    <div className="flex items-center gap-2">
                      <span className={`material-symbols-outlined text-[18px] ${pairValidationStatus.isValidating ? 'animate-spin' : ''}`}>
                        {pairValidationStatus.isValidating ? 'sync' : pairValidationStatus.isCompatible ? 'check_circle' : 'cancel'}
                      </span>
                      <span>PAIR VALIDATION: {pairValidationStatus.isValidating ? 'EVALUATING SCENE CORRESPONDENCE...' : pairValidationStatus.isCompatible ? 'STRUCTURALLY_COMPATIBLE' : (pairValidationStatus.status || 'PAIR_MISMATCH')}</span>
                    </div>
                  </div>
                  {pairValidationStatus.isValidating ? (
                    <span className="text-[10px] text-slate-500 font-mono">Analyzing geometric keypoint correspondence, phase correlation & reliable GPS...</span>
                  ) : pairValidationStatus.isCompatible === true ? (
                    <span className="text-[10px] text-emerald-700 font-mono">✓ Same-scene evidence confirmed. Valid bi-temporal pair for change detection.</span>
                  ) : pairValidationStatus.isCompatible === false ? (
                    <div className="flex flex-col gap-0.5 text-[10px] font-mono">
                      <span className="font-semibold text-rose-700">✕ Incompatible imagery pair: {pairValidationStatus.reason || 'Insufficient scene correspondence'}.</span>
                      <span className="text-slate-600">Siamese change detection will be halted server-side to prevent false damage attribution.</span>
                    </div>
                  ) : null}
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-mono text-slate-600 uppercase font-semibold">
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
                className="h-44 border-2 border-dashed border-slate-300 rounded-lg flex flex-col items-center justify-center p-4 cursor-pointer hover:border-accent bg-slate-50/60 hover:bg-slate-50 transition-all overflow-hidden relative shadow-sm"
              >
                {filePreview && mode !== 'border_video' ? (
                  <img src={filePreview} alt="Selected" className="w-full h-full object-contain rounded" />
                ) : selectedFile && mode === 'border_video' ? (
                  <div className="flex flex-col items-center gap-2 text-accent">
                    <span className="material-symbols-outlined text-[36px]">videocam</span>
                    <span className="text-slate-800 text-xs font-mono font-medium">{selectedFile.name}</span>
                    <span className="text-[11px] text-slate-500 font-mono">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-center gap-2 text-slate-400">
                    <span className="material-symbols-outlined text-[36px] text-slate-400">
                      {mode === 'border_video' ? 'movie' : 'add_photo_alternate'}
                    </span>
                    <span className="text-xs font-medium text-slate-700 font-mono">CLICK TO CHOOSE FILE</span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {mode === 'border_video' ? 'MP4 / AVI (Max 25MB)' : 'JPG / PNG / TIFF (Max 15MB)'}
                    </span>
                  </div>
                )}
              </div>
              {selectedFile && mode !== 'border_video' && (
                <span className="text-[10px] text-slate-700 font-mono truncate">{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
              )}
            </div>
          )}

          {/* Model & Runtime Parameters */}
          {mode === 'drone_image' && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-200">
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-mono text-slate-600 uppercase font-semibold">DRONE DETECTOR MODEL</label>
                <select
                  value={droneModel}
                  onChange={(e) => setDroneModel(e.target.value as any)}
                  disabled={isProcessing}
                  className="bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-slate-800 text-xs outline-none focus:border-accent shadow-sm"
                >
                  <option value="visdrone_only">VisDrone YOLOv8 (Frozen baseline)</option>
                  <option value="unified">Unified Drone 20ep (Multi-dataset)</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-600 uppercase font-semibold">
                  <span>CONFIDENCE THRESHOLD</span>
                  <span className="text-accent font-bold">{(confidenceThreshold * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0.10"
                  max="0.80"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  disabled={isProcessing}
                  className="accent-accent mt-1.5"
                />
              </div>
            </div>
          )}

          {mode === 'border_video' && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-200">
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-600 uppercase font-semibold">
                  <span>FRAME STRIDE</span>
                  <span className="text-accent font-bold">{frameStride}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="15"
                  step="1"
                  value={frameStride}
                  onChange={(e) => setFrameStride(parseInt(e.target.value))}
                  disabled={isProcessing}
                  className="accent-accent mt-1.5"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center text-[10px] font-mono text-slate-600 uppercase font-semibold">
                  <span>MAX FRAMES TO PROCESS</span>
                  <span className="text-accent font-bold">{maxFrames}</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="10"
                  value={maxFrames}
                  onChange={(e) => setMaxFrames(parseInt(e.target.value))}
                  disabled={isProcessing}
                  className="accent-accent mt-1.5"
                />
              </div>
            </div>
          )}

          {/* Error and Status Displays */}
          {fileError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-300 text-rose-800 text-[11px] font-mono flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-rose-600 shrink-0">warning</span>
              <span>{fileError}</span>
            </div>
          )}

          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-300 text-rose-800 text-[11px] font-mono flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-rose-600 shrink-0">error</span>
                <span>{errorMessage}</span>
              </div>
              <button
                onClick={() => setErrorMessage(null)}
                className="text-rose-500 hover:text-rose-800 text-[10px] font-bold underline"
              >
                DISMISS
              </button>
            </div>
          )}

          {isProcessing && (
            <div className="p-3.5 rounded-lg bg-sky-50 border border-sky-200 text-sky-900 text-[11px] font-mono space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-sky-600 animate-spin">progress_activity</span>
                  <span className="font-semibold tracking-wide">{statusMessage}</span>
                </div>
                <span className="text-[10px] font-bold text-sky-700 bg-sky-100 px-2 py-0.5 rounded">
                  {progressPercent > 0 ? `${progressPercent}%` : 'IN PROGRESS'}
                </span>
              </div>
              {progressPercent > 0 && (
                <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
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
        <div className="h-16 px-6 flex items-center justify-between border-t border-slate-200 bg-slate-50">
          {/* Always-interactive Cancel / Abort button */}
          {isProcessing ? (
            <button
              onClick={() => handleCancelOrClose(false)}
              className="px-4 py-2 rounded-lg border border-rose-300 bg-rose-50 text-rose-700 font-mono font-bold hover:bg-rose-100 transition-all flex items-center gap-2 cursor-pointer shadow-sm active:scale-95"
              title="Interrupt and abort in-flight inference safely"
            >
              <span className="material-symbols-outlined text-[16px] text-rose-600">cancel</span>
              <span>CANCEL INFERENCE</span>
            </button>
          ) : (
            <button
              onClick={() => handleCancelOrClose(true)}
              className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 font-mono hover:bg-slate-100 transition-all cursor-pointer shadow-sm active:scale-95"
            >
              CANCEL
            </button>
          )}

          <button
            onClick={handleExecute}
            disabled={isProcessing || (mode === 'damage_pair' && (pairValidationStatus.isCompatible === false || pairValidationStatus.isValidating))}
            className="px-5 py-2 rounded-lg bg-accent text-white font-mono font-bold tracking-wider hover:bg-accent-hover transition-all flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm active:scale-95 cursor-pointer"
            title={
              mode === 'damage_pair' && pairValidationStatus.isCompatible === false
                ? 'Execution blocked: Bi-temporal imagery pair mismatch (PAIR_MISMATCH)'
                : undefined
            }
          >
            {isProcessing ? (
              <>
                <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
                <span>PROCESSING...</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                <span>EXECUTE INFERENCE</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
