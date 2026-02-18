import { useState } from 'react';
import type { ResearchMode } from '../types';
import { InputBar } from './InputBar';

interface EmptyStateProps {
  onSubmit: (topic: string, mode: ResearchMode) => void;
  isLoading: boolean;
}

export function EmptyState({ onSubmit, isLoading }: EmptyStateProps) {
  const [mode, setMode] = useState<ResearchMode>('research');

  const placeholder = mode === 'research'
    ? 'Enter a research topic...'
    : 'Enter a claim to verify...';

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 -mt-20">
      <h2 className="text-4xl font-normal text-primary-text mb-6">
        How can I help you?
      </h2>

      <div className="flex rounded-lg bg-warm-tan p-1 mb-4">
        <button
          onClick={() => setMode('research')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
            mode === 'research'
              ? 'bg-white text-primary-text shadow-sm'
              : 'text-secondary-text hover:text-primary-text'
          }`}
        >
          Literature Review
        </button>
        <button
          onClick={() => setMode('verify')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
            mode === 'verify'
              ? 'bg-white text-primary-text shadow-sm'
              : 'text-secondary-text hover:text-primary-text'
          }`}
        >
          Verify Claim
        </button>
      </div>

      <div className="w-full max-w-2xl mx-auto">
        <InputBar
          onSubmit={(topic) => onSubmit(topic, mode)}
          isLoading={isLoading}
          bare
          placeholder={placeholder}
        />
      </div>
    </div>
  );
}
