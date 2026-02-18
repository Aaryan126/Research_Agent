interface UserMessageProps {
  content: string;
}

export function UserMessage({ content }: UserMessageProps) {
  return (
    <div className="flex justify-end animate-fade-in-up">
      <div className="max-w-[85%]">
        <div className="bg-warm-tan rounded-2xl px-5 py-3.5">
          <p className="text-base leading-relaxed text-primary-text whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    </div>
  );
}
