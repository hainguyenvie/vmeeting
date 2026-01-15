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
        meeting_id: meeting.id
      });

      console.log('✅ Summary generation completed:', result);

      // Use the raw structure (let BlockNoteSummaryView handle detection)
      // If we got parsed summary directly
      if (result.summary) {
        setAiSummary(result.summary as Summary);
      } else {
        // Fallback or specific logic if response structure differs
        setAiSummary(result as unknown as Summary);
      }

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

    // 🔥 AUTO-ENHANCE: Build enhanced context with speaker info and meeting time
    let enhancedPrompt = '';

    // Add meeting time context
    if (meeting.created_at) {
      const meetingDate = new Date(meeting.created_at);
      const formattedDate = meetingDate.toLocaleString('vi-VN', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      enhancedPrompt += `THÔNG TIN CUỘC HỌP:\n`;
      enhancedPrompt += `- Thời gian: ${formattedDate}\n`;
      enhancedPrompt += `- Số lượng transcript: ${transcripts.length}\n`;
      enhancedPrompt += `\n`;
    }

    // Add speaker mapping context
    const speakersWithNames = transcripts
      .filter(t => t.speaker)
      .reduce((acc, t) => {
        if (t.speaker && !acc.has(t.speaker)) {
          acc.set(t.speaker, t.speaker);
        }
        return acc;
      }, new Map<string, string>());

    if (speakersWithNames.size > 0) {
      enhancedPrompt += `DANH SÁCH NGƯỜI NÓI ĐƯỢC NHẬN DIỆN:\n`;
      Array.from(speakersWithNames.entries()).forEach(([speakerId, name]) => {
        enhancedPrompt += `- ${speakerId}: ${name}\n`;
      });
      enhancedPrompt += `\n`;
      enhancedPrompt += `LƯU Ý: Trong transcript, mỗi phát biểu đều có speaker label. Hãy dùng thông tin này để map với tên người được nhắc đến trong cuộc họp.\n\n`;
    }

    // Append user's custom prompt if provided
    if (customPrompt.trim()) {
      enhancedPrompt += `NGỮ CẢNH BỔ SUNG TỪ NGƯỜI DÙNG:\n${customPrompt}\n\n`;
    }

    // Format transcript with speaker labels and timestamps for better context
    const fullTranscript = transcripts.map(t => {
      if (t.speaker) {
        const timestamp = t.audio_start_time ?
          `[${Math.floor(t.audio_start_time / 60).toString().padStart(2, '0')}:${Math.floor(t.audio_start_time % 60).toString().padStart(2, '0')}]` :
          '';
        return `${timestamp} ${t.speaker}: ${t.text}`;
      }
      return t.text;
    }).join('\n');

    await processSummary({ transcriptText: fullTranscript, customPrompt: enhancedPrompt });
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
