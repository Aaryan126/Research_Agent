import { useEffect, useRef, useCallback } from 'react';

export function useAutoScroll<T extends HTMLElement>(dependency: unknown) {
  const containerRef = useRef<T>(null);
  const isUserScrolledUp = useRef(false);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const threshold = 100;
    isUserScrolledUp.current =
      el.scrollHeight - el.scrollTop - el.clientHeight > threshold;
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || isUserScrolledUp.current) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [dependency]);

  return { containerRef, handleScroll };
}
