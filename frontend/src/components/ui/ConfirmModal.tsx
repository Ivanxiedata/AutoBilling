import React from 'react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  type = 'warning',
  onConfirm,
  onCancel,
  loading = false
}) => {
  if (!isOpen) return null;

  const getIcon = () => {
    switch (type) {
      case 'danger':
        return '🗑️';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      default:
        return '❓';
    }
  };

  const getConfirmButtonStyles = () => {
    const baseStyles = "px-4 py-2 rounded-md font-medium transition duration-200 disabled:opacity-50";
    switch (type) {
      case 'danger':
        return `${baseStyles} bg-red-600 text-white hover:bg-red-700`;
      case 'warning':
        return `${baseStyles} bg-yellow-600 text-white hover:bg-yellow-700`;
      case 'info':
        return `${baseStyles} bg-blue-600 text-white hover:bg-blue-700`;
      default:
        return `${baseStyles} bg-gray-600 text-white hover:bg-gray-700`;
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
      <div className="relative p-5 border w-96 shadow-lg rounded-md bg-white mx-4">
        <div className="mt-3">
          <div className="flex items-center space-x-3 mb-4">
            <span className="text-2xl">{getIcon()}</span>
            <h3 className="text-lg font-medium text-gray-900">{title}</h3>
          </div>
          
          <p className="text-gray-600 mb-6">{message}</p>
          
          <div className="flex space-x-3 justify-end">
            <button
              onClick={onCancel}
              disabled={loading}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition duration-200 disabled:opacity-50"
            >
              {cancelText}
            </button>
            <button
              onClick={onConfirm}
              disabled={loading}
              className={getConfirmButtonStyles()}
            >
              {loading ? (
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Processing...</span>
                </div>
              ) : (
                confirmText
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal; 