import { useEffect, useRef } from 'react';

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'danger', // 'danger' or 'warning'
}) {
  const confirmButtonRef = useRef(null);

  useEffect(() => {
    if (isOpen && confirmButtonRef.current) {
      confirmButtonRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onCancel();
    }
  };

  return (
    <div
      style={styles.overlay}
      onClick={onCancel}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-message"
    >
      <div
        style={styles.dialog}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={styles.header}>
          <h3 id="confirm-dialog-title" style={styles.title}>
            {title}
          </h3>
        </div>
        
        <div style={styles.body}>
          <p id="confirm-dialog-message" style={styles.message}>
            {message}
          </p>
        </div>
        
        <div style={styles.footer}>
          <button
            onClick={onCancel}
            style={styles.cancelButton}
            type="button"
          >
            {cancelText}
          </button>
          <button
            ref={confirmButtonRef}
            onClick={onConfirm}
            style={{
              ...styles.confirmButton,
              ...(variant === 'danger' ? styles.dangerButton : styles.warningButton),
            }}
            type="button"
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    animation: 'fadeIn 0.15s ease-out',
  },
  dialog: {
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
    maxWidth: '400px',
    width: '90%',
    animation: 'slideUp 0.2s ease-out',
  },
  header: {
    padding: '20px 24px 16px',
    borderBottom: '1px solid #e0e0e0',
  },
  title: {
    margin: 0,
    fontSize: '18px',
    fontWeight: '600',
    color: '#333',
  },
  body: {
    padding: '20px 24px',
  },
  message: {
    margin: 0,
    fontSize: '14px',
    lineHeight: '1.5',
    color: '#666',
  },
  footer: {
    padding: '16px 24px 20px',
    display: 'flex',
    gap: '12px',
    justifyContent: 'flex-end',
  },
  cancelButton: {
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '500',
    backgroundColor: '#f5f5f5',
    border: '1px solid #ddd',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  confirmButton: {
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '500',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    color: 'white',
    transition: 'all 0.2s',
  },
  dangerButton: {
    backgroundColor: '#d32f2f',
  },
  warningButton: {
    backgroundColor: '#f57c00',
  },
};
