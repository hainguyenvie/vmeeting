/**
 * LiveTranscriptPanel Component
 * Displays transcripts in real-time as they arrive via WebSocket
 */

'use client'

import { useState, useRef, useEffect } from 'react';
// Helper or import
const formatTime = (timestamp: string) => {
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('vi-VN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return timestamp;
    }
};
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
    const [pendingTranscript, setPendingTranscript] = useState<string>("");
    const [isConnected, setIsConnected] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const previewTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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

                // 1. Handle PREVIEW (Transient)
                if (data.type === 'preview') {
                    if (data.transcript && data.transcript.trim()) {
                        setPendingTranscript(data.transcript);
                        if (previewTimeoutRef.current) clearTimeout(previewTimeoutRef.current);
                        previewTimeoutRef.current = setTimeout(() => {
                            setPendingTranscript("");
                        }, 3000);
                    }
                }

                // 2. Handle FINAL TRANSCRIPT (Persistent)
                else if (data.type === 'transcript') {
                    const newTranscript: Transcript = {
                        transcript: data.transcript,
                        timestamp: data.timestamp,
                        speaker: data.speaker,
                        meeting_id: data.meeting_id,
                        is_final: true,
                        // Add start/end time if available in data, though interface here doesn't have it yet? 
                        // Actually LiveTranscriptPanel local Transcript interface doesn't have start/end.
                        // But we pass 'data' which has it.
                    };

                    // Update local state (for live view) -> REMOVED as per user request (don't show final here)
                    // setTranscripts(prev => [...prev, newTranscript]); 

                    // Notify parent to update "Saved Transcripts"
                    if (onTranscriptReceived) {
                        // Pass raw data or enriched object. Parent (page.tsx) handles the full structure.
                        // We should pass 'data' because it has start_time/end_time which might not be in Transcript type here.
                        onTranscriptReceived({
                            ...newTranscript,
                            // @ts-ignore
                            audio_start_time: data.start_time,
                            // @ts-ignore
                            audio_end_time: data.end_time
                        });
                    }
                }

                // Auto-scroll logic happens here or via separate effect
                setTimeout(() => {
                    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
                }, 100);

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

    const containerClasses = variant === 'card'
        ? "bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col h-[600px]"
        : "bg-transparent flex flex-col h-48"; // Embedded height: h-48 (12rem / 192px)

    return (
        <div className={containerClasses}>
            {/* Header - Only show for card variant or if needed */}
            {variant === 'card' && (
                <div className="p-4 border-b border-gray-200 flex justify-between items-center flex-shrink-0">
                    <h3 className="text-lg font-semibold text-gray-900">Live Transcripts</h3>
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <span className="text-sm text-gray-500">
                            {isConnected ? 'Connected' : 'Waiting...'}
                        </span>
                        <span className="text-xs text-gray-400 ml-2">
                            {transcripts.length} segments
                        </span>
                    </div>
                </div>
            )}

            {/* Embedded Header - Simple Status */}
            {variant === 'embedded' && (
                <div className="pb-2 flex justify-between items-center flex-shrink-0">
                    <span className="text-sm font-medium text-gray-700">Live Transcripts</span>
                    <div className="flex items-center gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <span className="text-xs text-gray-500">
                            {isConnected ? 'Ready' : 'Connecting...'}
                        </span>
                    </div>
                </div>
            )}

            {/* Transcript List */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4"
            >
                {transcripts.length === 0 && !pendingTranscript ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400">
                        <div className="text-center">
                            <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                            </svg>
                            {isRecording ? (
                                <>
                                    <p className="font-medium text-gray-500">Listening...</p>
                                    <p className="text-sm mt-1">Start speaking to see live transcripts</p>
                                </>
                            ) : (
                                <>
                                    <p className="font-medium text-gray-500">Ready to record</p>
                                    <p className="text-sm mt-1">Start recording to see live transcripts</p>
                                </>
                            )}
                        </div>
                    </div>
                ) : (
                    <>
                        {/* Final Transcripts */}
                        {transcripts.map((item, index) => (
                            <div
                                key={index}
                                className="bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition border border-transparent hover:border-gray-200"
                            >
                                <div className="flex items-start gap-4">
                                    {/* Timestamp */}
                                    <div className="flex-shrink-0 text-xs text-gray-400 font-mono w-16 pt-1">
                                        {formatTime(item.timestamp)}
                                    </div>

                                    {/* Speaker Avatar */}
                                    <div className="flex-shrink-0">
                                        <div className={`
                                            w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold shadow-sm
                                            ${item.speaker?.includes('00') ? 'bg-blue-100 text-blue-700' :
                                                item.speaker?.includes('01') ? 'bg-green-100 text-green-700' :
                                                    item.speaker?.includes('02') ? 'bg-purple-100 text-purple-700' :
                                                        'bg-gray-200 text-gray-700'}
                                         `}>
                                            {item.speaker ? item.speaker.replace('SPEAKER_', '') : '?'}
                                        </div>
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1 min-w-0">
                                        <div className="text-xs font-semibold text-gray-500 mb-0.5">
                                            {item.speaker || "Unknown"}
                                        </div>
                                        <p className="text-gray-900 text-base leading-relaxed break-words">
                                            {item.transcript}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ))}

                        {/* Pending Draft Bubble */}
                        {pendingTranscript && (
                            <div className="bg-white border-2 border-dashed border-gray-200 rounded-lg p-4">
                                <div className="flex items-start gap-4">
                                    <div className="flex-shrink-0 text-xs text-gray-300 font-mono w-16 pt-1">
                                        ...
                                    </div>
                                    <div className="flex-shrink-0">
                                        <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-400 text-xs">
                                            ...
                                        </div>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-xs font-semibold text-gray-400 mb-0.5">
                                            Typing...
                                        </div>
                                        <p className="text-gray-500 italic text-base leading-relaxed break-words animate-pulse">
                                            {pendingTranscript}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </>
                )}
            </div>

            {/* Footer */}
            {isRecording && (
                <div className="p-2 bg-blue-50 border-t border-blue-100 text-xs text-blue-800 flex items-center gap-2 flex-shrink-0">
                    <span>💡 Tip: Speak clearly into your microphone. Transcripts appear every 3 seconds.</span>
                </div>
            )}
        </div>
    );
}
