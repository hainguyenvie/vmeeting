"use client"
import { useSidebar } from "@/components/Sidebar/SidebarProvider";
import { useState, useEffect, useCallback, Suspense } from "react";
import { Transcript, Summary } from "@/types";
import PageContent from "./page-content";
import { useRouter, useSearchParams } from "next/navigation";
import Analytics from "@/lib/analytics";
import { LoaderIcon } from "lucide-react";
import { meetingsAPI } from "@/lib/api";

interface MeetingDetailsResponse {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  transcripts: Transcript[];
}

function MeetingDetailsContent() {
  const searchParams = useSearchParams();
  const meetingId = searchParams.get('id');
  const { setCurrentMeeting, refetchMeetings } = useSidebar();
  const router = useRouter();
  const [meetingDetails, setMeetingDetails] = useState<MeetingDetailsResponse | null>(null);
  const [meetingSummary, setMeetingSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [shouldAutoGenerate, setShouldAutoGenerate] = useState<boolean>(false);
  const [hasCheckedAutoGen, setHasCheckedAutoGen] = useState<boolean>(false);

  // Check if gemma3:1b model is available in Ollama
  // Web version: this check might need to be adjusted or removed if we rely on backend config
  const checkForGemmaModel = useCallback(async (): Promise<boolean> => {
    try {
      // For web, we can't invoke 'get_ollama_models' directly.
      // We should rely on backend API or assume true for now/handle error downstream.
      // Or implemented a check endpoint.
      // For now, let's return true to fallback to backend handling.
      return true;
    } catch (error) {
      console.error('❌ Failed to check Ollama models:', error);
      return false;
    }
  }, []);

  // Set up auto-generation - respects DB as source of truth
  const setupAutoGeneration = useCallback(async () => {
    if (hasCheckedAutoGen) return; // Only check once

    try {
      // ✅ STEP 1: Check what's currently in database
      // Using direct invoke here is wrong. We need a REST endpoint for model config.
      // Assuming for now existing backend handles it or we skip auto-config on frontend.
      // For web, we can skip this intricate setup or implement a GET /api/config/model endpoint.
      // Let's simplified assuming backend has defaults.
      setHasCheckedAutoGen(true);
      return;

      /*
      const currentConfig = await invoke('api_get_model_config') as any;

      // ✅ STEP 2: If DB already has a model, use it (never override!)
      if (currentConfig && currentConfig.model) {
        console.log('✅ Using existing model from DB:', currentConfig.model);
        setShouldAutoGenerate(true);
        setHasCheckedAutoGen(true);
        return;
      }
      */
    } catch (error) {
      console.error('❌ Failed to setup auto-generation:', error);
    }

    setHasCheckedAutoGen(true);
  }, [hasCheckedAutoGen, checkForGemmaModel]);

  // Extract fetchMeetingDetails so it can be called from child components
  const fetchMeetingDetails = useCallback(async () => {
    if (!meetingId || meetingId === 'intro-call') {
      return;
    }

    try {
      const data = await meetingsAPI.getById(meetingId);
      console.log('Meeting details:', data);

      // Fetch transcripts separately as getById might not return them (check API implementation)
      // API implem: getById returns {id, title, created_at, duration, summary}
      // We need transcripts for the UI.
      const videoTranscripts = await meetingsAPI.getTranscripts(meetingId);

      const fullData = {
        ...data,
        transcripts: videoTranscripts
      };

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

    if (!meetingId || meetingId === 'intro-call') {
      console.warn('⚠️ No valid meeting ID in URL - meetingId:', meetingId);
      setError("No meeting selected");
      setIsLoading(false);
      Analytics.trackPageView('meeting_details');
      return;
    }

    console.log('✅ Valid meeting ID found, fetching details for:', meetingId);

    setMeetingDetails(null);
    setMeetingSummary(null);
    setError(null);
    setIsLoading(true);

    const loadData = async () => {
      try {
        const meetingData = await fetchMeetingDetails();

        // Handle Summary
        if (meetingData && meetingData.summary) {
          console.log('🔍 FETCH SUMMARY: Found summary in meeting data');
          const summaryData = meetingData.summary;

          let parsedData: any = summaryData;
          if (typeof summaryData === 'string') {
            try {
              parsedData = JSON.parse(summaryData);
            } catch (e) {
              console.warn('Failed to parse summary JSON, treating as raw string/legacy if applicable');
              parsedData = {};
            }
          }

          console.log('🔍 FETCH SUMMARY: Parsed data:', parsedData);

          // Priority 1: BlockNote JSON format
          if (parsedData.summary_json) {
            setMeetingSummary(parsedData as any);
            return;
          }

          // Priority 2: Markdown format
          if (parsedData.markdown) {
            setMeetingSummary(parsedData as any);
            return;
          }

          // Legacy format - apply formatting
          console.log('📦 LEGACY FORMAT: Detected legacy format, applying section formatting');
          // ... (legacy logic handled below if parsedData is not empty/malformed)
          const { MeetingName, _section_order, ...restSummaryData } = parsedData;

          // Only proceed if we have valid legacy data structure
          if (Object.keys(restSummaryData).length > 0) {
            // Format the summary data with consistent styling - PRESERVE ORDER
            const formattedSummary: Summary = {};

            // Use section order if available to maintain exact order and handle duplicates
            const sectionKeys = _section_order || Object.keys(restSummaryData);

            console.log('📦 LEGACY FORMAT: Processing sections:', sectionKeys);

            for (const key of sectionKeys) {
              try {
                const section = restSummaryData[key];
                // Comprehensive null checks to prevent the error
                if (section &&
                  typeof section === 'object' &&
                  'title' in section &&
                  'blocks' in section) {

                  const typedSection = section as { title?: string; blocks?: any[] };

                  // Ensure blocks is an array before mapping
                  if (Array.isArray(typedSection.blocks)) {
                    formattedSummary[key] = {
                      title: typedSection.title || key,
                      blocks: typedSection.blocks.map((block: any) => ({
                        ...block,
                        // type: 'bullet',
                        color: 'default',
                        content: block?.content?.trim() || ''
                      }))
                    };
                  } else {
                    // Handle case where blocks is not an array
                    console.warn(`📦 LEGACY FORMAT: Section ${key} has invalid blocks:`, typedSection.blocks);
                    formattedSummary[key] = {
                      title: typedSection.title || key,
                      blocks: []
                    };
                  }
                } else {
                  console.warn(`📦 LEGACY FORMAT: Skipping invalid section ${key}:`, section);
                }
              } catch (error) {
                console.warn(`📦 LEGACY FORMAT: Error processing section ${key}:`, error);
                // Continue processing other sections
              }
            }

            console.log('📦 LEGACY FORMAT: Formatted summary:', formattedSummary);
            setMeetingSummary(formattedSummary);
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

  // Auto-generation check: runs when meeting is loaded with no summary
  useEffect(() => {
    const checkAutoGen = async () => {
      // Only auto-generate if:
      // 1. We have meeting details
      // 2. No summary exists
      // 3. Meeting has transcripts
      // 4. Haven't checked yet
      if (
        meetingDetails &&
        meetingSummary === null &&
        meetingDetails.transcripts &&
        meetingDetails.transcripts.length > 0 &&
        !hasCheckedAutoGen
      ) {
        console.log('🚀 No summary found, checking for auto-generation...');
        await setupAutoGeneration();
      }
    };

    checkAutoGen();
  }, [meetingDetails, meetingSummary, hasCheckedAutoGen, setupAutoGeneration]);

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
      <LoaderIcon className="animate-spin size-6 " />
    </div>;
  }

  return <PageContent
    meeting={meetingDetails}
    summaryData={meetingSummary}
    shouldAutoGenerate={shouldAutoGenerate}
    onAutoGenerateComplete={() => setShouldAutoGenerate(false)}
    onMeetingUpdated={async () => {
      // Refetch meeting details to get updated title from backend
      await fetchMeetingDetails();
      // Refetch meetings list to update sidebar
      await refetchMeetings();
    }}
  />;
}

export default function MeetingDetails() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <LoaderIcon className="animate-spin size-6" />
      </div>
    }>
      <MeetingDetailsContent />
    </Suspense>
  );
}
