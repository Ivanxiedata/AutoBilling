import React from 'react';

interface ProgressStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  description?: string;
  progress?: number; // 0-100
}

interface ProgressModalProps {
  isOpen: boolean;
  title: string;
  steps: ProgressStep[];
  overallProgress: number; // 0-100
  currentStep?: string;
  onCancel?: () => void;
  canCancel?: boolean;
}

const ProgressModal: React.FC<ProgressModalProps> = ({
  isOpen,
  title,
  steps,
  overallProgress,
  currentStep,
  onCancel,
  canCancel = false
}) => {
  if (!isOpen) return null;

  const getStepIcon = (status: ProgressStep['status']) => {
    switch (status) {
      case 'completed':
        return '✅';
      case 'running':
        return '🔄';
      case 'failed':
        return '❌';
      case 'pending':
      default:
        return '⏳';
    }
  };

  const getStepColor = (status: ProgressStep['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'running':
        return 'text-blue-600';
      case 'failed':
        return 'text-red-600';
      case 'pending':
      default:
        return 'text-gray-400';
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
      <div className="relative p-6 border w-96 max-w-md shadow-lg rounded-md bg-white mx-4">
        <div className="mb-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
          
          {/* Overall Progress Bar */}
          <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
          
          {/* Progress Percentage */}
          <div className="text-center mb-4">
            <span className="text-2xl font-bold text-gray-900">{Math.round(overallProgress)}%</span>
            <p className="text-sm text-gray-500">Complete</p>
          </div>
        </div>

        {/* Steps List */}
        <div className="space-y-3 mb-6 max-h-64 overflow-y-auto">
          {steps.map((step) => (
            <div
              key={step.id}
              className={`flex items-start space-x-3 p-3 rounded-lg transition-all duration-200 ${
                step.status === 'running' ? 'bg-blue-50 border border-blue-200' :
                step.status === 'completed' ? 'bg-green-50' :
                step.status === 'failed' ? 'bg-red-50' :
                'bg-gray-50'
              }`}
            >
              <div className="flex-shrink-0 mt-0.5">
                <span className="text-lg">{getStepIcon(step.status)}</span>
              </div>
              
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${getStepColor(step.status)}`}>
                  {step.name}
                </p>
                {step.description && (
                  <p className="text-xs text-gray-500 mt-1">{step.description}</p>
                )}
                
                {/* Individual step progress bar for running steps */}
                {step.status === 'running' && step.progress !== undefined && (
                  <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${step.progress}%` }}
                    />
                  </div>
                )}
              </div>
              
              {step.status === 'running' && (
                <div className="flex-shrink-0">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Current Step Indicator */}
        {currentStep && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
            <p className="text-sm text-blue-800">
              <span className="font-medium">Current:</span> {currentStep}
            </p>
          </div>
        )}

        {/* Cancel Button */}
        {canCancel && onCancel && (
          <div className="flex justify-end">
            <button
              onClick={onCancel}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition duration-200 text-sm"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressModal; 