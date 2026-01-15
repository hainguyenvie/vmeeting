"use client";

import { useEffect, useState } from 'react';
import { Summary, SummaryResponse, Transcript } from '@/types';
import { useSidebar } from '@/components/Sidebar/SidebarProvider';
import { SummaryPanel } from '@/components/MeetingDetails/SummaryPanel';

// Custom hooks
import { useMeetingData } from '@/hooks/meeting-details/useMeetingData';
import { useSummaryGeneration } from '@/hooks/meeting-details/useSummaryGeneration';
import { useModelConfiguration } from '@/hooks/meeting-details/useModelConfiguration';
import { useTemplates } from '@/hooks/meeting-details/useTemplates';
import { useCopyOperations } from '@/hooks/meeting-details/useCopyOperations';
import { useMeetingOperations } from '@/hooks/meeting-details/useMeetingOperations';

interface ConnectedSummaryPanelProps {
    meeting: any;
    currentTranscripts: Transcript[]; // Live transcripts from parent
}

export function ConnectedSummaryPanel({ meeting, currentTranscripts }: ConnectedSummaryPanelProps) {
    // Sidebar context
    const { serverAddress } = useSidebar();

    // Local state for prompt
    const [customPrompt, setCustomPrompt] = useState<string>('');

    // Hooks
    const meetingData = useMeetingData({
        meeting,
        summaryData: meeting.summary ? JSON.parse(meeting.summary) : null
    });

    const modelConfig = useModelConfiguration({ serverAddress });
    const templates = useTemplates();
    const copyOps = useCopyOperations({
        meeting,
        transcripts: meetingData.transcripts,
        meetingTitle: meetingData.meetingTitle,
        aiSummary: meetingData.aiSummary,
        blockNoteSummaryRef: meetingData.blockNoteSummaryRef
    });

    // Use Meeting Operations for folder opening
    const meetingOps = useMeetingOperations({ meeting });

    const summaryGen = useSummaryGeneration({
        transcripts: meetingData.transcripts,
        meeting,
        modelConfig: modelConfig.modelConfig,
        isModelConfigLoading: modelConfig.isLoading,
        updateMeetingTitle: meetingData.updateMeetingTitle,
        setAiSummary: meetingData.setAiSummary,
        selectedTemplate: templates.selectedTemplate,
        // onSummaryGenerated: async () => {}, // Not used in PageContent?
    });

    // Sync transcripts from parent to meetingData (for Summary Logic)
    useEffect(() => {
        if (currentTranscripts) {
            meetingData.setTranscripts(currentTranscripts);
        }
    }, [currentTranscripts, meetingData.setTranscripts]);

    return (
        <div className="h-full flex flex-col bg-white">
            <SummaryPanel
                // Data
                meeting={{
                    ...meeting,
                    id: meeting.id,
                    title: meetingData.meetingTitle,
                    created_at: typeof meeting.created_at === 'number'
                        ? new Date(meeting.created_at * 1000).toISOString()
                        : meeting.created_at
                }}
                meetingTitle={meetingData.meetingTitle}
                aiSummary={meetingData.aiSummary}
                summaryResponse={null}
                summaryStatus={summaryGen.summaryStatus}
                summaryError={summaryGen.summaryError}
                transcripts={meetingData.transcripts}

                // Model Config
                modelConfig={modelConfig.modelConfig}
                setModelConfig={modelConfig.setModelConfig}
                onSaveModelConfig={modelConfig.handleSaveModelConfig}
                isModelConfigLoading={modelConfig.isLoading}

                // Title Editing
                onTitleChange={meetingData.handleTitleChange}
                isEditingTitle={meetingData.isEditingTitle}
                onStartEditTitle={() => meetingData.setIsEditingTitle(true)}
                onFinishEditTitle={() => {
                    meetingData.setIsEditingTitle(false);
                    meetingData.handleSaveMeetingTitle();
                }}
                isTitleDirty={meetingData.isTitleDirty}

                // Summary Actions
                summaryRef={meetingData.blockNoteSummaryRef}
                isSaving={meetingData.isSaving}
                onSaveAll={meetingData.saveAllChanges}
                onCopySummary={copyOps.handleCopySummary}
                onOpenFolder={meetingOps.handleOpenMeetingFolder}

                // Generation
                customPrompt={customPrompt}
                onGenerateSummary={(prompt) => {
                    setCustomPrompt(prompt);
                    return summaryGen.handleGenerateSummary(prompt);
                }}
                onRegenerateSummary={() => summaryGen.handleGenerateSummary(customPrompt)}

                // Templates
                availableTemplates={templates.availableTemplates}
                selectedTemplate={templates.selectedTemplate}
                onTemplateSelect={templates.handleTemplateSelection}

                // Updates
                onSaveSummary={meetingData.handleSaveSummary}
                onSummaryChange={meetingData.handleSummaryChange}
                onDirtyChange={meetingData.setIsSummaryDirty}

                // Helpers
                getSummaryStatusMessage={summaryGen.getSummaryStatusMessage}
            />
        </div>
    );
}
