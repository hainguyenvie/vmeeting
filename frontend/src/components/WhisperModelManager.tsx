import React from 'react';

interface ModelManagerProps {
  selectedModel?: string;
  onModelSelect?: (modelName: string) => void;
  className?: string;
  autoSave?: boolean;
}

export function ModelManager({
  selectedModel,
  onModelSelect,
  className = '',
  autoSave = false
}: ModelManagerProps) {
  return (
    <div className={`p-4 border rounded bg-gray-50 ${className}`}>
      <p className="text-gray-500 text-sm">
        Whisper Model Management is not available in the web version.
        <br />
        Using default server-side configuration.
      </p>
    </div>
  );
}
