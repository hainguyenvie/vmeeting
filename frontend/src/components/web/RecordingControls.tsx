/**
 * Recording Controls Component for Web Version
 * Uses Web Audio API for recording
 */

'use client'

import { useState, useEffect } from 'react';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';
import { audioAPI } from '@/lib/api';

interface RecordingControlsProps {
    meetingId: string;
    onRecordingStateChange?: (isRecording: boolean) => void;
    onTranscriptUpdate?: (transcript: any) => void;
    onRecordingComplete?: () => void;
    onRefresh?: () => void;
    children?: React.ReactNode;
}

export function RecordingControls({
    meetingId,
    onRecordingStateChange,
    onTranscriptUpdate,
    onRecordingComplete,
    onRefresh,
    children
}: RecordingControlsProps) {
    const [permissionGranted, setPermissionGranted] = useState<boolean | null>(null);
    const [error, setError] = useState<string | null>(null);

    const {
        isRecording,
        isPaused,
        duration,
        audioLevel,
        startRecording,
        stopRecording,
        pauseRecording,
        resumeRecording
    } = useAudioRecorder();

    const [model, setModel] = useState<string>('phowhisper');
    const [isSwitching, setIsSwitching] = useState(false);

    useEffect(() => {
        // Check current model
        const whisperUrl = process.env.NEXT_PUBLIC_WHISPER_URL || 'http://localhost:8178';
        fetch(`${whisperUrl}/current_model`)
            .then(res => res.json())
            .then(data => setModel(data.current_model || 'phowhisper'))
            .catch(err => console.error("Failed to check model", err));
    }, []);

    const handleModelChange = async (newModel: string) => {
        if (isRecording) return;
        setIsSwitching(true);
        try {
            const whisperUrl = process.env.NEXT_PUBLIC_WHISPER_URL || 'http://localhost:8178';
            const res = await fetch(`${whisperUrl}/switch_model?model_id=${newModel}`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'ok') {
                setModel(newModel);
            } else {
                setError("Failed to switch model: " + data.message);
            }
        } catch (e: any) {
            setError("Error switching model: " + e.message);
        } finally {
            setIsSwitching(false);
        }
    };

    const handleStartRecording = async () => {
        try {
            setError(null);
            await startRecording({
                meetingId,
                onTranscript: onTranscriptUpdate, // We might want to disable this for full pipeline mode? user said "không làm gì cả"
                onError: (err) => {
                    console.error('Recording error:', err);
                    setError(err.message);
                }
            });
            setPermissionGranted(true);
            onRecordingStateChange?.(true);
        } catch (err: any) {
            console.error('Failed to start recording:', err);
            setError(err.message || 'Failed to start recording');

            if (err.name === 'NotAllowedError') {
                setPermissionGranted(false);
                setError('Microphone permission denied. Please allow access in browser settings.');
            }
        }
    };

    const handleStopRecording = async () => {
        try {
            await stopRecording();
            console.log('Recording stopped - audio already streamed via WebSocket');
            onRecordingStateChange?.(false);
            onRecordingComplete?.();
        } catch (err: any) {
            console.error('Failed to stop recording:', err);
            setError(err.message || 'Failed to stop recording');
        }
    };

    const formatDuration = (seconds: number): string => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    // ... (formatDuration) ...

    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useState<HTMLInputElement | null>(null); // Use Ref actually

    // Helper for file input trigger
    const triggerFileUpload = () => {
        document.getElementById('audio-upload-input')?.click();
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        setError(null);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const uploadUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5167';
            // Note: endpoint is /ws/upload/{meetingId}
            const res = await fetch(`${uploadUrl}/ws/upload/${meetingId}`, {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();
            if (res.ok) {
                console.log("Upload success:", data);
                // Backend broadcasts transcripts, UI updates automatically via WebSocket
            } else {
                setError("Upload failed: " + (data.message || res.statusText));
            }
        } catch (err: any) {
            console.error("Upload error:", err);
            setError("Upload error: " + err.message);
        } finally {
            setIsUploading(false);
            // Reset input
            if (e.target) e.target.value = '';

            // Trigger refresh with polling to ensure all segments are loaded
            if (onRefresh) {
                console.log("Triggering refresh with polling...");
                let lastCount = -1;
                let attempts = 0;
                const maxAttempts = 10;

                const pollRefresh = async () => {
                    await onRefresh();
                    attempts++;

                    // Check again after a short delay
                    setTimeout(() => {
                        if (attempts < maxAttempts) {
                            pollRefresh();
                        }
                    }, 800); // Poll every 800ms for up to 8 seconds
                };

                // Start polling after initial delay
                setTimeout(pollRefresh, 500);
            }
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <input
                id="audio-upload-input"
                type="file"
                accept="audio/*,video/*"
                className="hidden"
                onChange={handleFileUpload}
            />

            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Recording</h3>
                <div className="flex items-center gap-2">
                    {isRecording && (
                        <span className="flex items-center gap-2 text-sm text-red-600 font-medium">
                            <span className="flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-red-500 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-600"></span>
                            </span>
                            REC
                        </span>
                    )}
                    {isUploading && (
                        <span className="flex items-center gap-2 text-sm text-blue-600 font-medium animate-pulse">
                            <svg className="animate-spin h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Processing File...
                        </span>
                    )}
                </div>
            </div>

            {/* Model Selector */}
            <div className="mb-6 p-3 bg-gray-50 rounded-lg flex items-center justify-between">
                <div className="flex items-center gap-2 flex-1">
                    <span className="text-sm font-medium text-gray-700">Model:</span>
                    <select
                        value={model}
                        onChange={(e) => handleModelChange(e.target.value)}
                        disabled={isRecording || isSwitching || isUploading}
                        className="block w-full max-w-[250px] rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-1.5"
                    >
                        <option value="phowhisper">PhoWhisper Medium (Accurate)</option>
                        <option value="zipformer">Zipformer 70k (Streaming)</option>
                    </select>
                </div>
                {isSwitching && <span className="text-xs text-blue-600 animate-pulse font-medium">Switching...</span>}
            </div>

            {/* Permission Warning */}
            {permissionGranted === false && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-800">
                        <strong>Microphone access denied.</strong> Please allow microphone permission in your browser settings.
                    </p>
                </div>
            )}

            {/* Error Display */}
            {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-800">{error}</p>
                </div>
            )}

            {/* Recording Status */}
            <div className="space-y-4">
                {/* Audio Level Meter */}
                {isRecording && (
                    <div className="space-y-2">
                        <label className="text-sm text-gray-600">Audio Level</label>
                        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 transition-all duration-150"
                                style={{ width: `${audioLevel * 100}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* Duration Display */}
                {isRecording && (
                    <div className="flex items-center gap-2 text-2xl font-mono text-gray-900">
                        <svg className="w-6 h-6 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                        </svg>
                        {formatDuration(duration)}
                    </div>
                )}

                {/* Controls */}
                <div className="flex gap-3">
                    {!isRecording ? (
                        <>
                            <button
                                onClick={handleStartRecording}
                                disabled={isUploading}
                                className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-medium shadow-sm ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
                                </svg>
                                Start Recording
                            </button>

                            <button
                                onClick={triggerFileUpload}
                                disabled={isUploading}
                                className={`flex-initial flex items-center justify-center gap-2 px-4 py-3 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium shadow-sm ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                title="Upload Audio File"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                </svg>
                                Upload
                            </button>
                        </>
                    ) : (
                        <>
                            {!isPaused ? (
                                <button
                                    onClick={pauseRecording}
                                    className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition font-medium"
                                >
                                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                    </svg>
                                    Pause
                                </button>
                            ) : (
                                <button
                                    onClick={resumeRecording}
                                    className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium"
                                >
                                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                                    </svg>
                                    Resume
                                </button>
                            )}

                            <button
                                onClick={handleStopRecording}
                                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition font-medium"
                            >
                                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                                </svg>
                                Stop & Save
                            </button>
                        </>
                    )}
                </div>

                {/* Info */}
                {!isRecording && !isUploading && (
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-800">
                            <strong>Tip:</strong> Make sure your microphone is connected and browser has permission to access it.
                        </p>
                    </div>
                )}
            </div>

            {/* Embedded Live Panel Slot */}
            {children && (
                <div className="mt-6 border-t border-gray-100 pt-6">
                    {children}
                </div>
            )}
        </div>
    );
}
