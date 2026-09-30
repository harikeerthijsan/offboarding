import { useEffect } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  onClose: () => void;
  children: React.ReactNode;
  maxWidth?: number;
  closeOnOverlay?: boolean;
}

/**
 * Centered modal rendered via a portal to <body> so it always overlays the whole
 * viewport — never trapped inside a card/section that has overflow/transform.
 */
export default function Modal({ onClose, children, maxWidth = 440, closeOnOverlay = true }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return createPortal(
    <div className="modal-overlay" onClick={() => closeOnOverlay && onClose()}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth }}>
        {children}
      </div>
    </div>,
    document.body,
  );
}
