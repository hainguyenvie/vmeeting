'use client';

import React from 'react';

interface CitationLinkProps {
  timestamp: string; // Format: "03:25" or "MM:SS"
  onJumpToTranscript?: (timeInSeconds: number) => void;
}

/**
 * Citation link component that converts timestamps [MM:SS] into clickable links
 * When clicked, scrolls to the corresponding transcript segment
 */
export function CitationLink({ timestamp, onJumpToTranscript }: CitationLinkProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    
    // Parse timestamp MM:SS to total seconds
    const parts = timestamp.split(':');
    if (parts.length === 2) {
      const minutes = parseInt(parts[0], 10);
      const seconds = parseInt(parts[1], 10);
      const totalSeconds = minutes * 60 + seconds;
      
      console.log(`🔗 Citation clicked: [${timestamp}] → ${totalSeconds}s`);
      
      if (onJumpToTranscript) {
        onJumpToTranscript(totalSeconds);
      } else {
        // Fallback: scroll to element with data-time attribute
        const transcriptElement = document.querySelector(`[data-time="${totalSeconds}"]`);
        if (transcriptElement) {
          transcriptElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
          // Highlight effect
          transcriptElement.classList.add('bg-yellow-200');
          setTimeout(() => {
            transcriptElement.classList.remove('bg-yellow-200');
          }, 2000);
        }
      }
    }
  };

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center text-blue-600 hover:text-blue-800 hover:underline cursor-pointer transition-colors mx-0.5 font-mono text-sm"
      title={`Jump to ${timestamp} in transcript`}
    >
      [{timestamp}]
    </button>
  );
}

/**
 * Parse text and replace [MM:SS] patterns with CitationLink components
 */
export function parseCitations(
  text: string,
  onJumpToTranscript?: (timeInSeconds: number) => void
): React.ReactNode[] {
  // Pattern: [MM:SS] where MM and SS are 2-digit numbers
  const pattern = /\[(\d{2}:\d{2})\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    // Add text before the timestamp
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    // Add CitationLink component
    const timestamp = match[1];
    parts.push(
      <CitationLink
        key={`citation-${match.index}`}
        timestamp={timestamp}
        onJumpToTranscript={onJumpToTranscript}
      />
    );

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts;
}
