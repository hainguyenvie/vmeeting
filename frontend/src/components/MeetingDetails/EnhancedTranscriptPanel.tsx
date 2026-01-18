"use client";

import { useState, useCallback, useEffect } from 'react';
import { Transcript } from '@/types';
import { RecordingControls } from '@/components/web/RecordingControls';
import { LiveTranscriptPanel } from '@/components/web/LiveTranscriptPanel';
import { FileContextUpload } from './FileContextUpload';
import { ChevronDown, ChevronUp, Edit2, Trash2, X, Check } from 'lucide-react';
import { meetingsAPI } from '@/lib/api';
import { toast } from 'sonner';

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

    // Speaker Management State
    const [renameState, setRenameState] = useState<{ isOpen: boolean; oldName: string; newName: string }>({
        isOpen: false, oldName: '', newName: ''
    });
    const [mergeState, setMergeState] = useState<{ isOpen: boolean; fromSpeaker: string; toSpeaker: string }>({
        isOpen: false, fromSpeaker: '', toSpeaker: ''
    });

    // Unique speakers for merge dropdown
    const uniqueSpeakers = Array.from(new Set(transcripts.map(t => t.speaker))).filter(Boolean) as string[];

    const handleRenameClick = (speaker: string) => {
        setRenameState({ isOpen: true, oldName: speaker, newName: speaker });
    };

    const handleDeleteClick = (speaker: string) => {
        setMergeState({ isOpen: true, fromSpeaker: speaker, toSpeaker: '' });
    };

    const confirmRename = async () => {
        try {
            await meetingsAPI.renameSpeaker(meetingId, renameState.oldName, renameState.newName);
            toast.success('Speaker renamed successfully');
            setRenameState({ ...renameState, isOpen: false });
            if (onRefreshTranscripts) await onRefreshTranscripts();
        } catch (error) {
            console.error(error);
            toast.error('Failed to rename speaker');
        }
    };

    const confirmMerge = async () => {
        if (!mergeState.toSpeaker) {
            toast.error('Please select a target speaker');
            return;
        }
        try {
            await meetingsAPI.mergeSpeakers(meetingId, mergeState.fromSpeaker, mergeState.toSpeaker);
            toast.success('Speaker deleted and segments merged');
            setMergeState({ ...mergeState, isOpen: false });
            if (onRefreshTranscripts) await onRefreshTranscripts();
        } catch (error) {
            console.error(error);
            toast.error('Failed to merge speaker');
        }
    };

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

    // Use useCallback to prevent LiveTranscriptPanel re-renders / WS reconnects
    const handleNewTranscript = useCallback((newTranscript: any) => {
        // @ts-ignore - bypassing strict prop type to allow functional update if supported by parent state
        onTranscriptUpdate((prevTranscripts: any) => {
            // Check if prevTranscripts is actually an array (it should be)
            const list = Array.isArray(prevTranscripts) ? prevTranscripts : [];

            const isDuplicate = list.some(
                (t: any) => t.timestamp === newTranscript.timestamp &&
                    (t.text || t.transcript) === (newTranscript.text || newTranscript.transcript)
            );

            if (!isDuplicate) {
                return [...list, {
                    id: `live-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                    meeting_id: newTranscript.meeting_id || meetingId,
                    text: newTranscript.text || newTranscript.transcript || '',
                    timestamp: newTranscript.timestamp,
                    speaker: newTranscript.speaker,
                    audio_start_time: newTranscript.audio_start_time,
                    audio_end_time: newTranscript.audio_end_time,
                    is_provisional: false
                }];
            }
            return list;
        });
    }, [meetingId, onTranscriptUpdate]);

    // Auto-refresh when recording stops to get full final transcripts
    useEffect(() => {
        if (!isRecording) {
            // Wait for backend pipeline to finish (it sends 'stop' then processes)
            const timer = setTimeout(() => {
                console.log("🔄 Auto-refreshing transcripts after recording...");
                if (onRefreshTranscripts) {
                    onRefreshTranscripts();
                }
            }, 2000); // 2s delay to be safe
            return () => clearTimeout(timer);
        }
    }, [isRecording, onRefreshTranscripts]);

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
        <div className="flex flex-col w-1/2 border-r border-gray-200 bg-white relative h-full">
            {/* Dialogs */}
            {renameState.isOpen && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-white p-4 rounded-lg shadow-xl w-80">
                        <h3 className="text-lg font-semibold mb-3">Rename Speaker</h3>
                        <input
                            type="text"
                            value={renameState.newName}
                            onChange={(e) => setRenameState({ ...renameState, newName: e.target.value })}
                            className="w-full border rounded p-2 mb-4"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setRenameState({ ...renameState, isOpen: false })}
                                className="px-3 py-1 text-gray-600 hover:bg-gray-100 rounded"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmRename}
                                className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                            >
                                Save
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {mergeState.isOpen && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-white p-4 rounded-lg shadow-xl w-80">
                        <h3 className="text-lg font-semibold mb-1">Delete Speaker</h3>
                        <p className="text-sm text-gray-500 mb-3">
                            Merge segments from <b>{mergeState.fromSpeaker}</b> into:
                        </p>
                        <select
                            value={mergeState.toSpeaker}
                            onChange={(e) => setMergeState({ ...mergeState, toSpeaker: e.target.value })}
                            className="w-full border rounded p-2 mb-4"
                        >
                            <option value="">Select a speaker...</option>
                            {uniqueSpeakers
                                .filter(s => s !== mergeState.fromSpeaker)
                                .map(s => (
                                    <option key={s} value={s}>{s}</option>
                                ))
                            }
                        </select>
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setMergeState({ ...mergeState, isOpen: false })}
                                className="px-3 py-1 text-gray-600 hover:bg-gray-100 rounded"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmMerge}
                                disabled={!mergeState.toSpeaker}
                                className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                            >
                                Merge & Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}

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
                                                    {/* Speaker Avatar - Fixed width to prevent misalignment */}
                                                    <div className="flex-shrink-0 flex flex-col items-center gap-1 w-24 group/speaker">
                                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs shadow-sm ${getSpeakerColor(transcript.speaker)}`}>
                                                            {transcript.speaker ? transcript.speaker.slice(0, 2).toUpperCase() : '??'}
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-[10px] font-medium text-gray-600 text-center leading-tight break-words max-w-[60px]">
                                                                {transcript.speaker || 'Unknown'}
                                                            </span>
                                                            {/* Action Buttons */}
                                                            {transcript.speaker && (
                                                                <div className="hidden group-hover/speaker:flex flex-col gap-0.5 ml-1">
                                                                    <button
                                                                        onClick={(e) => { e.stopPropagation(); handleRenameClick(transcript.speaker!); }}
                                                                        className="p-0.5 text-gray-400 hover:text-blue-600 rounded bg-white/80 shadow-sm"
                                                                        title="Rename"
                                                                    >
                                                                        <Edit2 className="w-3 h-3" />
                                                                    </button>
                                                                    <button
                                                                        onClick={(e) => { e.stopPropagation(); handleDeleteClick(transcript.speaker!); }}
                                                                        className="p-0.5 text-gray-400 hover:text-red-600 rounded bg-white/80 shadow-sm"
                                                                        title="Delete/Merge"
                                                                    >
                                                                        <Trash2 className="w-3 h-3" />
                                                                    </button>
                                                                </div>
                                                            )}
                                                        </div>
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
