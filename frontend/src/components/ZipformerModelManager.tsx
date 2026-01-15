import React from 'react';

interface ZipformerModelManagerProps {
    selectedModel: string;
    onModelSelect: (model: string) => void;
    autoSave?: boolean;
}

export function ZipformerModelManager({ selectedModel, onModelSelect, autoSave }: ZipformerModelManagerProps) {
    return (
        <div className="p-4 bg-gray-50 border rounded-lg">
            <p className="text-sm text-gray-500">Zipformer Model Manager is not available in web version.</p>
        </div>
    );
}
