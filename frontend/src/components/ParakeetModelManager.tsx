import React from 'react';

interface ParakeetModelManagerProps {
  selectedModel: string;
  onModelSelect: (model: string) => void;
  autoSave?: boolean;
}

export function ParakeetModelManager({ selectedModel, onModelSelect, autoSave }: ParakeetModelManagerProps) {
  return (
    <div className="p-4 bg-gray-50 border rounded-lg">
      <p className="text-sm text-gray-500">Parakeet Model Manager is not available in web version.</p>
    </div>
  );
}
