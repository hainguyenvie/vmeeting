"use client";

import { useState } from 'react';
import { Transcript } from '@/types';
import { RecordingControls } from '@/components/web/RecordingControls';
import { LiveTranscriptPanel } from '@/components/web/LiveTranscriptPanel';
import { FileContextUpload } from './FileContextUpload';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface EnhancedTranscriptPanelProps {
    meetingId: string;
    transcripts: Transcript[];
    customPrompt: string;
    onPromptChange: (value: string) => void;
    onTranscriptUpdate: (transcripts: Transcript[]) => void;
    onRecordingStateChange?: (isRecording: boolean) => void;
    onRefreshTranscripts?: () => Promise<void>;
}

export function EnhancedTranscriptPanel({
    meetingId,
    transcripts,
    customPrompt,
    onPromptChange,
    onTranscriptUpdate,
    onRecordingStateChange,
    onRefreshTranscripts
}: EnhancedTranscriptPanelProps) {
    const [isRecording, setIsRecording] = useState(false);
    const [recordingExpanded, setRecordingExpanded] = useState(true);
    const [transcriptsExpanded, setTranscriptsExpanded] = useState(true);
    const [contextExpanded, setContextExpanded] = useState(false);

    const handleRecordingStateChange = (recording: boolean) => {
        setIsRecording(recording);
        onRecordingStateChange?.(recording);
    };

    const handleRecordingComplete = async () => {
        console.log('Recording complete - refreshing transcripts from DB');
        setIsRecording(false);

        if (onRefreshTranscripts) {
            await onRefreshTranscripts();
        }
    };

    const handleNewTranscript = (newTranscript: any) => {
        console.log('⚡ New transcript received:', newTranscript);

        const isDuplicate = transcripts.some(
            t => t.timestamp === newTranscript.timestamp &&
                (t.text || (t as any).transcript) === (newTranscript.text || newTranscript.transcript)
        );

        if (!isDuplicate) {
            const updatedTranscripts = [...transcripts, {
                id: `live-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                meeting_id: newTranscript.meeting_id || meetingId,
                text: newTranscript.text || newTranscript.transcript || '',
                timestamp: newTranscript.timestamp,
                speaker: newTranscript.speaker,
                audio_start_time: newTranscript.audio_start_time,
                audio_end_time: newTranscript.audio_end_time,
                is_provisional: false
            }];

            onTranscriptUpdate(updatedTranscripts);
        }
    };

    const getSpeakerColor = (speaker?: string) => {
        if (!speaker) return 'bg-gray-400';
        const colors = [
            'bg-blue-500',
            'bg-green-500',
            'bg-purple-500',
            'bg-pink-500',
            'bg-yellow-500',
            'bg-indigo-500',
        ];
        const hash = speaker.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
        return colors[hash % colors.length];
    };

    const formatTimeRange = (startTime?: number, endTime?: number) => {
        if (startTime === undefined || endTime === undefined) return '--:-- - --:--';

        const formatTime = (seconds: number) => {
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        };

        return `${formatTime(startTime)} - ${formatTime(endTime)}`;
    };

    // Helper to get transcript text from either field
    const getTranscriptText = (transcript: any): string => {
        const text = transcript.text || transcript.transcript || '';
        console.log('🔍 Transcript text:', {
            hasText: !!transcript.text,
            hasTranscript: !!transcript.transcript,
            result: text,
            fullObject: transcript
        });
        return text;
    };

    return (
        <div className="flex flex-col w-2/3 border-r border-gray-200 bg-white relative h-full">
            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-y-auto" style={{ paddingBottom: contextExpanded ? '240px' : '60px' }}>

                {/* Recording Section - Collapsible */}
                <div className="border-b border-gray-200">
                    <div className="w-full px-4 py-3 flex items-center justify-between bg-gray-50">
                        <h2 className="text-sm font-semibold text-gray-900">Recording</h2>
                        <button
                            onClick={() => setRecordingExpanded(!recordingExpanded)}
                            className="p-1 hover:bg-gray-200 rounded transition-colors"
                            aria-label={recordingExpanded ? "Collapse recording" : "Expand recording"}
                        >
                            {recordingExpanded ? (
                                <ChevronDown className="w-4 h-4 text-gray-600" />
                            ) : (
                                <ChevronUp className="w-4 h-4 text-gray-600" />
                            )}
                        </button>
                    </div>

                    {recordingExpanded && (
                        <div className="pb-4">
                            <RecordingControls
                                meetingId={meetingId}
                                onRecordingStateChange={handleRecordingStateChange}
                                onTranscriptUpdate={handleNewTranscript}
                                onRecordingComplete={handleRecordingComplete}
                                onRefresh={onRefreshTranscripts}
                            >
                                <LiveTranscriptPanel
                                    meetingId={meetingId}
                                    isRecording={isRecording}
                                    variant="embedded"
                                    onTranscriptReceived={handleNewTranscript}
                                />
                            </RecordingControls>
                        </div>
                    )}
                </div>

                {/* Saved Transcripts Section - Collapsible with Scroll */}
                <div className="border-b border-gray-200 flex flex-col">
                    <div className="w-full px-4 py-3 flex items-center justify-between bg-gray-50">
                        <h2 className="text-sm font-semibold text-gray-900">
                            Saved Transcripts ({transcripts.length})
                        </h2>
                        <button
                            onClick={() => setTranscriptsExpanded(!transcriptsExpanded)}
                            className="p-1 hover:bg-gray-200 rounded transition-colors"
                            aria-label={transcriptsExpanded ? "Collapse transcripts" : "Expand transcripts"}
                        >
                            {transcriptsExpanded ? (
                                <ChevronDown className="w-4 h-4 text-gray-600" />
                            ) : (
                                <ChevronUp className="w-4 h-4 text-gray-600" />
                            )}
                        </button>
                    </div>

                    {transcriptsExpanded && (
                        <div className="px-4 pb-4 overflow-y-auto max-h-[500px]" id="transcript-scroll-container">
                            {transcripts.length === 0 ? (
                                <div className="text-center py-12 text-gray-500">
                                    <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <p className="mt-4 text-sm">No transcripts yet</p>
                                    <p className="text-xs mt-1">Start recording to see transcriptions</p>
                                </div>
                            ) : (
                                <div className="space-y-3 pt-2">
                                    {transcripts.map((transcript, index) => {
                                        const textContent = getTranscriptText(transcript);
                                        return (
                                            <div key={transcript.id || index} className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors" data-time={transcript.audio_start_time}>
                                                <div className="flex items-start gap-3">
                                                    {/* Speaker Avatar */}
                                                    <div className="flex-shrink-0 flex flex-col items-center gap-1">
                                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs shadow-sm ${getSpeakerColor(transcript.speaker)}`}>
                                                            {transcript.speaker ? transcript.speaker.slice(-2).toUpperCase() : '??'}
                                                        </div>
                                                        <span className="text-xs font-medium text-gray-600 text-center">
                                                            {transcript.speaker || 'Unknown'}
                                                        </span>
                                                    </div>

                                                    {/* Content */}
                                                    <div className="flex-1 min-w-0">
                                                        <div className="text-xs font-mono text-gray-500 mb-1">
                                                            {formatTimeRange(transcript.audio_start_time, transcript.audio_end_time)}
                                                        </div>
                                                        {textContent ? (
                                                            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                                                                {textContent}
                                                            </p>
                                                        ) : (
                                                            <p className="text-sm text-gray-400 italic">
                                                                No transcript text available
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Fixed Footer: Upload Context - Collapsible */}
            {!isRecording && (
                <div className="absolute bottom-0 left-0 right-0 bg-white border-t-2 border-gray-300 shadow-lg z-10">
                    <div className="w-full px-4 py-3 flex items-center justify-between bg-gray-50">
                        <label className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                            Add Context for AI Summary
                        </label>
                        <button
                            onClick={() => setContextExpanded(!contextExpanded)}
                            className="p-1 hover:bg-gray-200 rounded transition-colors"
                            aria-label={contextExpanded ? "Collapse context" : "Expand context"}
                        >
                            {contextExpanded ? (
                                <ChevronDown className="w-4 h-4 text-gray-600" />
                            ) : (
                                <ChevronUp className="w-4 h-4 text-gray-600" />
                            )}
                        </button>
                    </div>

                    {contextExpanded && (
                        <div className="px-4 pb-4 space-y-3 max-h-48 overflow-y-auto">
                            <textarea
                                placeholder="Add context: people involved, meeting overview, objective..."
                                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white shadow-sm resize-none"
                                rows={3}
                                value={customPrompt}
                                onChange={(e) => onPromptChange(e.target.value)}
                            />

                            <FileContextUpload
                                onFileContent={(content, fileName) => {
                                    const fileContext = `\n\n--- File: ${fileName} ---\n${content}\n--- End of ${fileName} ---\n`;
                                    onPromptChange(customPrompt + fileContext);
                                }}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
