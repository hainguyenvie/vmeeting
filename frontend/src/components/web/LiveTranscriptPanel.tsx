/**
 * LiveTranscriptPanel Component
 * Displays transcripts in real-time as they arrive via WebSocket
 * Style: Teleprompter / Stream Mode (Focus + Fade)
 */

'use client'

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Note: We are using a direct WebSocket connection here for simplicity in this component
// instead of the global transcriptionWS to better control the lifecycle within this panel.

interface Transcript {
    transcript: string;
    timestamp: string;
    speaker?: string;
    meeting_id: string;
    is_final?: boolean;
}

interface LiveTranscriptPanelProps {
    meetingId: string;
    isRecording: boolean;
    onTranscriptReceived?: (transcript: Transcript) => void;
    variant?: 'card' | 'embedded';
}

export function LiveTranscriptPanel({
    meetingId,
    isRecording,
    onTranscriptReceived,
    variant = 'card'
}: LiveTranscriptPanelProps) {
    const [transcripts, setTranscripts] = useState<Transcript[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    // WebSocket Effect
    useEffect(() => {
        const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:5167';
        const ws = new WebSocket(`${wsUrl}/ws/transcripts/${meetingId}`);

        ws.onopen = () => {
            console.log('Connected to transcript stream');
            setIsConnected(true);
            ws.send(JSON.stringify({ type: 'connected', meeting_id: meetingId }));
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('WS Message:', data);

                // Handle 'live_transcript' (intermediate/VAD) - ONLY for local display
                if (data.type === 'live_transcript') {
                    const liveTranscript: Transcript = {
                        transcript: data.transcript,
                        timestamp: data.timestamp,
                        speaker: data.speaker,
                        meeting_id: data.meeting_id,
                        is_final: false,
                    };

                    // Add to local state ONLY (not passed to parent)
                    setTranscripts(prev => [...prev, liveTranscript]);
                }

                // Handle 'transcript' (final/DB) - Pass to parent for Saved Transcripts
                else if (data.type === 'transcript') {
                    const finalTranscript: Transcript = {
                        transcript: data.transcript,
                        timestamp: data.timestamp,
                        speaker: data.speaker,
                        meeting_id: data.meeting_id,
                        is_final: true,
                    };

                    // DO NOT add to local state (live panel should not show final transcripts)
                    // ONLY notify parent to update "Saved Transcripts"
                    if (onTranscriptReceived) {
                        onTranscriptReceived({
                            ...finalTranscript,
                            // @ts-ignore
                            audio_start_time: data.start_time,
                            // @ts-ignore
                            audio_end_time: data.end_time
                        });
                    }
                }

            } catch (error) {
                console.error('Error parsing WS message:', error);
            }
        };

        ws.onclose = () => setIsConnected(false);
        ws.onerror = (err) => console.error("WS Error:", err);

        return () => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        };
    }, [meetingId, onTranscriptReceived]);

    // Clear live transcripts when recording stops
    useEffect(() => {
        if (!isRecording) {
            setTranscripts([]);
        }
    }, [isRecording]);

    // Auto-scroll when new transcripts arrive
    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [transcripts]);

    const containerClasses = variant === 'card'
        ? "bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col h-[600px]"
        : "bg-transparent flex flex-col h-64"; // Increased height for better view

    return (
        <div className={containerClasses}>
            {/* Header - Only show for card variant or if needed */}
            {variant === 'card' && (
                <div className="p-4 border-b border-gray-200 flex justify-between items-center flex-shrink-0">
                    <h3 className="text-lg font-semibold text-gray-900">Live Stream</h3>
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <span className="text-sm text-gray-500">
                            {isConnected ? 'Live' : 'Connecting...'}
                        </span>
                    </div>
                </div>
            )}

            {/* Embedded Header - Simple Status */}
            {variant === 'embedded' && (
                <div className="pb-2 flex justify-between items-center flex-shrink-0">
                    <span className="text-sm font-medium text-gray-700">Live Transcripts</span>
                    <div className="flex items-center gap-2">
                        {isRecording && <span className="animate-pulse text-red-500 text-xs font-bold">● REC</span>}
                        <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <span className="text-xs text-gray-500">
                            {isConnected ? 'Ready' : 'Connecting...'}
                        </span>
                    </div>
                </div>
            )}

            {/* Stream Content Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6 relative scroll-smooth">
                {transcripts.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400">
                        {isRecording ? (
                            <p className="animate-pulse">Listening for speech...</p>
                        ) : (
                            <p>Ready to transcribe</p>
                        )}
                    </div>
                ) : (
                    <div className="flex flex-col justify-end min-h-full pb-2">
                        <AnimatePresence initial={false}>
                            {transcripts.map((item, index) => {
                                const isLatest = index === transcripts.length - 1;
                                const uniqueKey = `${item.timestamp}-${index}`;
                                return (
                                    <motion.div
                                        key={uniqueKey}
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{
                                            opacity: isLatest ? 1 : 0.4,
                                            y: 0,
                                            scale: isLatest ? 1 : 0.98
                                        }}
                                        transition={{ duration: 0.4, ease: "easeOut" }}
                                        className={`origin-left mb-4 ${isLatest ? 'mb-8' : ''}`}
                                    >
                                        <div className="flex items-baseline gap-3">
                                            <span className={`text-xs font-bold uppercase tracking-wider flex-shrink-0 w-16 text-right
                                                ${isLatest ? 'text-blue-600' : 'text-gray-400'}
                                             `}>
                                                {item.speaker ? item.speaker.replace('SPEAKER_', 'Spk ') : '...'}
                                            </span>
                                            <p className={`
                                                font-medium leading-relaxed transition-all duration-500
                                                ${isLatest ? 'text-xl text-gray-900' : 'text-base text-gray-500'}
                                             `}>
                                                {item.transcript}
                                            </p>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                        <div ref={bottomRef} />
                    </div>
                )}
            </div>

            {/* Visual Indicator of VAD/Silence Trigger */}
            {isRecording && (
                <div className="px-4 py-2 bg-gradient-to-t from-white via-white to-transparent h-12 flex items-end">
                    <p className="text-[10px] text-gray-400 w-full text-center">
                        Transcripts appear after pauses in speech
                    </p>
                </div>
            )}
        </div>
    );
}

