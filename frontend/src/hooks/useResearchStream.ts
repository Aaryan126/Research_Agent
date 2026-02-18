import { useCallback, useRef } from 'react';
import type { ResultData, VerdictData, TraceEvent, ResearchMode } from '../types';

interface AgentStartData {
  agent: string;
  agent_id: string;
  iteration: number;
}

interface AgentEndData {
  agent: string;
  iteration: number;
}

export interface StreamCallbacks {
  onAgentStart: (data: AgentStartData) => void;
  onTraceEvent: (event: TraceEvent, agent: string, iteration: number) => void;
  onAgentEnd: (data: AgentEndData) => void;
  onVerdict: (data: VerdictData) => void;
  onResult: (data: ResultData) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/research';

function dispatchEvent(eventType: string, data: Record<string, unknown>, callbacks: StreamCallbacks) {
  switch (eventType) {
    case 'agent_start':
      callbacks.onAgentStart(data as unknown as AgentStartData);
      break;
    case 'reasoning':
      callbacks.onTraceEvent(
        { type: 'reasoning', text: (data.text as string) || '' },
        data.agent as string,
        data.iteration as number,
      );
      break;
    case 'tool_call':
      callbacks.onTraceEvent(
        { type: 'tool_call', tool_id: (data.tool_id as string) || '', params: (data.params as Record<string, unknown>) || {} },
        data.agent as string,
        data.iteration as number,
      );
      break;
    case 'tool_result':
      callbacks.onTraceEvent(
        { type: 'tool_result', tool_id: (data.tool_id as string) || '', results: data.results },
        data.agent as string,
        data.iteration as number,
      );
      break;
    case 'tool_progress':
      callbacks.onTraceEvent(
        { type: 'tool_progress', tool_call_id: (data.tool_call_id as string) || '', message: (data.message as string) || '' },
        data.agent as string,
        data.iteration as number,
      );
      break;
    case 'message_chunk':
      callbacks.onTraceEvent(
        { type: 'message_chunk', text: (data.text as string) || (data.content as string) || '' },
        data.agent as string,
        data.iteration as number,
      );
      break;
    case 'agent_end':
      callbacks.onAgentEnd(data as unknown as AgentEndData);
      break;
    case 'verdict':
      callbacks.onVerdict(data as unknown as VerdictData);
      break;
    case 'result':
      callbacks.onResult(data as unknown as ResultData);
      break;
    case 'error':
      callbacks.onError((data.message as string) || 'Unknown error');
      break;
    case 'done':
      callbacks.onDone();
      break;
  }
}

export function useResearchStream() {
  const abortRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (topic: string, callbacks: StreamCallbacks, mode: ResearchMode = 'research') => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic, mode }),
          signal: controller.signal,
        });

        if (!response.ok) {
          callbacks.onError(`Server error: ${response.status}`);
          callbacks.onDone();
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          callbacks.onError('No response body');
          callbacks.onDone();
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          let currentEvent = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith('data: ') && currentEvent) {
              try {
                const data = JSON.parse(line.slice(6));
                dispatchEvent(currentEvent, data, callbacks);
              } catch {
                // Skip malformed JSON
              }
              currentEvent = '';
            } else if (line.trim() === '') {
              currentEvent = '';
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        callbacks.onError(err instanceof Error ? err.message : 'Connection failed');
        callbacks.onDone();
      }
    },
    [],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { startStream, cancel };
}
