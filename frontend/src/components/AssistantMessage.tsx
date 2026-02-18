import { useRef, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import type { AssistantMessage as AssistantMessageType } from '../types';
import { ThinkingIndicator } from './ThinkingIndicator';
import { CombinedReasoningTrace } from './ReasoningTrace';
import { MarkdownRenderer } from './MarkdownRenderer';

const PDF_STYLES = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  div {
    font-family: 'Inter', system-ui, sans-serif;
    color: #1A1A1A;
    line-height: 1.75;
  }
  h1 { font-size: 1.875rem; font-weight: 700; margin-top: 1.5em; margin-bottom: 0.6em; }
  h2 { font-size: 1.5rem; font-weight: 600; margin-top: 1.5em; margin-bottom: 0.6em; }
  h3 { font-size: 1.25rem; font-weight: 600; margin-top: 1em; margin-bottom: 0.4em; }
  h1 + *, h2 + *, h3 + * { margin-top: 0.25em; }
  p { margin-top: 0.5em; margin-bottom: 0.5em; }
  ul, ol { margin-top: 0.4em; margin-bottom: 0.4em; padding-left: 1.5em; list-style: none; }
  ol { counter-reset: li; }
  li { margin-top: 0.15em; margin-bottom: 0.15em; position: relative; }
  ul > li::before { content: "\\2022"; position: absolute; left: -1em; }
  ol > li::before { counter-increment: li; content: counter(li) "."; position: absolute; left: -1.5em; }
  a { color: #D4744A; text-decoration: underline; }
  code { background-color: #F0EDE8; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.875em; }
  pre { background-color: #1e1e1e; color: #d4d4d4; border-radius: 0.5rem; padding: 1rem; overflow-x: auto; margin: 0.75em 0; }
  pre code { background-color: transparent; padding: 0; color: inherit; }
  table { border-collapse: collapse; width: 100%; margin: 0.75em 0; }
  th, td { border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }
  th { background-color: #F0EDE8; font-weight: 600; }
  blockquote { border-left: 3px solid #D4744A; padding-left: 1em; margin: 0.75em 0; color: #6B6B6B; }
`;

interface AssistantMessageProps {
  message: AssistantMessageType;
}

export function AssistantMessage({ message }: AssistantMessageProps) {
  const reportRef = useRef<HTMLDivElement>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const hasTrace = message.traces.length > 0;
  const isActive = message.traces.some((t) => t.isActive);
  const iterationInfo = message.status === 'complete' && message.result
    ? message.result.iteration_info
    : null;

  async function handleDownload() {
    const el = reportRef.current;
    if (!el || isDownloading) return;
    setIsDownloading(true);

    try {
      // Use a hidden iframe so html2canvas doesn't touch the main page
      const iframe = document.createElement('iframe');
      iframe.style.position = 'fixed';
      iframe.style.left = '-10000px';
      iframe.style.top = '0';
      iframe.style.width = '750px';
      iframe.style.border = 'none';
      iframe.style.opacity = '0';
      iframe.style.pointerEvents = 'none';
      document.body.appendChild(iframe);

      const iframeDoc = iframe.contentDocument!;
      iframeDoc.open();
      iframeDoc.write(`<!DOCTYPE html><html><head>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
        <style>${PDF_STYLES}</style>
        </head>
        <body style="margin:0;padding:40px;background:white;">${el.innerHTML}</body></html>`);
      iframeDoc.close();

      // Strip Tailwind classes — html2canvas can't parse oklch() colors
      iframeDoc.querySelectorAll('*').forEach((node) => node.removeAttribute('class'));

      // Wait for font load + layout
      if (iframeDoc.fonts) {
        await iframeDoc.fonts.ready;
      }
      await new Promise((r) => setTimeout(r, 500));
      iframe.style.height = iframeDoc.body.scrollHeight + 'px';
      await new Promise((r) => setTimeout(r, 100));

      const canvas = await html2canvas(iframeDoc.body, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
        windowWidth: 750,
        windowHeight: iframeDoc.body.scrollHeight,
      });

      document.body.removeChild(iframe);

      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 10;
      const usableWidth = pageWidth - margin * 2;
      const usableHeight = pageHeight - margin * 2;

      const pxPerMm = canvas.width / usableWidth;
      const pageHeightPx = Math.floor(usableHeight * pxPerMm);
      const fullCtx = canvas.getContext('2d')!;

      // Scan backwards from targetY to find a white row (gap between lines)
      function findBreakPoint(targetY: number): number {
        const searchRange = Math.floor(pageHeightPx * 0.15);
        for (let y = targetY; y > targetY - searchRange && y > 0; y--) {
          const row = fullCtx.getImageData(0, y, canvas.width, 1).data;
          let isBlank = true;
          for (let i = 0; i < row.length; i += 4) {
            if (row[i] < 245 || row[i + 1] < 245 || row[i + 2] < 245) {
              isBlank = false;
              break;
            }
          }
          if (isBlank) return y;
        }
        return targetY;
      }

      let sliceStart = 0;
      while (sliceStart < canvas.height) {
        if (sliceStart > 0) pdf.addPage();

        const remaining = canvas.height - sliceStart;
        let sliceEnd: number;
        if (remaining <= pageHeightPx) {
          sliceEnd = canvas.height;
        } else {
          sliceEnd = findBreakPoint(sliceStart + pageHeightPx);
        }

        const sliceHeight = sliceEnd - sliceStart;
        const pageCanvas = document.createElement('canvas');
        pageCanvas.width = canvas.width;
        pageCanvas.height = sliceHeight;
        const ctx = pageCanvas.getContext('2d')!;
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, sliceHeight);
        ctx.drawImage(canvas, 0, sliceStart, canvas.width, sliceHeight, 0, 0, canvas.width, sliceHeight);

        const pageImg = pageCanvas.toDataURL('image/jpeg', 0.95);
        const sliceHeightMm = sliceHeight / pxPerMm;
        pdf.addImage(pageImg, 'JPEG', margin, margin, usableWidth, sliceHeightMm);

        sliceStart = sliceEnd;
      }

      const filename = iterationInfo?.includes('Claim verification')
        ? 'claim-verification.pdf'
        : 'literature-review.pdf';
      pdf.save(filename);
    } catch (err) {
      console.error('PDF generation failed:', err);
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="animate-fade-in-up">
      <div className="min-w-0">
        {message.status === 'thinking' && <ThinkingIndicator />}

        {hasTrace && (
          <CombinedReasoningTrace
            traces={message.traces}
            verdicts={message.verdicts}
            iterationInfo={iterationInfo}
            isActive={isActive}
            activeAgent={message.activeAgent}
          />
        )}

        {message.status === 'error' && (
          <div className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3 mt-3">
            {message.error || 'An error occurred during the research workflow.'}
          </div>
        )}

        {message.status === 'complete' && message.result && (
          <div className="mt-2">
            {message.result.report ? (
              <>
                <div ref={reportRef}>
                  <MarkdownRenderer content={message.result.report} />
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={handleDownload}
                    disabled={isDownloading}
                    className="flex items-center gap-1.5 text-sm text-secondary-text
                               hover:text-primary-text transition-colors cursor-pointer
                               border border-gray-200 rounded-lg px-3 py-1.5
                               disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isDownloading ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    {isDownloading ? 'Generating...' : 'Download PDF'}
                  </button>
                </div>
              </>
            ) : (
              <p className="text-sm text-secondary-text">
                No report content found in the workflow execution.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
