'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { dashboard, providers as providersApi, billFetcher } from '@/lib/api';
import Layout from '@/components/Layout';
import { useToast } from '@/hooks/useToast';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { handleApiError, shouldRedirectToLogin } from '@/lib/errorHandler';
import { jwtDecode } from 'jwt-decode';
import { getHouses, type House } from '@/lib/housesData';

interface Provider {
  _id?: string | { $oid: string };
  id?: string;
  name: string;
  type: string;
  latest_bill?: { date: string; amount: string; description?: string };
  login_url?: string;
  user_id?: string;
  house_id?: string;
}

interface DecodedToken {
  sub: string;
  exp: number;
}

interface DeleteConfirmation {
  isOpen: boolean;
  providerId: string | null;
  providerName: string;
}

export default function ProvidersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [deleteConfirmation, setDeleteConfirmation] = useState<DeleteConfirmation>({
    isOpen: false,
    providerId: null,
    providerName: ''
  });
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [houses, setHouses] = useState<House[]>([]);
  const [selectedHouseId, setSelectedHouseId] = useState<string | null>(null);
  const [fetchingProviderId, setFetchingProviderId] = useState<string | null>(null);
  const [fetchProgress, setFetchProgress] = useState<number>(0);
  const [fetchedBill, setFetchedBill] = useState<any>(null);
  const [fetchErrors, setFetchErrors] = useState<Record<string, string>>({});
  const [lastFetchedProviderId, setLastFetchedProviderId] = useState<string | null>(null);

  // Enhanced user ID validation and token management
  const getUserId = (): string | null => {
    const urlUserId = searchParams.get('user_id');
    if (urlUserId && urlUserId !== 'null' && urlUserId !== 'undefined') {
      return urlUserId;
    }
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        const decodedToken: DecodedToken = jwtDecode(token);
        if (decodedToken.exp * 1000 < Date.now()) {
          localStorage.removeItem('auth_token');
          return null;
        }
        return decodedToken.sub;
      } catch (error) {
        localStorage.removeItem('auth_token');
        return null;
      }
    }
    return null;
  };
  const validUserId = getUserId();

  const redirectToLogin = () => {
    localStorage.removeItem('auth_token');
    router.push('/login');
  };

  // Fetch providers for the user
  const fetchDashboard = async () => {
    if (!validUserId) {
      toast.warning(
        'Authentication Required',
        'Please log in to view your providers.',
        {
          action: {
            label: 'Go to Login',
            onClick: redirectToLogin
          }
        }
      );
      return;
    }
    try {
      const dashboardData = await dashboard.get(validUserId);
      let savedProviders: Provider[] = [];
      try {
        const savedProvidersData = localStorage.getItem('providers_data');
        if (savedProvidersData) {
          savedProviders = JSON.parse(savedProvidersData);
        }
      } catch (error) {
        // ignore
      }
      const mergedProviders = dashboardData.providers.map((p: Provider) => {
        const provider = {
          ...p,
          id: typeof p._id === 'object' && p._id !== null && '$oid' in p._id
            ? p._id.$oid
            : (p._id || p.id || '') as string
        };
        const savedProvider = savedProviders.find(sp => sp.id === provider.id);
        return savedProvider?.latest_bill 
          ? { ...provider, latest_bill: savedProvider.latest_bill }
          : provider;
      });
      setProviders(mergedProviders);
    } catch (err: any) {
      if (shouldRedirectToLogin(err)) {
        const errorResult = handleApiError(err, undefined, redirectToLogin);
        toast.warning(errorResult.title, errorResult.message, {
          action: errorResult.action
        });
      } else {
        const errorResult = handleApiError(err, () => fetchDashboard());
        toast.error(errorResult.title, errorResult.message, {
          action: errorResult.action
        });
      }
    }
  };

  const handleDeleteProvider = async (providerId: string, providerName: string) => {
    setDeleteConfirmation({
      isOpen: true,
      providerId,
      providerName
    });
  };

  const confirmDeleteProvider = async () => {
    if (!deleteConfirmation.providerId) return;
    setDeleteLoading(true);
    try {
      await providersApi.delete(deleteConfirmation.providerId);
      setProviders((prev) => prev.filter((p) => p.id !== deleteConfirmation.providerId));
      toast.success(
        'Provider Deleted',
        `${deleteConfirmation.providerName} has been successfully removed.`
      );
      await fetchDashboard();
      setDeleteConfirmation({ isOpen: false, providerId: null, providerName: '' });
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast.error(
          'Provider Not Found',
          'This provider may have already been deleted.',
          {
            action: {
              label: 'Refresh',
              onClick: () => window.location.reload()
            }
          }
        );
      } else if (err.response?.status === 401) {
        toast.warning(
          'Authentication Required',
          'Please log in again to delete providers.',
          {
            action: {
              label: 'Go to Login',
              onClick: redirectToLogin
            }
          }
        );
      } else {
        const errorResult = handleApiError(err, confirmDeleteProvider);
        toast.error(errorResult.title, errorResult.message, {
          action: errorResult.action
        });
      }
    } finally {
      setDeleteLoading(false);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirmation({ isOpen: false, providerId: null, providerName: '' });
  };

  useEffect(() => {
    fetchDashboard();
    setHouses(getHouses());
  }, [searchParams]);

  useEffect(() => {
    if (houses.length > 0 && !selectedHouseId) {
      setSelectedHouseId(houses[0].id);
    }
  }, [houses, selectedHouseId]);

  const filteredProviders = selectedHouseId
    ? providers.filter((p) => p.house_id === selectedHouseId)
    : providers;

  // Unified handler to fetch bills for a provider (used by card)
  const handleFetch = async (provider: Provider) => {
    if (!provider.id) {
      toast.error('Error', 'Provider ID is missing');
      return;
    }
    toast.info('Starting Automation', `Extracting bills for ${provider.name}...`);
    try {
      const { job_id } = await billFetcher.start(provider.id);
      toast.success('Bill Extraction Started', `Bill extraction job (${job_id}) started for ${provider.name}`);
    } catch (error: any) {
      console.error('Fetch bill error:', error);
      if (error.response?.status === 401 || error.response?.status === 403) {
        toast.error('Authentication Required', 'Please log in to fetch bills');
        redirectToLogin();
      } else {
        toast.error('Extraction Failed', error.message || 'Failed to extract bill');
      }
    }
  };

  return (
    <Layout>
      <div className="mb-16 mt-8 px-4 md:px-12 lg:px-24 xl:px-32">
        <div className="rounded-3xl bg-gray-900/70 border border-gray-700/60 shadow-xl p-8 md:p-12">
          <h2 className="text-4xl font-bold text-white mb-10">Your Connected Providers</h2>
          <div className="mb-10 flex flex-col md:flex-row md:items-center md:space-x-6">
            <label className="text-lg font-semibold text-white mb-2 md:mb-0">Select Property:</label>
            <select
              value={selectedHouseId || ''}
              onChange={e => setSelectedHouseId(e.target.value)}
              className="bg-gray-800 border border-gray-600 text-white rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent text-lg"
            >
              {houses.map(house => (
                <option key={house.id} value={house.id}>{house.name} - {house.address}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProviders.map((provider) => {
              const getProviderIcon = (type: string) => {
                switch (type.toLowerCase()) {
                  case 'water': return '💧';
                  case 'electric': case 'electricity': return '⚡';
                  case 'gas': return '🔥';
                  case 'internet': return '🌐';
                  default: return '🏢';
                }
              };
              const getProviderGradient = (type: string) => {
                switch (type.toLowerCase()) {
                  case 'water': return 'from-blue-600 to-blue-400';
                  case 'electric': case 'electricity': return 'from-yellow-600 to-yellow-400';
                  case 'gas': return 'from-orange-600 to-orange-400';
                  case 'internet': return 'from-purple-600 to-purple-400';
                  default: return 'from-gray-600 to-gray-400';
                }
              };
              return (
                <div key={provider.id} className="relative bg-gray-900 border border-gray-700 rounded-2xl p-6 hover:border-pink-500 transition-all duration-300 group">
                  <div className="flex items-center space-x-4 mb-4">
                    <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${getProviderGradient(provider.type)} flex items-center justify-center text-2xl shadow-lg`}>
                      {getProviderIcon(provider.type)}
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-white group-hover:text-pink-100 transition-colors">
                        {provider.name}
                      </h3>
                      <p className="text-gray-400 capitalize text-sm font-medium">
                        {provider.type} Provider
                      </p>
                    </div>
                  </div>
                  {provider.latest_bill && (
                    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                      <h4 className="text-sm font-bold text-pink-400 mb-2 flex items-center space-x-2">
                        <span>📄</span>
                        <span>Latest Bill</span>
                      </h4>
                      <div className="text-sm text-gray-300">
                        <div className="flex justify-between">
                          <span>Amount:</span>
                          <span className="text-pink-200 font-mono">{provider.latest_bill.amount}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Date:</span>
                          <span className="text-pink-200 font-mono">{provider.latest_bill.date}</span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="mt-4 flex flex-col space-y-2">
                    <button
                      onClick={() => handleFetch(provider)}
                      className="group/btn w-full bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white px-6 py-4 rounded-2xl transition-all duration-300 font-bold text-base shadow-lg hover:shadow-pink-500/30 hover:scale-105 relative overflow-hidden mb-2"
                    >
                      <span className="relative z-10 flex items-center justify-center space-x-2">
                        <span className="text-xl group-hover/btn:scale-110 transition-transform">🔍</span>
                        <span>View Bills</span>
                      </span>
                    </button>
                  </div>
                  <button
                    onClick={() => handleDeleteProvider(provider.id!, provider.name)}
                    className="absolute top-4 right-4 bg-red-600 hover:bg-red-500 text-white rounded-full p-2 transition-all duration-200 hover:scale-110 hover:shadow-lg"
                    title="Delete Provider"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {deleteConfirmation.isOpen && (
        <ConfirmModal
          isOpen={deleteConfirmation.isOpen}
          title={`Delete ${deleteConfirmation.providerName}?`}
          message="This will remove the provider and all associated bills."
          loading={deleteLoading}
          onConfirm={confirmDeleteProvider}
          onCancel={cancelDelete}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      )}
    </Layout>
  );
} 