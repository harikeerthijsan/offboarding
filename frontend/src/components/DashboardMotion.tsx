import { useEffect, useRef, type ReactNode } from 'react';
import '../styles/dashboard-motion.css';

/** Presentation-only motion: no state updates, click handlers, or data access. */
export default function DashboardMotion({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const enabled = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
    let frame = 0;
    let card: HTMLElement | null = null;
    const reset = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      element.style.removeProperty('--motion-x');
      element.style.removeProperty('--motion-y');
      card?.style.removeProperty('--glow-opacity');
      card = null;
    };
    const move = (event: PointerEvent) => {
      if (!enabled.matches || event.pointerType !== 'mouse') return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const bounds = element.getBoundingClientRect();
        element.style.setProperty('--motion-x', `${((event.clientX - bounds.left) / bounds.width - 0.5) * 16}px`);
        element.style.setProperty('--motion-y', `${((event.clientY - bounds.top) / bounds.height - 0.5) * 12}px`);
        const next = event.target instanceof Element ? event.target.closest<HTMLElement>('.card, .dstat') : null;
        if (card !== next) card?.style.removeProperty('--glow-opacity');
        card = next;
        if (card) {
          const rect = card.getBoundingClientRect();
          card.style.setProperty('--glow-x', `${event.clientX - rect.left}px`);
          card.style.setProperty('--glow-y', `${event.clientY - rect.top}px`);
          card.style.setProperty('--glow-opacity', '1');
        }
      });
    };
    element.addEventListener('pointermove', move, { passive: true });
    element.addEventListener('pointerleave', reset);
    enabled.addEventListener('change', reset);
    return () => {
      reset();
      element.removeEventListener('pointermove', move);
      element.removeEventListener('pointerleave', reset);
      enabled.removeEventListener('change', reset);
    };
  }, []);

  return (
    <div className="dash dash-motion" ref={root}>
      <div className="dash-atmosphere" aria-hidden="true">
        <div className="dash-aurora" />
        <div className="dash-wave" />
        <svg className="dash-ribbons" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMin slice">
          <defs>
            <linearGradient id="dashboard-ribbon" x1="0" y1="0" x2="1" y2="1">
              <stop stopColor="#22b9ff" stopOpacity=".45" />
              <stop offset=".5" stopColor="#5274f9" stopOpacity=".28" />
              <stop offset="1" stopColor="#b77af5" stopOpacity=".38" />
            </linearGradient>
          </defs>
          <path d="M-80 360 C160 100 340 530 640 210 S1030 10 1300 90" stroke="url(#dashboard-ribbon)" strokeWidth="72" fill="none" />
          <path d="M-80 330 C160 70 340 500 640 180 S1030 -20 1300 60" stroke="#fff" strokeOpacity=".7" strokeWidth="2" fill="none" />
          <path d="M-80 395 C160 135 340 565 640 245 S1030 45 1300 125" stroke="#85caff" strokeOpacity=".45" strokeWidth="2" fill="none" />
        </svg>
        <span className="dash-light dash-light-one" />
        <span className="dash-light dash-light-two" />
        <span className="dash-light dash-light-three" />
      </div>
      {children}
    </div>
  );
}
