import { Sparkles } from 'lucide-react';

export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 text-secondary-text text-lg">
      <Sparkles className="w-4 h-4 text-terracotta animate-pulse" />
      <span>Researching</span>
      <div className="flex gap-1">
        <span className="thinking-dot w-1.5 h-1.5 rounded-full bg-terracotta inline-block" />
        <span className="thinking-dot w-1.5 h-1.5 rounded-full bg-terracotta inline-block" />
        <span className="thinking-dot w-1.5 h-1.5 rounded-full bg-terracotta inline-block" />
      </div>
    </div>
  );
}
