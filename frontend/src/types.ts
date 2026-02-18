export type ResearchMode = 'research' | 'verify';

export type MessageRole = 'user' | 'assistant';

export type AssistantStatus = 'thinking' | 'streaming' | 'complete' | 'error';

// --- Reasoning trace types ---

export interface ReasoningEvent {
  type: 'reasoning';
  text: string;
}

export interface ToolCallEvent {
  type: 'tool_call';
  tool_id: string;
  params: Record<string, unknown>;
}

export interface ToolResultEvent {
  type: 'tool_result';
  tool_id: string;
  results: unknown;
}

export interface ToolProgressEvent {
  type: 'tool_progress';
  tool_call_id: string;
  message: string;
}

export interface MessageChunkEvent {
  type: 'message_chunk';
  text: string;
}

export type TraceEvent = ReasoningEvent | ToolCallEvent | ToolResultEvent | ToolProgressEvent | MessageChunkEvent;

export interface AgentTrace {
  agent: string;
  agentId: string;
  iteration: number;
  events: TraceEvent[];
  isActive: boolean;
  finalMessage: string;
}

export interface VerdictData {
  verdict: string;
  iteration: number;
}

// --- Message types ---

export interface ResultData {
  report: string | null;
  review: string | null;
  iteration_info: string | null;
  iterations: string[];
}

export interface UserMessage {
  id: string;
  role: 'user';
  content: string;
}

export interface AssistantMessage {
  id: string;
  role: 'assistant';
  status: AssistantStatus;
  traces: AgentTrace[];
  activeAgent: string | null;
  verdicts: VerdictData[];
  result: ResultData | null;
  error: string | null;
}

export type ChatMessage = UserMessage | AssistantMessage;
