'use client';

import { useState, useEffect, useCallback } from 'react';
// import { invoke } from '@tauri-apps/api/core'; // Desktop
import { toast } from 'sonner';
import { ModelConfig, ModelSettingsModal } from '@/components/ModelSettingsModal';

interface SummaryModelSettingsProps {
  refetchTrigger?: number; // Change this to trigger refetch
}

export function SummaryModelSettings({ refetchTrigger }: SummaryModelSettingsProps) {
  const [modelConfig, setModelConfig] = useState<ModelConfig>({
    provider: 'ollama',
    model: 'llama3.2:latest',
    whisperModel: 'large-v3',
    apiKey: null,
    ollamaEndpoint: null
  });

  // Reusable fetch function
  const fetchModelConfig = useCallback(async () => {
    try {
      // Web version: localStorage
      const savedConfig = localStorage.getItem('model_config');
      if (savedConfig) {
        const data = JSON.parse(savedConfig);
        setModelConfig(data);
      }

      /* Desktop:
      const data = await invoke('api_get_model_config') as any;
      if (data && data.provider !== null) {
        // ...
        setModelConfig(data);
      }
      */
    } catch (error) {
      console.error('Failed to fetch model config:', error);
      toast.error('Failed to load model settings');
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchModelConfig();
  }, [fetchModelConfig]);

  // Refetch when trigger changes (optional external control)
  useEffect(() => {
    if (refetchTrigger !== undefined && refetchTrigger > 0) {
      fetchModelConfig();
    }
  }, [refetchTrigger, fetchModelConfig]);

  // Listen for model config updates from other components
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'model_config' && e.newValue) {
        setModelConfig(JSON.parse(e.newValue));
      }
    };
    window.addEventListener('storage', handleStorageChange);

    /* Desktop
    const setupListener = async () => {
      const { listen } = await import('@tauri-apps/api/event');
      const unlisten = await listen<ModelConfig>('model-config-updated', (event) => {
        setModelConfig(event.payload);
      });
      return unlisten;
    }; 
    */

    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  // Save handler
  const handleSaveModelConfig = async (config: ModelConfig) => {
    try {
      // Web version: localStorage
      localStorage.setItem('model_config', JSON.stringify(config));

      /* Desktop:
      await invoke('api_save_model_config', { ... });
      const { emit } = await import('@tauri-apps/api/event');
      await emit('model-config-updated', config);
      */

      setModelConfig(config);
      toast.success('Model settings saved successfully');
    } catch (error) {
      console.error('Error saving model config:', error);
      toast.error('Failed to save model settings');
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">Summary Model Configuration</h3>
      <p className="text-sm text-gray-600 mb-6">
        Configure the AI model used for generating meeting summaries.
      </p>
      <ModelSettingsModal
        modelConfig={modelConfig}
        setModelConfig={setModelConfig}
        onSave={handleSaveModelConfig}
        skipInitialFetch={true}
      />
    </div>
  );
}
