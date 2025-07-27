import { useState, useCallback } from 'react';
import { ToastMessage } from '@/components/ui/Toast';

let toastIdCounter = 0;

export const useToast = () => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((
    type: ToastMessage['type'],
    title: string,
    message?: string,
    options?: {
      duration?: number;
      action?: {
        label: string;
        onClick: () => void;
      };
    }
  ) => {
    const id = `toast-${++toastIdCounter}`;
    const newToast: ToastMessage = {
      id,
      type,
      title,
      message,
      duration: options?.duration,
      action: options?.action,
    };

    setToasts(prev => [...prev, newToast]);
    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const clearAllToasts = useCallback(() => {
    setToasts([]);
  }, []);

  // Convenience methods
  const success = useCallback((title: string, message?: string, options?: { duration?: number; action?: { label: string; onClick: () => void } }) => {
    return addToast('success', title, message, options);
  }, [addToast]);

  const error = useCallback((title: string, message?: string, options?: { duration?: number; action?: { label: string; onClick: () => void } }) => {
    return addToast('error', title, message, options);
  }, [addToast]);

  const warning = useCallback((title: string, message?: string, options?: { duration?: number; action?: { label: string; onClick: () => void } }) => {
    return addToast('warning', title, message, options);
  }, [addToast]);

  const info = useCallback((title: string, message?: string, options?: { duration?: number; action?: { label: string; onClick: () => void } }) => {
    return addToast('info', title, message, options);
  }, [addToast]);

  return {
    toasts,
    addToast,
    removeToast,
    clearAllToasts,
    success,
    error,
    warning,
    info,
  };
}; 