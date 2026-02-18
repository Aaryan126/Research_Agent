import type { ChatMessage } from '../types';
import { useAutoScroll } from '../hooks/useAutoScroll';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';

interface ChatContainerProps {
  messages: ChatMessage[];
}

export function ChatContainer({ messages }: ChatContainerProps) {
  const { containerRef, handleScroll } = useAutoScroll<HTMLDivElement>(messages);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto"
    >
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <UserMessage key={msg.id} content={msg.content} />
          ) : (
            <AssistantMessage key={msg.id} message={msg} />
          ),
        )}
      </div>
    </div>
  );
}
