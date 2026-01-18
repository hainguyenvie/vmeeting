import { useState, useCallback } from 'react';
import { Transcript, Summary } from '@/types';
import { ModelConfig } from '@/components/ModelSettingsModal';
import { useSidebar } from '@/components/Sidebar/SidebarProvider';
import { toast } from 'sonner';
import Analytics from '@/lib/analytics';
import { summaryAPI } from '@/lib/api';

type SummaryStatus = 'idle' | 'processing' | 'summarizing' | 'regenerating' | 'completed' | 'error';

interface UseSummaryGenerationProps {
  meeting: any;
  transcripts: Transcript[];
  modelConfig: ModelConfig;
  isModelConfigLoading: boolean;
  selectedTemplate: string;
  onMeetingUpdated?: () => Promise<void>;
  updateMeetingTitle: (title: string) => void;
  setAiSummary: (summary: Summary | null) => void;
}

export function useSummaryGeneration({
  meeting,
  transcripts,
  modelConfig,
  isModelConfigLoading,
  selectedTemplate,
  onMeetingUpdated,
  updateMeetingTitle,
  setAiSummary,
}: UseSummaryGenerationProps) {
  const [summaryStatus, setSummaryStatus] = useState<SummaryStatus>('idle');
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [originalTranscript, setOriginalTranscript] = useState<string>('');

  const { startSummaryPolling } = useSidebar();

  // Helper to get status message
  const getSummaryStatusMessage = useCallback((status: SummaryStatus) => {
    switch (status) {
      case 'processing':
        return 'Processing transcript...';
      case 'summarizing':
        return 'Generating summary...';
      case 'regenerating':
        return 'Regenerating summary...';
      case 'completed':
        return 'Summary completed';
      case 'error':
        return 'Error generating summary';
      default:
        return '';
    }
  }, []);

  // Unified summary processing logic
  const processSummary = useCallback(async ({
    transcriptText,
    customPrompt = '',
    isRegeneration = false,
  }: {
    transcriptText: string;
    customPrompt?: string;
    metadata?: any;
    isRegeneration?: boolean;
  }) => {
    setSummaryStatus(isRegeneration ? 'regenerating' : 'processing');
    setSummaryError(null);

    try {
      if (!transcriptText.trim()) {
        throw new Error('No transcript text available. Please add some text first.');
      }

      if (!isRegeneration) {
        setOriginalTranscript(transcriptText);
      }

      console.log('Processing transcript with template:', selectedTemplate);

      // Calculate time since recording
      const timeSinceRecording = (Date.now() - new Date(meeting.created_at).getTime()) / 60000; // minutes

      // Track summary generation started
      await Analytics.trackSummaryGenerationStarted(
        modelConfig.provider || 'ollama',
        modelConfig.model || 'unknown',
        transcriptText.length,
        timeSinceRecording
      );

      // Track custom prompt usage if present
      if (customPrompt.trim().length > 0) {
        await Analytics.trackCustomPromptUsed(customPrompt.trim().length);
      }

      setSummaryStatus('summarizing');

      // Call REST API
      const result = await summaryAPI.generate({
        transcript: transcriptText,
        template_id: selectedTemplate,
        provider: modelConfig.provider || 'ollama',
        model: modelConfig.model || 'gemma2:2b',
        api_key: modelConfig.apiKey || undefined,
        custom_prompt: customPrompt,
        meeting_id: meeting.id,
        metadata: (arguments[0] as any).metadata // Access metadata from args
      });

      console.log('✅ Summary generation completed:', result);

      // CRITICAL FIX: Store the FULL response (including markdown field)
      // BlockNoteSummaryView needs the markdown field to properly render tables
      setAiSummary(result as any);

      setSummaryStatus('completed');

      await Analytics.trackSummaryGenerationCompleted(
        modelConfig.provider || 'ollama',
        modelConfig.model || 'unknown',
        true
      );

      if (onMeetingUpdated) {
        await onMeetingUpdated();
      }

    } catch (error) {
      console.error(`Failed to ${isRegeneration ? 'regenerate' : 'generate'} summary:`, error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setSummaryError(errorMessage);
      setSummaryStatus('error');
      if (isRegeneration) {
        setAiSummary(null);
      }

      toast.error(`Failed to ${isRegeneration ? 'regenerate' : 'generate'} summary`, {
        description: errorMessage,
      });

      await Analytics.trackSummaryGenerationCompleted(
        modelConfig.provider || 'ollama',
        modelConfig.model || 'unknown',
        false,
        undefined,
        errorMessage
      );
    }
  }, [
    meeting.id,
    meeting.created_at,
    modelConfig,
    selectedTemplate,
    startSummaryPolling,
    setAiSummary,
    updateMeetingTitle,
    onMeetingUpdated,
  ]);

  // Public API: Generate summary from transcripts
  const handleGenerateSummary = useCallback(async (customPrompt: string = '') => {
    // Check if model config is still loading
    if (isModelConfigLoading) {
      console.log('⏳ Model configuration is still loading, please wait...');
      toast.info('Loading model configuration, please wait...');
      return;
    }

    if (!transcripts.length) {
      const error_msg = 'No transcripts available for summary';
      console.log(error_msg);
      toast.error(error_msg);
      return;
    }

    console.log('🚀 Starting summary generation with config:', {
      provider: modelConfig.provider,
      model: modelConfig.model,
      template: selectedTemplate
    });

    // Construct metadata
    let meetingDate = new Date();
    if (meeting.created_at) {
      // Check if timestamp is in seconds (10 digits) or ms (13 digits)
      const timestamp = meeting.created_at < 10000000000 ? meeting.created_at * 1000 : meeting.created_at;
      meetingDate = new Date(timestamp);
    }

    const metadata = {
      meeting_title: meeting.title || 'Cuộc họp không tên',
      date: meetingDate.toLocaleString('vi-VN'),
      participants: Array.from(new Set(transcripts.map(t => t.speaker).filter(Boolean)))
    };

    // Format transcript with speaker labels and timestamps
    const fullTranscript = transcripts.map(t => {
      // FIX: Database uses 'transcript' column, not 'text'
      const content = (t as any).transcript || t.text || '';
      if (t.speaker) {
        // Simplified formatting
        return `${t.speaker}: ${content}`;
      }
      return content;
    }).join('\n');

    // Pass metadata separately, do NOT bake into customPrompt
    await processSummary({
      transcriptText: fullTranscript,
      customPrompt: customPrompt, // Only user input
      metadata: metadata
    });
  }, [transcripts, meeting, processSummary, modelConfig, isModelConfigLoading, selectedTemplate]);

  // Public API: Regenerate summary from original transcript
  const handleRegenerateSummary = useCallback(async () => {
    if (!originalTranscript.trim()) {
      console.error('No original transcript available for regeneration');
      return;
    }

    await processSummary({
      transcriptText: originalTranscript,
      isRegeneration: true
    });
  }, [originalTranscript, processSummary]);

  return {
    summaryStatus,
    summaryError,
    handleGenerateSummary,
    handleRegenerateSummary,
    getSummaryStatusMessage,
  };
}
