import { useState } from 'react';
import { Sparkles, ChevronDown, ChevronRight, Check } from 'lucide-react';
import type { AgentTrace, TraceEvent, VerdictData } from '../types';

interface TraceEventCardProps {
  event: TraceEvent;
}

function TraceEventCard({ event }: TraceEventCardProps) {
  switch (event.type) {
    case 'reasoning':
      return (
        <div className="flex items-start gap-1.5 py-1 text-xs text-secondary-text">
          <Check className="w-3 h-3 mt-0.5 shrink-0 stroke-1 text-green-400" />
          <span className="whitespace-pre-wrap">{event.text}</span>
        </div>
      );
    case 'tool_call': {
      const query = (event.params?.query as string)
        || (event.params?.input as string)
        || JSON.stringify(event.params);
      return (
        <div className="flex items-start gap-1.5 py-2 text-xs">
          <Check className="w-3 h-3 mt-0.5 shrink-0 stroke-1 text-green-400" />
          <div>
            <span className="font-medium text-primary-text">{event.tool_id}</span>
            <span className="text-secondary-text ml-1">{query}</span>
          </div>
        </div>
      );
    }
    case 'tool_result': {
      const results = event.results;
      let summary = 'Result received';
      if (Array.isArray(results)) {
        summary = `${results.length} result${results.length !== 1 ? 's' : ''} returned`;
      } else if (typeof results === 'string') {
        summary = results.length > 120 ? results.slice(0, 120) + '...' : results;
      }
      return (
        <div className="flex items-start gap-1.5 py-2 text-xs text-secondary-text">
          <Check className="w-3 h-3 mt-0.5 shrink-0 stroke-1 text-green-400" />
          <span>{summary}</span>
        </div>
      );
    }
    case 'tool_progress':
      return (
        <div className="flex items-start gap-1.5 py-1.5 text-xs text-secondary-text">
          <Check className="w-3 h-3 mt-0.5 shrink-0 stroke-1 text-green-400" />
          <span>{event.message}</span>
        </div>
      );
    case 'message_chunk':
      return null;
    default:
      return null;
  }
}

interface AgentDividerProps {
  agent: string;
  iteration: number;
}

function AgentDivider({ agent, iteration }: AgentDividerProps) {
  return (
    <div className="flex items-center gap-2 pt-3 pb-1">
      <span className="text-[11px] font-medium text-terracotta uppercase tracking-wide">
        {agent} &middot; Iteration {iteration}
      </span>
      <div className="flex-1 border-t border-gray-200" />
    </div>
  );
}

interface CombinedReasoningTraceProps {
  traces: AgentTrace[];
  verdicts: VerdictData[];
  iterationInfo?: string | null;
  isActive: boolean;
  activeAgent?: string | null;
}

export function CombinedReasoningTrace({ traces, verdicts, iterationInfo, isActive, activeAgent }: CombinedReasoningTraceProps) {
  const [isOpen, setIsOpen] = useState(false);

  const uniqueAgents = new Set(traces.map((t) => t.agent));
  const totalToolCalls = traces.reduce(
    (sum, t) => sum + t.events.filter((e) => e.type === 'tool_call').length,
    0,
  );

  const stats: string[] = [];
  if (uniqueAgents.size > 0) {
    stats.push(`${uniqueAgents.size} agent${uniqueAgents.size !== 1 ? 's' : ''}`);
  }
  if (totalToolCalls > 0) {
    stats.push(`${totalToolCalls} tool call${totalToolCalls !== 1 ? 's' : ''}`);
  }

  // Get the latest meaningful event text for the live snippet
  let latestSnippet = '';
  if (isActive) {
    for (let i = traces.length - 1; i >= 0; i--) {
      const events = traces[i].events;
      for (let j = events.length - 1; j >= 0; j--) {
        const e = events[j];
        if (e.type === 'reasoning' && e.text) {
          latestSnippet = e.text;
          break;
        }
        if (e.type === 'tool_call') {
          latestSnippet = e.tool_id + ': ' + ((e.params?.query as string) || (e.params?.input as string) || '');
          break;
        }
        if (e.type === 'tool_progress' && e.message) {
          latestSnippet = e.message;
          break;
        }
      }
      if (latestSnippet) break;
    }
    if (latestSnippet.length > 120) {
      latestSnippet = latestSnippet.slice(0, 120) + '...';
    }
  }

  const label = isActive
    ? latestSnippet || (activeAgent ? `${activeAgent} working...` : 'Working...')
    : 'Reasoning Trace';

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-1.5 py-1.5 text-sm
                   text-secondary-text hover:opacity-70 transition-opacity
                   cursor-pointer overflow-hidden"
      >
        {isActive ? (
          <Sparkles className="w-3.5 h-3.5 shrink-0 text-terracotta animate-pulse" />
        ) : isOpen ? (
          <ChevronDown className="w-3.5 h-3.5 shrink-0" />
        ) : null}
        <span className="truncate">{label}</span>
        {stats.length > 0 && !isActive && (
          <span className="shrink-0 text-[10px] text-secondary-text bg-warm-tan rounded-full px-1.5 py-0.5 ml-auto">
            {stats.join(' · ')}
          </span>
        )}
        {!isOpen && (
          <ChevronRight className="w-3.5 h-3.5 shrink-0 text-secondary-text opacity-50" />
        )}
      </button>
      {isOpen && (
        <div className="pl-5 pb-1 max-h-80 overflow-y-auto">
          {traces.map((trace, traceIdx) => {
            const displayEvents = trace.events.filter((e) => e.type !== 'message_chunk');
            return (
              <div key={`${trace.agent}-${trace.iteration}-${traceIdx}`}>
                <AgentDivider agent={trace.agent} iteration={trace.iteration} />
                {displayEvents.map((event, i) => (
                  <TraceEventCard key={i} event={event} />
                ))}
              </div>
            );
          })}

          {verdicts.length > 0 && (
            <div className="pt-2 space-y-0.5">
              {verdicts.map((v, i) => (
                <p
                  key={i}
                  className={`text-[11px] ${
                    v.verdict === 'PASS' ? 'text-green-600' : 'text-amber-600'
                  }`}
                >
                  Iteration {v.iteration}: {v.verdict}
                </p>
              ))}
              {iterationInfo && (
                <p className="text-[11px] text-secondary-text">
                  Final report from: {iterationInfo}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
