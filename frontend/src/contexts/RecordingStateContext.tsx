'use client';

import React, { createContext, useContext, useState } from 'react';
// import { invoke } from '@tauri-apps/api/core'; // Desktop only
// import { listen } from '@tauri-apps/api/event'; // Desktop only

/**
 * WEB VERSION - Recording state context (stub)
 * Desktop-only feature - recording state sync is not available in web version
 * Web version uses its own recording logic via WebSocket
 */

interface RecordingState {
  isRecording: boolean;
  isPaused: boolean;
  isActive: boolean;
  recordingDuration: number | null;
  activeDuration: number | null;
}

interface RecordingStateContextType extends RecordingState { }

const RecordingStateContext = createContext<RecordingStateContextType | null>(null);

export const useRecordingState = () => {
  const context = useContext(RecordingStateContext);
  if (!context) {
    throw new Error('useRecordingState must be used within a RecordingStateProvider');
  }
  return context;
};

export function RecordingStateProvider({ children }: { children: React.ReactNode }) {
  // Web version: No-op implementation - returns default not-recording state
  const [state] = useState<RecordingState>({
    isRecording: false,
    isPaused: false,
    isActive: false,
    recordingDuration: null,
    activeDuration: null,
  });

  return (
    <RecordingStateContext.Provider value={state}>
      {children}
    </RecordingStateContext.Provider>
  );
}
