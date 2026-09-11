import React, { useState, useRef } from 'react';
import { analysisApi } from '../api';
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

  // Parameter options
  const [droneModel, setDroneModel] = useState<'visdrone_only' | 'unified'>('visdrone_only');
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.25);
  const [maxFrames, setMaxFrames] = useState<number>(30);
  const [frameStride, setFrameStride] = useState<number>(5);

  // Upload/Processing state
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const preInputRef = useRef<HTMLInputElement>(null);
  const postInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const MAX_IMAGE_SIZE_MB = 15;
  const MAX_VIDEO_SIZE_MB = 100;

  const validateFile = (file: File, isVideo: boolean = false): boolean => {
    setFileError(null);
    const maxBytes = (isVideo ? MAX_VIDEO_SIZE_MB : MAX_IMAGE_SIZE_MB) * 1024 * 1024;
    if (file.size > maxBytes) {
      setFileError(`File size exceeds ${isVideo ? MAX_VIDEO_SIZE_MB : MAX_IMAGE_SIZE_MB}MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
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
          setStatusMessage('DAMAGE MAP COMPUTED. RENDERING...');
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
        setStatusMessage(`PROCESSING VIDEO FRAMES (STRIDE=${frameStride}, MAX=${maxFrames})...`);
        const resp = await analysisApi.analyzeBorderVideo({
          video_base64: videoB64,
          frame_stride: frameStride,
          max_frames: maxFrames,
        });

        if (resp.success && resp.data) {
          setStatusMessage('VIDEO ANALYSIS COMPLETE...');
          const reportData = resp.data.report || resp.data;
          // Attach video artifact metadata if present
          if (resp.data.annotated_video_artifact) {
            reportData.annotated_video_artifact = resp.data.annotated_video_artifact;
          }
          const rawVideoUrl = selectedFile ? URL.createObjectURL(selectedFile) : undefined;
          onAnalysisSuccess(reportData, {
            imageUrl: undefined,
            videoUrl: rawVideoUrl,
          });
          onClose();
        } else {
          throw new Error(typeof resp.error === 'string' ? resp.error : (resp.error as any)?.message || 'Video analysis failed.');
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Operation failed during backend execution.');
    } finally {
      setIsProcessing(false);
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
                      {mode === 'border_video' ? 'MP4 / AVI (Max 100MB)' : 'JPG / PNG / TIFF (Max 15MB)'}
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
            <div className="p-3 rounded bg-status-ai/10 border border-status-ai/20 text-status-ai text-[11px] flex items-center gap-2 animate-pulse">
              <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
              <span>{statusMessage}</span>
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
