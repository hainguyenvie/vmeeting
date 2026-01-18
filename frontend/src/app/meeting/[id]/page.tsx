"use client"

import { useSidebar } from "@/components/Sidebar/SidebarProvider";
import { useState, useEffect, useCallback } from "react";
import { Transcript, Summary } from "@/types";
import { useRouter } from "next/navigation";
import { LoaderIcon } from "lucide-react";
import { meetingsAPI } from "@/lib/api";
import { motion } from 'framer-motion';
import { EnhancedTranscriptPanel } from '@/components/MeetingDetails/EnhancedTranscriptPanel';
import { SummaryPanel } from '@/components/MeetingDetails/SummaryPanel';
import { toast } from 'sonner';

// Custom hooks
import { useMeetingData } from '@/hooks/meeting-details/useMeetingData';
import { useSummaryGeneration } from '@/hooks/meeting-details/useSummaryGeneration';
import { useModelConfiguration } from '@/hooks/meeting-details/useModelConfiguration';
import { useTemplates } from '@/hooks/meeting-details/useTemplates';
import { useCopyOperations } from '@/hooks/meeting-details/useCopyOperations';
import { useMeetingOperations } from '@/hooks/meeting-details/useMeetingOperations';

interface MeetingDetailsResponse {
    id: string;
    title: string;
    created_at: string | number;
    updated_at?: string;
    transcripts: Transcript[];
}

export default function MeetingDetailPage({ params }: { params: { id: string } }) {
    const router = useRouter();
    const meetingId = params.id;
    // ... rest of state ...

    // NEW: Global click handler for citation links
    useEffect(() => {
        const handleCitationClick = (e: MouseEvent) => {
            const target = e.target as HTMLElement;
            // Traverse up to find if click was inside an anchor tag
            const anchor = target.closest('a');

            if (anchor && anchor.hash && anchor.hash.startsWith('#transcript-')) {
                e.preventDefault();
                const targetId = anchor.hash.substring(1); // remove '#'
                console.log('🔗 Intercepted citation click:', targetId);

                const element = document.getElementById(targetId);
                if (element) {
                    // 1. Scroll into view
                    element.scrollIntoView({ behavior: 'smooth', block: 'center' });

                    // 2. Dispatch custom event to highlight the transcript
                    const event = new CustomEvent('highlightTranscript', { detail: targetId });
                    window.dispatchEvent(event);
                } else {
                    console.warn('⚠️ Target transcript element not found:', targetId);
                }
            }
        };

        // Add listener to the document
        document.addEventListener('click', handleCitationClick);

        return () => {
            document.removeEventListener('click', handleCitationClick);
        };
    }, []);

    const { setCurrentMeeting, refetchMeetings, serverAddress } = useSidebar();
    const [meetingDetails, setMeetingDetails] = useState<MeetingDetailsResponse | null>(null);
    const [meetingSummary, setMeetingSummary] = useState<Summary | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [customPrompt, setCustomPrompt] = useState<string>('');
    const [isRecording, setIsRecording] = useState(false);

    // Fetch meeting details
    const fetchMeetingDetails = useCallback(async () => {
        if (!meetingId) {
            return;
        }

        try {
            const data = await meetingsAPI.getById(meetingId);
            console.log('📥 Meeting details:', data);

            //Fetch transcripts
            const videoTranscripts = await meetingsAPI.getTranscripts(meetingId);
            console.log('📥 Fetched transcripts from API:', videoTranscripts.length, 'items');
            console.log('📥 First transcript:', videoTranscripts[0]);
            console.log('📥 All transcripts:', videoTranscripts);

            const fullData = {
                ...data,
                transcripts: videoTranscripts
            };

            console.log('📥 Setting meetingDetails with', fullData.transcripts.length, 'transcripts');
            setMeetingDetails(fullData as any);

            // Sync with sidebar context
            setCurrentMeeting({ id: data.id, title: data.title });

            return fullData;
        } catch (error) {
            console.error('Error fetching meeting details:', error);
            setError("Failed to load meeting details");
            return null;
        }
    }, [meetingId, setCurrentMeeting]);

    // Reset states when meetingId changes
    useEffect(() => {
        setMeetingDetails(null);
        setMeetingSummary(null);
        setError(null);
        setIsLoading(true);
    }, [meetingId]);

    useEffect(() => {
        console.log('🔍 MeetingDetails useEffect triggered - meetingId:', meetingId);

        if (!meetingId) {
            console.warn('⚠️ No valid meeting ID in URL');
            setError("No meeting selected");
            setIsLoading(false);
            return;
        }

        const loadData = async () => {
            try {
                const meetingData = await fetchMeetingDetails();

                // Handle Summary
                if (meetingData && meetingData.summary) {
                    const summaryData = meetingData.summary;

                    let parsedData: any = summaryData;
                    if (typeof summaryData === 'string') {
                        try {
                            parsedData = JSON.parse(summaryData);
                        } catch (e) {
                            console.warn('Failed to parse summary JSON');
                            parsedData = {};
                        }
                    }

                    // Priority: BlockNote JSON or Markdown format
                    if (parsedData.summary_json || parsedData.markdown) {
                        setMeetingSummary(parsedData as any);
                    } else {
                        setMeetingSummary(null);
                    }
                } else {
                    setMeetingSummary(null);
                }

            } finally {
                setIsLoading(false);
            }
        };

        loadData();
    }, [meetingId, fetchMeetingDetails]);

    // Initialize hooks ONLY when meeting data is available
    const meetingData = useMeetingData({
        meeting: meetingDetails || { id: meetingId, title: '', transcripts: [] },
        summaryData: meetingSummary,
        onMeetingUpdated: async () => {
            await fetchMeetingDetails();
            await refetchMeetings();
        }
    });

    const modelConfig = useModelConfiguration({ serverAddress });
    const templates = useTemplates();

    const summaryGeneration = useSummaryGeneration({
        meeting: meetingDetails || { id: meetingId },
        transcripts: meetingData.transcripts,
        modelConfig: modelConfig.modelConfig,
        isModelConfigLoading: modelConfig.isLoading,
        selectedTemplate: templates.selectedTemplate,
        onMeetingUpdated: async () => {
            await fetchMeetingDetails();
            await refetchMeetings();
        },
        updateMeetingTitle: meetingData.updateMeetingTitle,
        setAiSummary: meetingData.setAiSummary,
    });

    const copyOperations = useCopyOperations({
        meeting: meetingDetails || { id: meetingId },
        transcripts: meetingData.transcripts,
        meetingTitle: meetingData.meetingTitle,
        aiSummary: meetingData.aiSummary,
        blockNoteSummaryRef: meetingData.blockNoteSummaryRef,
    });

    const meetingOperations = useMeetingOperations({
        meeting: meetingDetails || { id: meetingId },
    });

    // Delete meeting handler
    const handleDeleteMeeting = async () => {
        if (!meetingDetails) return;

        if (!confirm(`Are you sure you want to delete "${meetingDetails.title}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            await meetingsAPI.delete(meetingId);
            alert('Meeting deleted successfully');
            router.push('/'); // Navigate back to homepage
        } catch (err: any) {
            alert('Failed to delete meeting: ' + err.message);
        }
    };

    if (error) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="text-center">
                    <p className="text-red-500 mb-4">{error}</p>
                    <button
                        onClick={() => router.push('/')}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                    >
                        Go Back
                    </button>
                </div>
            </div>
        );
    }

    if (isLoading || !meetingDetails) {
        return <div className="flex items-center justify-center h-screen">
            <LoaderIcon className="animate-spin size-6" />
        </div>;
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="flex flex-col h-screen bg-gray-50"
        >
            {/* Header Bar with Delete Button */}
            <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.push('/')}
                        className="p-2 text-gray-600 hover:bg-gray-100 rounded transition"
                        title="Back to homepage"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                    </button>
                    <h1 className="text-lg font-semibold text-gray-900">{meetingDetails.title}</h1>
                </div>
                <button
                    onClick={handleDeleteMeeting}
                    className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition flex items-center gap-2"
                    title="Delete meeting"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span className="font-medium">Delete Meeting</span>
                </button>
            </div>

            <div className="flex flex-1 overflow-hidden">

                <EnhancedTranscriptPanel
                    meetingId={meetingId}
                    transcripts={meetingData.transcripts}
                    customPrompt={customPrompt}
                    onPromptChange={setCustomPrompt}
                    onTranscriptUpdate={meetingData.setTranscripts}
                    onRecordingStateChange={setIsRecording}
                    onRefreshTranscripts={async () => { await fetchMeetingDetails(); }}
                />

                <SummaryPanel
                    meeting={meetingDetails}
                    meetingTitle={meetingData.meetingTitle}
                    onTitleChange={meetingData.handleTitleChange}
                    isEditingTitle={meetingData.isEditingTitle}
                    onStartEditTitle={() => meetingData.setIsEditingTitle(true)}
                    onFinishEditTitle={() => meetingData.setIsEditingTitle(false)}
                    isTitleDirty={meetingData.isTitleDirty}
                    summaryRef={meetingData.blockNoteSummaryRef}
                    isSaving={meetingData.isSaving}
                    onSaveAll={meetingData.saveAllChanges}
                    onCopySummary={copyOperations.handleCopySummary}
                    onOpenFolder={meetingOperations.handleOpenMeetingFolder}
                    aiSummary={meetingData.aiSummary}
                    summaryStatus={summaryGeneration.summaryStatus}
                    transcripts={meetingData.transcripts}
                    modelConfig={modelConfig.modelConfig}
                    setModelConfig={modelConfig.setModelConfig}
                    onSaveModelConfig={modelConfig.handleSaveModelConfig}
                    onGenerateSummary={summaryGeneration.handleGenerateSummary}
                    customPrompt={customPrompt}
                    summaryResponse={null}
                    onSaveSummary={meetingData.handleSaveSummary}
                    onSummaryChange={meetingData.handleSummaryChange}
                    onDirtyChange={meetingData.setIsSummaryDirty}
                    summaryError={summaryGeneration.summaryError}
                    onRegenerateSummary={summaryGeneration.handleRegenerateSummary}
                    getSummaryStatusMessage={summaryGeneration.getSummaryStatusMessage}
                    availableTemplates={templates.availableTemplates}
                    selectedTemplate={templates.selectedTemplate}
                    onTemplateSelect={templates.handleTemplateSelection}
                    isModelConfigLoading={modelConfig.isLoading}
                    currentTranscripts={meetingData.transcripts}
                />

            </div>
        </motion.div>
    );
}
