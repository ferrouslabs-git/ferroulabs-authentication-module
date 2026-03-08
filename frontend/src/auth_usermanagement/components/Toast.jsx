import { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext(null);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = Date.now() + Math.random();
    const toast = { id, message, type, duration };
    
    setToasts((prev) => [...prev, toast]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
    }

    return id;
  }, []);

  const success = useCallback((message, duration) => showToast(message, 'success', duration), [showToast]);
  const error = useCallback((message, duration) => showToast(message, 'error', duration), [showToast]);
  const warning = useCallback((message, duration) => showToast(message, 'warning', duration), [showToast]);
  const info = useCallback((message, duration) => showToast(message, 'info', duration), [showToast]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value = {
    showToast,
    success,
    error,
    warning,
    info,
    dismissToast,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}

function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;

  return (
    <div style={styles.container}>
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          onDismiss={() => onDismiss(toast.id)}
        />
      ))}
    </div>
  );
}

function Toast({ message, type, onDismiss }) {
  const typeStyles = {
    success: { backgroundColor: '#4caf50', icon: '✓' },
    error: { backgroundColor: '#f44336', icon: '✕' },
    warning: { backgroundColor: '#ff9800', icon: '⚠' },
    info: { backgroundColor: '#2196f3', icon: 'ℹ' },
  };

  const style = typeStyles[type] || typeStyles.info;

  return (
    <div
      style={{
        ...styles.toast,
        backgroundColor: style.backgroundColor,
      }}
      role="alert"
      aria-live="polite"
    >
      <span style={styles.icon}>{style.icon}</span>
      <span style={styles.message}>{message}</span>
      <button
        onClick={onDismiss}
        style={styles.closeButton}
        aria-label="Dismiss notification"
      >
        ×
      </button>
    </div>
  );
}

const styles = {
  container: {
    position: 'fixed',
    top: '20px',
    right: '20px',
    zIndex: 2000,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    maxWidth: '400px',
  },
  toast: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    color: 'white',
    fontSize: '14px',
    animation: 'slideInRight 0.3s ease-out',
    minWidth: '300px',
  },
  icon: {
    fontSize: '18px',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  message: {
    flex: 1,
    lineHeight: '1.4',
  },
  closeButton: {
    background: 'transparent',
    border: 'none',
    color: 'white',
    fontSize: '24px',
    cursor: 'pointer',
    padding: '0 4px',
    lineHeight: '1',
    opacity: 0.8,
    transition: 'opacity 0.2s',
    flexShrink: 0,
  },
};
