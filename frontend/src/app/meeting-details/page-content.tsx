"use client";
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Summary, SummaryResponse } from '@/types';
import { useSidebar } from '@/components/Sidebar/SidebarProvider';
import Analytics from '@/lib/analytics';
import { TranscriptPanel } from '@/components/MeetingDetails/TranscriptPanel';
import { SummaryPanel } from '@/components/MeetingDetails/SummaryPanel';
import { toast } from 'sonner';

// Custom hooks
import { useMeetingData } from '@/hooks/meeting-details/useMeetingData';
import { useSummaryGeneration } from '@/hooks/meeting-details/useSummaryGeneration';
import { useModelConfiguration } from '@/hooks/meeting-details/useModelConfiguration';
import { useTemplates } from '@/hooks/meeting-details/useTemplates';
import { useCopyOperations } from '@/hooks/meeting-details/useCopyOperations';
import { useMeetingOperations } from '@/hooks/meeting-details/useMeetingOperations';

export default function PageContent({
  meeting,
  summaryData,
  shouldAutoGenerate = false,
  onAutoGenerateComplete,
  onMeetingUpdated
}: {
  meeting: any;
  summaryData: Summary | null;
  shouldAutoGenerate?: boolean;
  onAutoGenerateComplete?: () => void;
  onMeetingUpdated?: () => Promise<void>;
}) {
  console.log('📄 PAGE CONTENT: Initializing with data:', {
    meetingId: meeting.id,
    summaryDataKeys: summaryData ? Object.keys(summaryData) : null,
    transcriptsCount: meeting.transcripts?.length
  });

  // State
  const [customPrompt, setCustomPrompt] = useState<string>('');
  const [isRecording] = useState(false);
  const [summaryResponse] = useState<SummaryResponse | null>(null);
  const [speakerNames, setSpeakerNames] = useState<Map<string, string>>(new Map());

  // Sidebar context
  const { serverAddress } = useSidebar();

  // 🔥 FIX: Initialize hooks FIRST before using them in callbacks
  const meetingData = useMeetingData({ meeting, summaryData, onMeetingUpdated });
  const modelConfig = useModelConfiguration({ serverAddress });
  const templates = useTemplates();

  // Speaker management handlers
  const handleSpeakerUpdate = useCallback((oldSpeaker: string, newName: string) => {
    // Update speaker names map
    setSpeakerNames(prev => {
      const updated = new Map(prev);
      updated.set(oldSpeaker, newName);
      return updated;
    });

    // 🔥 FIX: Actually update transcripts to reflect the change in UI
    meetingData.setTranscripts(prev => prev.map(t =>
      t.speaker === oldSpeaker
        ? { ...t, speaker: newName }
        : t
    ));

    toast.success(`Speaker renamed to "${newName}"`);
    
    // TODO: Call backend to update speaker name in database
    // await invoke('update_speaker_name', { meetingId: meeting.id, oldSpeaker, newName });
  }, [meetingData]);

  const handleSpeakerMerge = useCallback((fromSpeaker: string, toSpeaker: string) => {
    // Remove merged speaker from names map
    setSpeakerNames(prev => {
      const updated = new Map(prev);
      updated.delete(fromSpeaker);
      return updated;
    });

    // 🔥 FIX: Actually reassign transcripts to merged speaker
    meetingData.setTranscripts(prev => prev.map(t =>
      t.speaker === fromSpeaker
        ? { ...t, speaker: toSpeaker }
        : t
    ));

    toast.success(`Merged "${fromSpeaker}" into "${toSpeaker}"`);
    
    // TODO: Call backend to merge speakers in database
    // await invoke('merge_speakers', { meetingId: meeting.id, fromSpeaker, toSpeaker });
  }, [meetingData]);

  const summaryGeneration = useSummaryGeneration({
    meeting,
    transcripts: meetingData.transcripts,
    modelConfig: modelConfig.modelConfig,
    isModelConfigLoading: modelConfig.isLoading,
    selectedTemplate: templates.selectedTemplate,
    onMeetingUpdated,
    updateMeetingTitle: meetingData.updateMeetingTitle,
    setAiSummary: meetingData.setAiSummary,
  });

  const copyOperations = useCopyOperations({
    meeting,
    transcripts: meetingData.transcripts,
    meetingTitle: meetingData.meetingTitle,
    aiSummary: meetingData.aiSummary,
    blockNoteSummaryRef: meetingData.blockNoteSummaryRef,
  });

  const meetingOperations = useMeetingOperations({
    meeting,
  });

  // 🔥 Citation handler: Jump to transcript by timestamp
  const handleJumpToTranscript = useCallback((timeInSeconds: number) => {
    console.log(`🔗 Jumping to transcript at ${timeInSeconds}s`);
    
    // Find transcript container
    const container = document.getElementById('transcript-scroll-container');
    if (!container) {
      console.warn('Transcript container not found');
      return;
    }
    
    // Find closest transcript element by time
    const elements = Array.from(container.querySelectorAll('[data-time]'));
    
    if (elements.length === 0) {
      toast.error('No transcript segments found');
      return;
    }
    
    let closestElement: Element | null = null;
    let minDiff = Infinity;
    
    for (const el of elements) {
      const elTime = parseInt(el.getAttribute('data-time') || '0', 10);
      const diff = Math.abs(elTime - timeInSeconds);
      if (diff < minDiff) {
        minDiff = diff;
        closestElement = el;
      }
    }
    
    if (closestElement) {
      // Scroll to element
      closestElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      
      // Add highlight effect
      closestElement.classList.add('bg-yellow-200', 'transition-colors', 'duration-500');
      setTimeout(() => {
        closestElement?.classList.remove('bg-yellow-200');
      }, 2000);
      
      toast.success(`Jumped to [${Math.floor(timeInSeconds / 60)}:${(timeInSeconds % 60).toString().padStart(2, '0')}]`);
    } else {
      toast.error('Transcript segment not found');
    }
  }, []);

  // Track page view
  useEffect(() => {
    Analytics.trackPageView('meeting_details');
  }, []);

  // 🔥 Setup global click handler for citation links (works in tables AND paragraphs)
  useEffect(() => {
    const handleCitationClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      
      // 🔥 IGNORE clicks on upload buttons and form controls
      if (
        target.closest('button[type="button"]')?.textContent?.includes('Upload') ||
        target.closest('input[type="file"]') ||
        target.closest('textarea') ||
        target.closest('[data-no-citation]') // Allow components to opt-out
      ) {
        console.log('⏭️ Skipping citation detection for form control');
        return;
      }
      
      // Strategy 1: Check if clicked directly on text containing [MM:SS]
      let text = target.textContent || '';
      let timestampMatch = text.match(/\[(\d{2}):(\d{2})\]/);
      
      // Strategy 2: If not found, check parent elements (for nested spans/tags)
      if (!timestampMatch) {
        let parent = target.parentElement;
        let depth = 0;
        while (parent && depth < 3) { // Check up to 3 levels
          text = parent.textContent || '';
          timestampMatch = text.match(/\[(\d{2}):(\d{2})\]/);
          if (timestampMatch) break;
          parent = parent.parentElement;
          depth++;
        }
      }
      
      if (timestampMatch) {
        // Check if click is near the timestamp (within 50 chars)
        const clickOffset = text.indexOf(`[${timestampMatch[1]}:${timestampMatch[2]}]`);
        const targetText = target.textContent || '';
        
        // Only trigger if clicking on/near the timestamp itself
        if (targetText.includes('[') || target.closest('td') || clickOffset >= 0) {
          e.preventDefault();
          const minutes = parseInt(timestampMatch[1], 10);
          const seconds = parseInt(timestampMatch[2], 10);
          const totalSeconds = minutes * 60 + seconds;
          
          console.log(`🔗 Citation clicked: [${timestampMatch[1]}:${timestampMatch[2]}] → ${totalSeconds}s`);
          handleJumpToTranscript(totalSeconds);
        }
      }
    };

    // Add event listener to document
    document.addEventListener('click', handleCitationClick);
    
    return () => {
      document.removeEventListener('click', handleCitationClick);
    };
  }, [handleJumpToTranscript]);

  // Auto-generate summary when flag is set
  useEffect(() => {
    const autoGenerate = async () => {
      if (shouldAutoGenerate && meetingData.transcripts.length > 0) {
        console.log(`🤖 Auto-generating summary with ${modelConfig.modelConfig.provider}/${modelConfig.modelConfig.model}...`);
        await summaryGeneration.handleGenerateSummary('');

        // Notify parent that auto-generation is complete
        if (onAutoGenerateComplete) {
          onAutoGenerateComplete();
        }
      }
    };

    autoGenerate();
  }, [shouldAutoGenerate]); // Only trigger when flag changes

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="flex flex-col h-screen bg-gray-50"
    >
      <div className="flex flex-1 overflow-hidden">
      

        <TranscriptPanel
          transcripts={meetingData.transcripts}
          customPrompt={customPrompt}
          onPromptChange={setCustomPrompt}
          onCopyTranscript={copyOperations.handleCopyTranscript}
          onOpenMeetingFolder={meetingOperations.handleOpenMeetingFolder}
          isRecording={isRecording}
          onSpeakerUpdate={handleSpeakerUpdate}
          onSpeakerMerge={handleSpeakerMerge}
        />

          <SummaryPanel
          meeting={meeting}
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
          summaryResponse={summaryResponse}
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
        />

      </div>
    </motion.div>
  );
}
