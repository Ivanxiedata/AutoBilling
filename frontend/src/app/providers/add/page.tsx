'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { providers } from '@/lib/api';
import Layout from '@/components/Layout';
import Link from 'next/link';

export default function AddProviderPage() {
  const [step, setStep] = useState(1);
  const [url, setUrl] = useState('');
  const [providerName, setProviderName] = useState('');
  const [providerType, setProviderType] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const searchParams = useSearchParams();
  const router = useRouter();
  const userId = searchParams.get('user_id');
  const preSelectedType = searchParams.get('type'); // Get the pre-selected type
  const houseId = searchParams.get('house_id');

  // Initialize provider type from URL parameter
  useEffect(() => {
    if (preSelectedType) {
      setProviderType(preSelectedType);
    }
  }, [preSelectedType]);

  const getUtilityInfo = (type: string) => {
    switch (type) {
      case 'water':
        return {
          icon: '💧',
          color: 'blue',
          name: 'Water Utility',
          examples: 'City Water, Municipal Water, Water District'
        };
      case 'electric':
        return {
          icon: '⚡',
          color: 'yellow',
          name: 'Electric Utility',
          examples: 'Electric Company, Power Company, Energy Provider'
        };
      case 'gas':
        return {
          icon: '🔥',
          color: 'orange',
          name: 'Gas Utility',
          examples: 'Natural Gas Company, Gas Provider'
        };
      case 'internet':
        return {
          icon: '🌐',
          color: 'purple',
          name: 'Internet Service',
          examples: 'Internet Provider, Cable Company, ISP'
        };
      default:
        return {
          icon: '🏢',
          color: 'gray',
          name: 'Utility Provider',
          examples: 'Any Utility Service'
        };
    }
  };

  const utilityInfo = getUtilityInfo(preSelectedType || '');

  const handleContinue = () => {
    if (!url) {
      setError('Please enter a URL');
      return;
    }

    setError('');
    setStep(2); // Move directly to credentials step
  };

  const handleCreateProvider = async () => {
    if (!providerName || !providerType || !username || !password) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const providerData = {
        name: providerName,
        type: providerType,
        login_url: url,
        username,
        password,
        selectors: [], // Empty selectors since automation will handle detection
        house_id: houseId, // Associate provider with selected property
      };

      await providers.create({ ...providerData, user_id: userId });
      setSuccess('Provider created successfully!');
      setTimeout(() => {
        router.push(`/bills?user_id=${userId}`);
      }, 2000);
    } catch (err: any) {
      console.error('Create provider error:', err);
      
      let errorMessage = 'Failed to create provider.';
      const errorDetail = err.response?.data?.detail;
      const status = err.response?.status;

      if (status === 409) {
        // Duplicate provider error
        errorMessage = errorDetail || 'This provider already exists in your account.';
      } else if (status === 400) {
        // Validation error
      if (typeof errorDetail === 'string') {
        errorMessage = errorDetail;
      } else if (Array.isArray(errorDetail)) {
        // Handle FastAPI validation errors
        errorMessage = errorDetail.map(e => `${e.loc.join('.')} - ${e.msg}`).join('; ');
        }
      } else if (status === 500) {
        errorMessage = 'Server error occurred. Please try again later.';
      } else if (!err.response) {
        errorMessage = 'Network error. Please check your connection and try again.';
      } else {
        errorMessage = errorDetail || errorMessage;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <Link
            href={`/bills?user_id=${userId}`}
            className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
          >
            ← Back to Bills
          </Link>
          {preSelectedType ? (
            <div className="text-center">
              <div className="text-6xl mb-4">{utilityInfo.icon}</div>
              <h1 className="text-3xl font-bold text-gray-900">Add {utilityInfo.name}</h1>
              <p className="text-gray-600">Connect your {utilityInfo.name.toLowerCase()} account for automated bill tracking</p>
              <p className="text-sm text-gray-500 mt-2">Examples: {utilityInfo.examples}</p>
            </div>
          ) : (
            <div>
          <h1 className="text-3xl font-bold text-gray-900">Add Provider</h1>
          <p className="text-gray-600">Add a new utility provider</p>
            </div>
          )}
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
            }`}>
              1
            </div>
            <div className={`flex-1 h-1 mx-4 ${
              step >= 2 ? 'bg-blue-600' : 'bg-gray-200'
            }`}></div>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
            }`}>
              2
            </div>
          </div>
          <div className="flex justify-between mt-2 text-sm text-gray-600">
            <span>Enter URL</span>
            <span>Add Credentials</span>
          </div>
        </div>

        {error && (
          <div className={`border px-4 py-3 rounded mb-6 ${
            error.includes('already have') || error.includes('already exists') 
              ? 'bg-yellow-50 border-yellow-200 text-yellow-800' 
              : 'bg-red-50 border-red-200 text-red-700'
          }`}>
            <div className="flex items-start">
              <span className="mr-2">
                {error.includes('already have') || error.includes('already exists') ? '⚠️' : '❌'}
              </span>
              <span>{error}</span>
            </div>
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-6">
            {success}
          </div>
        )}

        {/* Step 1: URL Input */}
        {step === 1 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Step 1: Enter Provider URL</h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                  Login Page URL
                </label>
                <input
                  type="url"
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/login"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-500 text-black"
                  required
                />
                <p className="text-sm text-gray-500 mt-1">
                  Enter the URL of your utility provider's login page
                </p>
              </div>
              <button
                onClick={handleContinue}
                disabled={!url}
                className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-200 disabled:opacity-50"
              >
                Continue to Credentials
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Credentials */}
        {step === 2 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Step 2: Provider Details</h2>
            
            <div className="mb-6 p-4 bg-blue-50 rounded-lg">
              <h3 className="font-medium text-blue-900 mb-2">🚀 Ready to Connect!</h3>
              <p className="text-sm text-blue-700 mb-2">Enter your provider details below. The automation will automatically detect login fields when you run it.</p>
              <p className="text-xs text-blue-600">💡 We'll check for duplicates to avoid adding the same provider twice.</p>
            </div>

            <div className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                  Provider Name
                </label>
                <input
                  type="text"
                  id="name"
                  value={providerName}
                  onChange={(e) => setProviderName(e.target.value)}
                  placeholder={preSelectedType ? `e.g., City of Austin ${utilityInfo.name}` : "e.g., CoServ Electric"}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-black"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  Choose a unique name to identify this provider in your account
                </p>
              </div>

              <div>
                <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-2">
                  Provider Type
                </label>
                {preSelectedType ? (
                  <div className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-900 flex items-center">
                    <span className="text-xl mr-2">{utilityInfo.icon}</span>
                    <span className="capitalize">{preSelectedType}</span>
                    <input type="hidden" value={providerType} />
                  </div>
                ) : (
                <select
                  id="type"
                  value={providerType}
                  onChange={(e) => setProviderType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-black"
                  required
                >
                  <option value="">Select type</option>
                  <option value="electric">Electric</option>
                  <option value="water">Water</option>
                  <option value="gas">Gas</option>
                  <option value="internet">Internet</option>
                  <option value="other">Other</option>
                </select>
                )}
              </div>

              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
                  Username/Email for this Provider
                </label>
                <input
                  type="text"
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Your login username or email"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-black"
                  required
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                  Password for this Provider
                </label>
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your login password"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-black"
                  required
                />
              </div>

              <div className="flex space-x-4">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-md hover:bg-gray-300 transition duration-200"
                >
                  Back
                </button>
                <button
                  onClick={handleCreateProvider}
                  disabled={loading}
                  className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-200 disabled:opacity-50"
                >
                  {loading ? 'Creating...' : preSelectedType ? `Connect ${utilityInfo.name}` : 'Create Provider'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
} 