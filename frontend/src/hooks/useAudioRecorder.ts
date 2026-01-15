/**
 * Web Audio API Recorder Hook
 * Replaces Rust cpal audio capture
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { createAudioStreamWS } from '@/lib/websocket';
import type { TranscriptUpdate } from '@/lib/api';

export interface AudioRecorderOptions {
    meetingId: string;
    onTranscript?: (update: TranscriptUpdate) => void;
    onError?: (error: Error) => void;
    sampleRate?: number;
    channelCount?: number;
}

export interface AudioRecorderState {
    isRecording: boolean;
    isPaused: boolean;
    duration: number; // seconds
    audioLevel: number; // 0-1
}

export function useAudioRecorder() {
    const [state, setState] = useState<AudioRecorderState>({
        isRecording: false,
        isPaused: false,
        duration: 0,
        audioLevel: 0,
    });

    const mediaRecorder = useRef<MediaRecorder | null>(null);
    const mediaStream = useRef<MediaStream | null>(null);
    const audioChunks = useRef<Blob[]>([]);
    const wsRef = useRef<ReturnType<typeof createAudioStreamWS> | null>(null);
    const audioContext = useRef<AudioContext | null>(null);
    const analyser = useRef<AnalyserNode | null>(null);
    const durationInterval = useRef<NodeJS.Timeout | null>(null);
    const levelInterval = useRef<NodeJS.Timeout | null>(null);

    /**
     * Start recording
     * Replaces: invoke('start_recording')
     */
    const startRecording = useCallback(async (options: AudioRecorderOptions) => {
        try {
            // Request microphone permission
            mediaStream.current = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: options.channelCount || 1,
                    sampleRate: options.sampleRate || 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });

            // Setup audio context
            const sampleRate = options.sampleRate || 16000;
            audioContext.current = new AudioContext({ sampleRate });
            const source = audioContext.current.createMediaStreamSource(mediaStream.current);
            analyser.current = audioContext.current.createAnalyser();
            analyser.current.fftSize = 256;

            // Use ScriptProcessor for raw PCM access (bufferSize: 4096 is nice balance)
            const processor = audioContext.current.createScriptProcessor(4096, 1, 1);

            source.connect(analyser.current);
            analyser.current.connect(processor);
            processor.connect(audioContext.current.destination); // Needed for processing to happen

            // Connect WebSocket
            wsRef.current = createAudioStreamWS(options.meetingId);
            wsRef.current.connect();

            if (options.onTranscript) {
                wsRef.current.on('transcript-update', options.onTranscript);
            }

            // Buffer to hold audio samples until we have enough to send
            let chunks: Float32Array[] = [];
            let totalLength = 0;
            const CHUNK_DURATION_MS = 500; // Send every 0.5s (FAST DRAFT)
            const SAMPLES_PER_CHUNK = sampleRate * (CHUNK_DURATION_MS / 1000);

            processor.onaudioprocess = (e) => {
                if (!mediaStream.current || !wsRef.current) return;

                const inputData = e.inputBuffer.getChannelData(0);
                const bufferCopy = new Float32Array(inputData); // Copy buffer

                chunks.push(bufferCopy);
                totalLength += bufferCopy.length;

                // When we have enough data (~1s), send raw PCM
                if (totalLength >= SAMPLES_PER_CHUNK) {
                    const merged = mergeBuffers(chunks, totalLength);

                    // Convert Float32 to Int16 PCM
                    const pcmData = convertFloat32ToInt16(merged);

                    // Send to backend
                    if (wsRef.current.getStatus() === 'connected') {
                        wsRef.current.sendBinary(pcmData);
                    }

                    // Reset buffer
                    chunks = [];
                    totalLength = 0;
                }
            };

            // Store reference to close later
            (mediaRecorder.current as any) = processor;

            // Helpers
            const mergeBuffers = (buffers: Float32Array[], len: number) => {
                const result = new Float32Array(len);
                let offset = 0;
                for (const buf of buffers) {
                    result.set(buf, offset);
                    offset += buf.length;
                }
                return result;
            };

            const convertFloat32ToInt16 = (buffer: Float32Array): ArrayBuffer => {
                const l = buffer.length;
                const buf = new Int16Array(l);
                for (let i = 0; i < l; i++) {
                    const s = Math.max(-1, Math.min(1, buffer[i]));
                    // Convert to 16-bit PCM
                    buf[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                return buf.buffer;
            };

            // Start duration timer
            const startTime = Date.now();
            durationInterval.current = setInterval(() => {
                setState((prev) => ({
                    ...prev,
                    duration: (Date.now() - startTime) / 1000,
                }));
            }, 100);

            // Start audio level monitoring
            levelInterval.current = setInterval(() => {
                if (analyser.current) {
                    const dataArray = new Uint8Array(analyser.current.frequencyBinCount);
                    analyser.current.getByteFrequencyData(dataArray);
                    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
                    setState((prev) => ({
                        ...prev,
                        audioLevel: average / 255,
                    }));
                }
            }, 100);

            setState((prev) => ({
                ...prev,
                isRecording: true,
                isPaused: false,
            }));

            console.log('Recording started (WAV streaming)');
        } catch (error) {
            console.error('Failed to start recording:', error);
            options.onError?.(error as Error);
            throw error;
        }
    }, []);

    const stopRecording = useCallback(async (): Promise<Blob> => {
        if (!audioContext.current || audioContext.current.state === 'closed') {
            throw new Error('Recorder is not active');
        }

        try {
            // Disconnect processor
            const processor = (mediaRecorder.current as any);
            if (processor) {
                processor.disconnect();
                mediaRecorder.current = null;
            }

            // Stop media stream
            if (mediaStream.current) {
                mediaStream.current.getTracks().forEach((track) => track.stop());
                mediaStream.current = null;
            }

            // Send 'stop' signal to backend BEFORE closing
            if (wsRef.current && wsRef.current.getStatus() === 'connected') {
                console.log('📤 Sending stop signal to backend...');
                // Use helper's send(type, data) - don't double stringify!
                wsRef.current.send('stop', null);

                // Give backend time to process the signal before we disconnect
                await new Promise<void>(resolve => setTimeout(() => resolve(), 500));
            }

            // Close WebSocket
            if (wsRef.current) {
                wsRef.current.disconnect();
                wsRef.current = null;
            }

            // Close audio context
            if (audioContext.current) {
                audioContext.current.close();
                audioContext.current = null;
            }

            // Clear intervals
            if (durationInterval.current) {
                clearInterval(durationInterval.current);
                durationInterval.current = null;
            }
            if (levelInterval.current) {
                clearInterval(levelInterval.current);
                levelInterval.current = null;
            }

            setState({
                isRecording: false,
                isPaused: false,
                duration: 0,
                audioLevel: 0,
            });

            console.log('Recording stopped');

            // Return empty blob as we streamed everything
            return new Blob([], { type: 'audio/wav' });
        } catch (error) {
            console.error('Error stopping recording:', error);
            throw error;
        }
    }, []);

    /**
     * Pause recording
     */
    const pauseRecording = useCallback(() => {
        if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
            mediaRecorder.current.pause();
            setState((prev) => ({ ...prev, isPaused: true }));
        }
    }, []);

    /**
     * Resume recording
     */
    const resumeRecording = useCallback(() => {
        if (mediaRecorder.current && mediaRecorder.current.state === 'paused') {
            mediaRecorder.current.resume();
            setState((prev) => ({ ...prev, isPaused: false }));
        }
    }, []);

    /**
     * Cleanup on unmount
     */
    useEffect(() => {
        return () => {
            if (mediaRecorder.current) {
                // If it's a MediaRecorder (standard)
                if (typeof (mediaRecorder.current as any).stop === 'function' && (mediaRecorder.current as any).state !== 'inactive') {
                    (mediaRecorder.current as any).stop();
                }
                // If it's a ScriptProcessorNode (our custom raw streaming)
                else if (typeof (mediaRecorder.current as any).disconnect === 'function') {
                    (mediaRecorder.current as any).disconnect();
                }
            }
            if (mediaStream.current) {
                mediaStream.current.getTracks().forEach((track) => track.stop());
            }
            if (wsRef.current) {
                wsRef.current.disconnect();
            }
            if (audioContext.current) {
                audioContext.current.close();
            }
            if (durationInterval.current) {
                clearInterval(durationInterval.current);
            }
            if (levelInterval.current) {
                clearInterval(levelInterval.current);
            }
        };
    }, []);

    return {
        ...state,
        startRecording,
        stopRecording,
        pauseRecording,
        resumeRecording,
    };
}
