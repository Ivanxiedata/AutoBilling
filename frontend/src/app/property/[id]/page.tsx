'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { dashboard, providers as providersApi } from '@/lib/api';
import Layout from '@/components/Layout';
import Link from 'next/link';
import { useToast } from '@/hooks/useToast';
import { ToastContainer } from '@/components/ui/Toast';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { handleApiError, shouldRedirectToLogin } from '@/lib/errorHandler';
import { jwtDecode } from 'jwt-decode';
import { getHouses, getTenantsByHouseId } from '@/lib/housesData';

interface Bill {
  date: string;
  amount: string;
  description?: string;
}

interface Provider {
  _id?: string | { $oid: string };
  id?: string;
  name: string;
  type: string;
  latest_bill?: Bill;
  login_url?: string;
  user_id?: string;
}

interface House {
  id: string;
  name: string;
  address: string;
  type: string;
  bedrooms: number;
  bathrooms: number;
  sqft?: number;
  monthly_rent: number;
  status: 'occupied' | 'vacant' | 'maintenance';
  tenant_count: number;
  monthly_bills: number;
  created_at: string;
}

interface Tenant {
  id: string;
  name: string;
  email: string;
  payment_amount: number;
  house_id: string;
  created_at: string;
}

interface DeleteConfirmation {
  isOpen: boolean;
  providerId: string | null;
  providerName: string;
}

interface DecodedToken {
  sub: string;
  exp: number;
}

interface AutomationResult {
  taskId: string;
  providerId: string;
  providerName: string;
  providerType: string;
  status: string;
  analysisResult: string;
  extractedTransactions: any[];
  completedAt: string;
}

export default function PropertyDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  
  const propertyId = params.id as string;
  const [property, setProperty] = useState<House | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'utilities' | 'bills' | 'tenants'>('overview');
  const [deleteConfirmation, setDeleteConfirmation] = useState<DeleteConfirmation>({
    isOpen: false,
    providerId: null,
    providerName: ''
  });
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [automationResults, setAutomationResults] = useState<AutomationResult[]>([]);
  
  // Fetch states
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
        console.error('Error decoding token:', error);
        localStorage.removeItem('auth_token');
        return null;
      }
    }
    return null;
  };

  const userId = getUserId();

  const redirectToLogin = () => {
    localStorage.removeItem('auth_token');
    router.push('/login');
  };

  useEffect(() => {
    const initializePage = async () => {
      if (!userId) {
        toast.warning('Authentication Required', 'Please log in to view property details.');
        setLoading(false);
        return;
      }

      // Load property data
      const houses = getHouses();
      const foundProperty = houses.find(h => h.id === propertyId);
      
      if (!foundProperty) {
        toast.error('Property Not Found', 'The requested property could not be found.');
        router.push(`/houses?user_id=${userId}`);
        return;
      }

      setProperty(foundProperty);
      
      // Load tenants for this property
      const propertyTenants = getTenantsByHouseId(propertyId);
      setTenants(propertyTenants);
      
      // Load providers and automation results
      await fetchProviders();
      loadAutomationResults();
      
      setLoading(false);
    };

    initializePage();
  }, [propertyId, userId]);

  const fetchProviders = async () => {
    if (!userId) return;

    try {
      const dashboardData = await dashboard.get(userId);
      
      // Filter providers for this property if they have house_id
      const propertyProviders = dashboardData.providers.filter((p: any) => 
        !p.house_id || p.house_id === propertyId
      );
      
      // Load saved providers data from localStorage
      let savedProviders: Provider[] = [];
      try {
        const savedProvidersData = localStorage.getItem('providers_data');
        if (savedProvidersData) {
          savedProviders = JSON.parse(savedProvidersData);
        }
      } catch (error) {
        console.error('Error loading saved providers:', error);
      }
      
      // Merge with saved data
      const mergedProviders = propertyProviders.map((p: Provider) => {
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
      console.error('Providers fetch error:', err);
      if (shouldRedirectToLogin(err)) {
        const errorResult = handleApiError(err, undefined, redirectToLogin);
        toast.warning(errorResult.title, errorResult.message, {
          action: errorResult.action
        });
      }
    }
  };

  const loadAutomationResults = () => {
    const savedResults = localStorage.getItem('automationResults');
    if (savedResults) {
      try {
        const results: AutomationResult[] = JSON.parse(savedResults);
        // Filter results for providers related to this property
        const propertyResults = results.filter(result => 
          providers.some(p => p.id === result.providerId)
        );
        setAutomationResults(propertyResults);
      } catch (error) {
        console.error('Error loading automation results:', error);
      }
    }
  };

  const handleFetch = async (provider: Provider, forceRefresh: boolean = false) => {
    if (!provider.id) {
      toast.error('Error', 'Provider ID is missing');
      return;
    }

    setFetchingProviderId(provider.id);
    setFetchProgress(0);
    setFetchErrors(prev => ({ ...prev, [provider.id!]: '' }));
    toast.info('Starting Automation', `Extracting bills for ${provider.name}...`);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('Authentication Required', 'Please log in to fetch bills');
        redirectToLogin();
        return;
      }

      const res = await fetch(`/providers/${provider.id}/fetch-bill${forceRefresh ? '?force=true' : ''}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          toast.error('Authentication Required', 'Please log in to fetch bills');
          redirectToLogin();
          return;
        }
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const { job_id } = await res.json();

      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 2000));
        const statusRes = await fetch(`/providers/fetch-bill-status/${job_id}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!statusRes.ok) {
          throw new Error(`Status check failed: ${statusRes.status}`);
        }

        const statusData = await statusRes.json();
        setFetchProgress(statusData.progress || 0);

        if (statusData.status === 'done') {
          const billData = statusData.bill;
          setFetchedBill(billData);
          setLastFetchedProviderId(provider.id);
          
          // Create automation result and save to localStorage
          const automationResult = {
            taskId: `bill_${provider.id}_${Date.now()}`,
            providerId: provider.id,
            providerName: provider.name,
            providerType: provider.type,
            status: 'completed',
            analysisResult: billData.analysis || `Bill extracted for ${provider.name}. Amount: ${billData.current_bill_amount || billData.amount}`,
            extractedTransactions: billData.transactions || [],
            completedAt: new Date().toISOString()
          };

          const updatedResults = [...automationResults.filter(r => r.providerId !== provider.id), automationResult];
          setAutomationResults(updatedResults);
          localStorage.setItem('automationResults', JSON.stringify(updatedResults));
          
          // Update provider with latest bill data
          const updatedProviders = providers.map(p => 
            p.id === provider.id 
              ? { 
                  ...p, 
                  latest_bill: {
                    date: billData.due_date || billData.date || new Date().toISOString().split('T')[0],
                    amount: billData.current_bill_amount || billData.amount || '$0.00',
                    description: billData.description || 'Latest bill'
                  }
                }
              : p
          );
          setProviders(updatedProviders);
          localStorage.setItem('providers_data', JSON.stringify(updatedProviders));
          
          toast.success('Bill Extracted', `Successfully extracted bill for ${provider.name}`);
          done = true;
        } else if (statusData.status === 'error') {
          setFetchErrors(prev => ({ ...prev, [provider.id!]: statusData.error || 'Unknown error' }));
          toast.error('Extraction Failed', statusData.error || 'Failed to extract bill');
          done = true;
        }
      }
    } catch (error: any) {
      console.error('Fetch bill error:', error);
      setFetchErrors(prev => ({ ...prev, [provider.id!]: error.message || 'Failed to fetch bill' }));
      toast.error('Extraction Failed', error.message || 'Failed to extract bill');
    } finally {
      setFetchingProviderId(null);
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
      setProviders(prev => prev.filter(p => p.id !== deleteConfirmation.providerId));
      setFetchErrors(prev => {
        const copy = { ...prev };
        delete copy[deleteConfirmation.providerId!];
        return copy;
      });
      
      toast.success('Provider Deleted', `${deleteConfirmation.providerName} has been successfully removed.`);
      setDeleteConfirmation({ isOpen: false, providerId: null, providerName: '' });
    } catch (err: any) {
      console.error('Delete provider error:', err);
      const errorResult = handleApiError(err, confirmDeleteProvider);
      toast.error(errorResult.title, errorResult.message, {
        action: errorResult.action
      });
    } finally {
      setDeleteLoading(false);
    }
  };

  const getPropertyTypeIcon = (type: string) => {
    switch (type) {
      case 'single_family': return '🏠';
      case 'duplex': return '🏘️';
      case 'apartment': return '🏢';
      case 'condo': return '🏗️';
      case 'townhouse': return '🏘️';
      default: return '🏠';
    }
  };

  const getProviderIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'water': return '💧';
      case 'electric':
      case 'electricity': return '⚡';
      case 'gas': return '🔥';
      case 'internet': return '🌐';
      default: return '🏢';
    }
  };

  const getProviderGradient = (type: string) => {
    switch (type.toLowerCase()) {
      case 'water': return 'from-blue-500/20 to-cyan-500/20';
      case 'electric':
      case 'electricity': return 'from-yellow-500/20 to-orange-500/20';
      case 'gas': return 'from-red-500/20 to-pink-500/20';
      case 'internet': return 'from-purple-500/20 to-indigo-500/20';
      default: return 'from-gray-500/20 to-gray-600/20';
    }
  };

  const totalMonthlyBills = providers.reduce((sum, provider) => {
    if (provider.latest_bill?.amount) {
      const amount = parseFloat(provider.latest_bill.amount.replace(/[$,]/g, ''));
      return sum + (isNaN(amount) ? 0 : amount);
    }
    return sum;
  }, 0);

  const totalTenantPayments = tenants.reduce((sum, tenant) => sum + tenant.payment_amount, 0);

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500 mx-auto"></div>
            <p className="mt-4 text-white">Loading property details...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (!property) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="text-red-400 text-lg">Property not found</div>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link
                href={`/houses?user_id=${userId}`}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>
              <div className="text-4xl">{getPropertyTypeIcon(property.type)}</div>
              <div>
                <h1 className="text-4xl font-bold text-white">{property.name}</h1>
                <p className="text-gray-300">{property.address}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className={`px-4 py-2 rounded-full text-sm font-medium ${
                property.status === 'occupied' ? 'bg-green-900 text-green-400' : 
                property.status === 'vacant' ? 'bg-orange-900 text-orange-400' : 
                'bg-red-900 text-red-400'
              }`}>
                {property.status.charAt(0).toUpperCase() + property.status.slice(1)}
              </span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mb-8">
          <nav className="flex space-x-8">
            {[
              { id: 'overview', label: 'Overview', icon: '📊' },
              { id: 'utilities', label: 'Utilities', icon: '⚡' },
              { id: 'bills', label: 'Bills', icon: '💰' },
              { id: 'tenants', label: 'Tenants', icon: '👥' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-pink-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Property Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Property Details</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Bedrooms</span>
                    <span className="text-white">{property.bedrooms}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Bathrooms</span>
                    <span className="text-white">{property.bathrooms}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Square Feet</span>
                    <span className="text-white">{property.sqft?.toLocaleString() || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Monthly Rent</span>
                    <span className="text-white">${property.monthly_rent.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Financial Overview</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Monthly Bills</span>
                    <span className="text-red-400">${totalMonthlyBills.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Tenant Payments</span>
                    <span className="text-green-400">${totalTenantPayments.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-t border-gray-700 pt-3">
                    <span className="text-gray-400">Net Income</span>
                    <span className={`font-semibold ${
                      (property.monthly_rent - totalMonthlyBills) > 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      ${(property.monthly_rent - totalMonthlyBills).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Occupancy</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Current Tenants</span>
                    <span className="text-white">{property.tenant_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Max Capacity</span>
                    <span className="text-white">{property.bedrooms}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Occupancy Rate</span>
                    <span className="text-white">
                      {((property.tenant_count / property.bedrooms) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <button
                  onClick={() => setActiveTab('utilities')}
                  className="bg-gradient-to-r from-blue-600 to-blue-500 text-white p-4 rounded-xl hover:from-blue-500 hover:to-blue-400 transition-all duration-200"
                >
                  <div className="text-2xl mb-2">⚡</div>
                  <div className="font-medium">Manage Utilities</div>
                </button>
                <button
                  onClick={() => setActiveTab('bills')}
                  className="bg-gradient-to-r from-green-600 to-green-500 text-white p-4 rounded-xl hover:from-green-500 hover:to-green-400 transition-all duration-200"
                >
                  <div className="text-2xl mb-2">💰</div>
                  <div className="font-medium">View Bills</div>
                </button>
                <button
                  onClick={() => setActiveTab('tenants')}
                  className="bg-gradient-to-r from-purple-600 to-purple-500 text-white p-4 rounded-xl hover:from-purple-500 hover:to-purple-400 transition-all duration-200"
                >
                  <div className="text-2xl mb-2">👥</div>
                  <div className="font-medium">Manage Tenants</div>
                </button>
                <button
                  onClick={() => router.push(`/providers/add?user_id=${userId}&house_id=${property.id}`)}
                  className="bg-gradient-to-r from-pink-600 to-pink-500 text-white p-4 rounded-xl hover:from-pink-500 hover:to-pink-400 transition-all duration-200"
                >
                  <div className="text-2xl mb-2">➕</div>
                  <div className="font-medium">Add Provider</div>
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'utilities' && (
          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white">Utility Providers</h2>
              <button
                onClick={() => router.push(`/providers/add?user_id=${userId}&house_id=${property.id}`)}
                className="bg-pink-600 hover:bg-pink-500 text-white px-4 py-2 rounded-lg transition duration-200 font-medium flex items-center space-x-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                <span>Add Provider</span>
              </button>
            </div>

            {providers.length === 0 ? (
              <div className="text-center py-16">
                <div className="bg-gray-900 border border-gray-700 rounded-3xl p-12">
                  <div className="text-6xl mb-6">⚡</div>
                  <h3 className="text-2xl font-bold text-white mb-4">No utility providers yet</h3>
                  <p className="text-gray-300 mb-8">Add your first utility provider to get started</p>
                  <button
                    onClick={() => router.push(`/providers/add?user_id=${userId}&house_id=${property.id}`)}
                    className="bg-pink-600 hover:bg-pink-500 text-white px-8 py-4 rounded-xl transition duration-200 font-bold"
                  >
                    Add First Provider
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {providers.map((provider) => (
                  <div
                    key={provider.id}
                    className={`relative bg-gradient-to-br ${getProviderGradient(provider.type)} backdrop-blur-xl border border-gray-600/50 hover:border-pink-500/50 rounded-2xl p-6 transition-all duration-300 hover:scale-105 shadow-xl`}
                  >
                    <div className="flex flex-col items-center mb-4">
                      <div className="text-5xl bg-gray-800/60 rounded-2xl p-4 mb-3">{getProviderIcon(provider.type)}</div>
                      <h3 className="font-bold text-white text-xl mb-1 text-center">{provider.name}</h3>
                      <p className="text-gray-400 text-sm font-medium capitalize">{provider.type}</p>
                    </div>

                    <div className="space-y-3">
                      <button
                        onClick={() => handleFetch(provider, false)}
                        disabled={fetchingProviderId === provider.id}
                        className="w-full bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white px-4 py-3 rounded-xl transition-all duration-300 font-bold text-sm shadow-lg hover:shadow-pink-500/30 hover:scale-105 disabled:opacity-50"
                      >
                        {fetchingProviderId === provider.id ? 'Fetching...' : '🔍 Extract Bills'}
                      </button>

                      {fetchingProviderId === provider.id && (
                        <div className="w-full">
                          <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                            <div className="bg-pink-500 h-2 rounded-full transition-all duration-300" style={{ width: `${fetchProgress}%` }} />
                          </div>
                          <span className="text-pink-300 text-xs font-semibold">{fetchProgress}%</span>
                        </div>
                      )}

                      {provider.latest_bill && (
                        <div className="bg-gray-800/60 rounded-xl p-3 border border-gray-700/50">
                          <h4 className="text-xs font-bold text-pink-400 mb-2">📄 Latest Bill</h4>
                          <div className="text-xs text-gray-300">
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

                      {fetchErrors[provider.id!] && (
                        <div className="text-red-400 text-xs text-center">{fetchErrors[provider.id!]}</div>
                      )}
                    </div>

                    <button
                      onClick={() => handleDeleteProvider(provider.id!, provider.name)}
                      className="absolute top-3 right-3 bg-red-600 hover:bg-red-500 text-white rounded-full p-2 transition-all duration-200 hover:scale-110 hover:shadow-lg"
                      title="Delete Provider"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'bills' && (
          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white">Bills Summary</h2>
              <Link
                href={`/bills?user_id=${userId}&house_id=${property.id}`}
                className="bg-pink-600 hover:bg-pink-500 text-white px-4 py-2 rounded-lg transition duration-200 font-medium"
              >
                View Full Bills Page
              </Link>
            </div>

            {providers.filter(p => p.latest_bill).length === 0 ? (
              <div className="text-center py-16">
                <div className="bg-gray-900 border border-gray-700 rounded-3xl p-12">
                  <div className="text-6xl mb-6">💰</div>
                  <h3 className="text-2xl font-bold text-white mb-4">No bills found</h3>
                  <p className="text-gray-300 mb-8">Extract bills from your utility providers to see them here</p>
                  <button
                    onClick={() => setActiveTab('utilities')}
                    className="bg-pink-600 hover:bg-pink-500 text-white px-8 py-4 rounded-xl transition duration-200 font-bold"
                  >
                    Go to Utilities
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-gray-900 border border-gray-700 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-gray-800 border-b border-gray-700">
                        <th className="text-left py-4 px-6 text-gray-300 font-semibold">Provider</th>
                        <th className="text-left py-4 px-6 text-gray-300 font-semibold">Type</th>
                        <th className="text-left py-4 px-6 text-gray-300 font-semibold">Amount</th>
                        <th className="text-left py-4 px-6 text-gray-300 font-semibold">Date</th>
                        <th className="text-left py-4 px-6 text-gray-300 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {providers.filter(p => p.latest_bill).map((provider) => (
                        <tr key={provider.id} className="border-b border-gray-700/50 hover:bg-gray-800/50">
                          <td className="py-4 px-6">
                            <div className="flex items-center space-x-3">
                              <div className="text-2xl">{getProviderIcon(provider.type)}</div>
                              <div className="text-white font-medium">{provider.name}</div>
                            </div>
                          </td>
                          <td className="py-4 px-6 text-gray-300 capitalize">{provider.type}</td>
                          <td className="py-4 px-6 text-pink-400 font-mono font-semibold">{provider.latest_bill?.amount}</td>
                          <td className="py-4 px-6 text-gray-300">{provider.latest_bill?.date}</td>
                          <td className="py-4 px-6">
                            <span className="px-2 py-1 bg-orange-900 text-orange-400 rounded-full text-xs font-medium">
                              Unpaid
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'tenants' && (
          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white">Tenants</h2>
              <Link
                href={`/tenants?user_id=${userId}&house_id=${property.id}`}
                className="bg-pink-600 hover:bg-pink-500 text-white px-4 py-2 rounded-lg transition duration-200 font-medium"
              >
                Manage Tenants
              </Link>
            </div>

            {tenants.length === 0 ? (
              <div className="text-center py-16">
                <div className="bg-gray-900 border border-gray-700 rounded-3xl p-12">
                  <div className="text-6xl mb-6">👥</div>
                  <h3 className="text-2xl font-bold text-white mb-4">No tenants yet</h3>
                  <p className="text-gray-300 mb-8">Add tenants to track payments and occupancy</p>
                  <Link
                    href={`/tenants?user_id=${userId}&house_id=${property.id}`}
                    className="bg-pink-600 hover:bg-pink-500 text-white px-8 py-4 rounded-xl transition duration-200 font-bold inline-block"
                  >
                    Add First Tenant
                  </Link>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {tenants.map((tenant) => (
                  <div key={tenant.id} className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
                    <div className="flex items-center space-x-4 mb-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold text-lg">
                        {tenant.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1">
                        <h3 className="text-white font-semibold">{tenant.name}</h3>
                        <p className="text-gray-400 text-sm">{tenant.email}</p>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Payment Amount</span>
                        <span className="text-green-400 font-semibold">${tenant.payment_amount.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Added</span>
                        <span className="text-gray-300 text-sm">{new Date(tenant.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Delete Confirmation Modal */}
        <ConfirmModal
          isOpen={deleteConfirmation.isOpen}
          title={`Delete ${deleteConfirmation.providerName}?`}
          message="This will remove the provider and all associated bills."
          loading={deleteLoading}
          onConfirm={confirmDeleteProvider}
          onCancel={() => setDeleteConfirmation({ isOpen: false, providerId: null, providerName: '' })}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />

        <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
      </div>
    </Layout>
  );
} 