'use client';

import React, { createContext, useContext, useState } from 'react';
// import { listen } from '@tauri-apps/api/event'; // Desktop only
// import { toast } from 'sonner';

/**
 * WEB VERSION - Ollama download context (stub)
 * Desktop-only feature - downloads are not supported in web version
 */

interface OllamaDownloadState {
  downloadProgress: Map<string, number>;
  downloadingModels: Set<string>;
}

interface OllamaDownloadContextType extends OllamaDownloadState {
  isDownloading: (modelName: string) => boolean;
  getProgress: (modelName: string) => number | undefined;
}

const OllamaDownloadContext = createContext<OllamaDownloadContextType | null>(null);

export const useOllamaDownload = () => {
  const context = useContext(OllamaDownloadContext);

  // Web version: Return default no-op values if provider is not available
  if (!context) {
    return {
      downloadProgress: new Map<string, number>(),
      downloadingModels: new Set<string>(),
      isDownloading: () => false,
      getProgress: () => undefined,
    };
  }

  return context;
};

export function OllamaDownloadProvider({ children }: { children: React.ReactNode }) {
  // Web version: No-op implementation
  const [downloadProgress] = useState<Map<string, number>>(new Map());
  const [downloadingModels] = useState<Set<string>>(new Set());

  const contextValue: OllamaDownloadContextType = {
    downloadProgress,
    downloadingModels,
    isDownloading: () => false,
    getProgress: () => undefined,
  };

  return (
    <OllamaDownloadContext.Provider value={contextValue}>
      {children}
    </OllamaDownloadContext.Provider>
  );
}
