import { useState, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { ArrowUp } from 'lucide-react';

interface InputBarProps {
  onSubmit: (topic: string) => void;
  isLoading: boolean;
  bare?: boolean;
  placeholder?: string;
}

export function InputBar({ onSubmit, isLoading, bare, placeholder }: InputBarProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  return (
    <div className={bare ? '' : 'shrink-0 bg-cream px-4 py-3'}>
      <form
        onSubmit={handleSubmit}
        className={bare ? '' : 'max-w-4xl mx-auto'}
      >
        <div className="flex items-center bg-white rounded-2xl shadow-sm hover:shadow-md transition-shadow border border-gray-200 px-5 py-3">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={placeholder || 'Enter a research topic...'}
            rows={1}
            disabled={isLoading}
            style={{ lineHeight: '1.5' }}
            className="flex-1 resize-none min-h-0
                       text-base text-primary-text placeholder-secondary-text
                       focus:outline-none
                       disabled:opacity-50 disabled:cursor-not-allowed
                       bg-transparent"
          />
          <button
            type="submit"
            disabled={!value.trim() || isLoading}
            className="shrink-0 ml-3 w-8 h-8 rounded-lg bg-terracotta text-white
                       flex items-center justify-center
                       hover:bg-terracotta-hover transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <ArrowUp className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
