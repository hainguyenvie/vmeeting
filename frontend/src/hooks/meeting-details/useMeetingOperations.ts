import { useCallback } from 'react';
// import { invoke as invokeTauri } from '@tauri-apps/api/core'; // Desktop only
import { toast } from 'sonner';

interface UseMeetingOperationsProps {
  meeting: any;
}

export function useMeetingOperations({
  meeting,
}: UseMeetingOperationsProps) {

  // Open meeting folder in file explorer (Desktop only - disabled for web)
  const handleOpenMeetingFolder = useCallback(async () => {
    // Web version: Not supported
    toast.info('Opening meeting folder is only available in desktop version');
    console.warn('[Web] Open meeting folder not supported');
  }, [meeting.id]);

  return {
    handleOpenMeetingFolder,
  };
}
