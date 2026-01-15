import { useState, useEffect, useCallback } from 'react';
import { ModelConfig } from '@/components/ModelSettingsModal';
// import { invoke as invokeTauri } from '@tauri-apps/api/core'; // Desktop only
import { toast } from 'sonner';
import Analytics from '@/lib/analytics';

interface UseModelConfigurationProps {
  serverAddress: string | null;
}

export function useModelConfiguration({ serverAddress }: UseModelConfigurationProps) {
  // Note: No hardcoded defaults - DB is the source of truth
  const [modelConfig, setModelConfig] = useState<ModelConfig>({
    provider: 'ollama',
    model: '', // Empty until loaded from DB 
    whisperModel: 'large-v3'
  });
  const [isLoading, setIsLoading] = useState(true);
  const [, setError] = useState<string>('');

  // Fetch model configuration on mount and when serverAddress changes
  useEffect(() => {
    const fetchModelConfig = async () => {
      setIsLoading(true);
      try {
        console.log('🔄 [Web] Fetching model configuration from localStorage...');

        // Web version: Load from localStorage or use defaults
        const savedConfig = localStorage.getItem('model_config');
        if (savedConfig) {
          const data = JSON.parse(savedConfig);
          console.log('✅ Loaded model config from localStorage:', data);
          setModelConfig(data);
        } else {
          // Default web config
          const defaultConfig: ModelConfig = {
            provider: 'ollama',
            model: 'llama3:8b', // Reasonable default
            whisperModel: 'large-v3',
            ollamaEndpoint: 'http://localhost:11434'
          };
          setModelConfig(defaultConfig);
          console.warn('⚠️ No model config found in localStorage, using defaults');
        }

        /* Desktop legacy code:
        const data = await invokeTauri('api_get_model_config', {}) as any;
        if (data && data.provider !== null) {
          // ... logic to check API key ...
          setModelConfig(data);
        }
        */
      } catch (error) {
        console.error('❌ Failed to fetch model config:', error);
      } finally {
        setIsLoading(false);
        console.log('✅ Model configuration loading complete');
      }
    };

    fetchModelConfig();
  }, [serverAddress]);

  // Listen for model config updates from other components
  useEffect(() => {
    // Web version: handle via window event or simple effect
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'model_config' && e.newValue) {
        setModelConfig(JSON.parse(e.newValue));
      }
    };
    window.addEventListener('storage', handleStorageChange);

    /* Desktop legacy:
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

  // Save model configuration
  const handleSaveModelConfig = useCallback(async (updatedConfig?: ModelConfig) => {
    try {
      const configToSave = updatedConfig || modelConfig;
      const payload = {
        provider: configToSave.provider,
        model: configToSave.model,
        whisperModel: configToSave.whisperModel,
        apiKey: configToSave.apiKey ?? null,
        ollamaEndpoint: configToSave.ollamaEndpoint ?? null
      };

      console.log('[Web] Saving model config to localStorage:', payload);

      // Track model configuration change
      if (updatedConfig && (
        updatedConfig.provider !== modelConfig.provider ||
        updatedConfig.model !== modelConfig.model
      )) {
        await Analytics.trackModelChanged(
          modelConfig.provider,
          modelConfig.model,
          updatedConfig.provider,
          updatedConfig.model
        );
      }

      // Web version: Save to localStorage
      localStorage.setItem('model_config', JSON.stringify(payload));

      /* Desktop legacy:
      await invokeTauri('api_save_model_config', { ... });
      const { emit } = await import('@tauri-apps/api/event');
      await emit('model-config-updated', payload);
      */

      console.log('Save model config success');
      setModelConfig(payload);

      toast.success("Summary settings Saved successfully (Local Storage)");

      await Analytics.trackSettingsChanged('model_config', `${payload.provider}_${payload.model}`);
    } catch (error) {
      console.error('Failed to save model config:', error);
      toast.error("Failed to save summary settings", { description: String(error) });
      if (error instanceof Error) {
        setError(error.message);
      } else {
        setError('Failed to save model config: Unknown error');
      }
    }
  }, [modelConfig]);

  return {
    modelConfig,
    setModelConfig,
    handleSaveModelConfig,
    isLoading,
  };
}
