import { useState, useCallback, useMemo } from 'react';
import type { ChatMessage, AssistantMessage as AssistantMsg, AgentTrace, TraceEvent, ResearchMode } from './types';
import { useResearchStream } from './hooks/useResearchStream';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatContainer } from './components/ChatContainer';
import { InputBar } from './components/InputBar';
import { EmptyState } from './components/EmptyState';

let nextId = 0;
function genId() {
  return `msg-${++nextId}`;
}

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [mode, setMode] = useState<ResearchMode>('research');
  const { startStream } = useResearchStream();

  const conversations = useMemo(() => {
    return messages
      .filter((m) => m.role === 'user')
      .map((m) => ({ id: m.id, title: m.content }));
  }, [messages]);

  const handleToggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => !prev);
  }, []);

  const handleNewChat = useCallback(() => {
    if (isLoading) return;
    setMessages([]);
  }, [isLoading]);

  const updateAssistant = useCallback(
    (id: string, updater: (prev: AssistantMsg) => Partial<AssistantMsg>) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id && m.role === 'assistant'
            ? { ...m, ...updater(m as AssistantMsg) }
            : m,
        ),
      );
    },
    [],
  );

  const handleSubmit = useCallback(
    (topic: string, submitMode?: ResearchMode) => {
      if (isLoading) return;

      const activeMode = submitMode || mode;
      setMode(activeMode);

      const userId = genId();
      const assistantId = genId();

      const userMsg: ChatMessage = { id: userId, role: 'user', content: topic };
      const assistantMsg: AssistantMsg = {
        id: assistantId,
        role: 'assistant',
        status: 'thinking',
        traces: [],
        activeAgent: null,
        verdicts: [],
        result: null,
        error: null,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsLoading(true);

      startStream(topic, {
        onAgentStart(data) {
          updateAssistant(assistantId, (prev) => {
            const newTrace: AgentTrace = {
              agent: data.agent,
              agentId: data.agent_id,
              iteration: data.iteration,
              events: [],
              isActive: true,
              finalMessage: '',
            };
            return {
              status: 'streaming',
              traces: [...prev.traces, newTrace],
              activeAgent: data.agent,
            };
          });
        },

        onTraceEvent(event: TraceEvent, agent: string, iteration: number) {
          updateAssistant(assistantId, (prev) => {
            const traces = prev.traces.map((t) => {
              if (t.agent !== agent || t.iteration !== iteration) return t;
              const updatedTrace = { ...t, events: [...t.events, event] };
              if (event.type === 'message_chunk') {
                updatedTrace.finalMessage = t.finalMessage + event.text;
              }
              return updatedTrace;
            });
            return { traces };
          });
        },

        onAgentEnd(data) {
          updateAssistant(assistantId, (prev) => {
            const traces = prev.traces.map((t) => {
              if (t.agent !== data.agent || t.iteration !== data.iteration) return t;
              return { ...t, isActive: false };
            });
            return { traces, activeAgent: null };
          });
        },

        onVerdict(data) {
          updateAssistant(assistantId, (prev) => ({
            verdicts: [...prev.verdicts, data],
          }));
        },

        onResult(data) {
          updateAssistant(assistantId, () => ({
            status: 'complete',
            result: data,
            activeAgent: null,
          }));
        },

        onError(message) {
          updateAssistant(assistantId, () => ({
            status: 'error',
            error: message,
            activeAgent: null,
          }));
        },

        onDone() {
          setIsLoading(false);
          updateAssistant(assistantId, (prev) => {
            if (prev.status === 'thinking' || prev.status === 'streaming') {
              return { status: 'error', error: 'Stream ended unexpectedly', activeAgent: null };
            }
            return {};
          });
        },
      }, activeMode);
    },
    [isLoading, mode, startStream, updateAssistant],
  );

  return (
    <>
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onNewChat={handleNewChat}
        conversations={conversations}
      />
      <Header onToggleSidebar={handleToggleSidebar} />
      {messages.length === 0 ? (
        <EmptyState onSubmit={handleSubmit} isLoading={isLoading} />
      ) : (
        <>
          <ChatContainer messages={messages} />
          <InputBar
            onSubmit={handleSubmit}
            isLoading={isLoading}
            placeholder={mode === 'verify' ? 'Enter a claim to verify...' : 'Enter a research topic...'}
          />
        </>
      )}
    </>
  );
}

export default App;
