"use client";

import { useState, useRef } from 'react';
import { Upload, File, X } from 'lucide-react';
import { toast } from 'sonner';

interface FileContextUploadProps {
  onFileContent: (content: string, fileName: string) => void;
}

export function FileContextUpload({ onFileContent }: FileContextUploadProps) {
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; content: string }>>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) {
      console.log('No files selected');
      return;
    }

    console.log(`📁 Processing ${files.length} file(s)...`);

    for (const file of Array.from(files)) {
      try {
        console.log(`📄 Reading file: ${file.name} (${file.type}, ${file.size} bytes)`);
        
        // Simplified validation - accept any text-readable file
        const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        const validExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf', '.json'];
        
        if (!validExtensions.includes(extension)) {
          console.warn(`Invalid extension: ${extension}`);
          toast.warning(`File type may not be supported: ${extension}`, {
            description: 'Best results with: .txt, .md, .json'
          });
          // Continue anyway - try to read it
        }

        // Read file content
        const content = await readFileContent(file);
        
        console.log(`✅ File read successfully: ${content.length} characters`);
        
        if (content.trim()) {
          setUploadedFiles(prev => [...prev, { name: file.name, content }]);
          onFileContent(content, file.name);
          toast.success(`File uploaded: ${file.name}`, {
            description: `${content.length} characters added to context`
          });
        } else {
          toast.error(`File is empty: ${file.name}`);
        }
      } catch (error) {
        console.error('File upload error:', error);
        toast.error(`Failed to read ${file.name}`, {
          description: String(error)
        });
      }
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const content = e.target?.result as string;
        
        // For PDF files, show warning that text extraction is basic
        if (file.name.toLowerCase().endsWith('.pdf')) {
          toast.warning('PDF text extraction is basic', {
            description: 'For best results, use .txt or .md files'
          });
        }
        
        resolve(content);
      };
      
      reader.onerror = () => {
        reject(new Error('Failed to read file'));
      };
      
      // Read as text
      reader.readAsText(file);
    });
  };

  const handleRemoveFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
    toast.info('File removed from context');
  };

  return (
    <div className="mt-2">
      {/* Upload Button */}
      <button
        type="button"
        data-no-citation="true"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          console.log('📁 Upload button clicked, triggering file input...');
          if (fileInputRef.current) {
            fileInputRef.current.click();
          }
        }}
        className="w-full flex items-center justify-center gap-2 px-3 py-2 border-2 border-dashed border-gray-300 rounded-md hover:border-indigo-400 hover:bg-indigo-50 transition-colors text-sm text-gray-600 hover:text-indigo-600 cursor-pointer"
      >
        <Upload className="w-4 h-4" />
        <span>Upload context file (txt, md, pdf, docx, json)</span>
      </button>
      
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".txt,.md,.pdf,.doc,.docx,.json,text/*"
        onChange={handleFileUpload}
        className="hidden"
        onClick={(e) => console.log('📁 File input clicked')}
      />

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="mt-2 space-y-1">
          {uploadedFiles.map((file, index) => (
            <div
              key={index}
              className="flex items-center justify-between gap-2 px-3 py-2 bg-indigo-50 border border-indigo-200 rounded text-sm"
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <File className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                <span className="text-gray-800 truncate">{file.name}</span>
                <span className="text-xs text-gray-500 flex-shrink-0">
                  ({file.content.length} chars)
                </span>
              </div>
              <button
                onClick={() => handleRemoveFile(index)}
                className="text-gray-500 hover:text-red-600 transition-colors flex-shrink-0"
                title="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
