'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { dashboard, providers as providersApi, billFetcher } from '@/lib/api';
import Layout from '@/components/Layout';
import Link from 'next/link';
import { useToast } from '@/hooks/useToast';
import { ToastContainer } from '@/components/ui/Toast';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { handleApiError, shouldRedirectToLogin } from '@/lib/errorHandler';
import { jwtDecode } from 'jwt-decode';
import { getHouses, type House } from '@/lib/housesData';

interface BillData {
  date: string;
  description: string;
  amount: string;
  balance: string;
}

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

interface AutomationResult {
  taskId: string;
  providerId: string;
  providerName: string;
  providerType: string;
  status: string;
  analysisResult: string;
  extractedTransactions: BillData[];
  completedAt: string;
}

interface CategorySummary {
  type: string;
  icon: string;
  totalAmount: number;
  billCount: number;
  avgAmount: number;
  trend: 'up' | 'down' | 'stable';
  results: AutomationResult[];
  isExpanded: boolean;
}

interface DeleteConfirmation {
  isOpen: boolean;
  providerId: string | null;
  providerName: string;
}

interface DashboardData {
  providers: Provider[];
  recent_bills: Array<{ amount: string; date: string; provider_id: string }>;
  tenants: Array<{ name: string; email: string }>;
  stats: {
    total_spent: number;
    avg_per_bill: number;
    bill_count: number;
  };
}

const getCategoryIcon = (type: string) => {
  switch (type.toLowerCase()) {
    case 'water':
      return '💧';
    case 'electricity':
    case 'electric':
      return '⚡';
    case 'gas':
      return '🔥';
    case 'internet':
    case 'broadband':
      return '🌐';
    case 'trash':
    case 'waste':
      return '🗑️';
    case 'sewer':
      return '🏭';
    default:
      return '🏠';
  }
};

const getCategoryGradient = (type: string) => {
  switch (type.toLowerCase()) {
    case 'water':
      return 'from-blue-600 to-cyan-500';
    case 'electricity':
    case 'electric':
      return 'from-yellow-500 to-orange-500';
    case 'gas':
      return 'from-red-500 to-pink-500';
    case 'internet':
    case 'broadband':
      return 'from-purple-600 to-indigo-500';
    case 'trash':
    case 'waste':
      return 'from-green-600 to-emerald-500';
    case 'sewer':
      return 'from-gray-600 to-slate-500';
    default:
      return 'from-gray-600 to-gray-500';
  }
};

export default function BillsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const userId = searchParams.get('user_id');
  const [automationResults, setAutomationResults] = useState<AutomationResult[]>([]);
  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedResult, setSelectedResult] = useState<AutomationResult | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState<{
    show: boolean;
    type: 'result' | 'category' | 'all';
    target?: string;
    name?: string;
  }>({ show: false, type: 'result' });

  // Add provider-related state
  const [providers, setProviders] = useState<Provider[]>([]);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState<DeleteConfirmation>({
    isOpen: false,
    providerId: null,
    providerName: ''
  });
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Add state for progress and bill result
  const [fetchingProviderId, setFetchingProviderId] = useState<string | null>(null);
  const [fetchProgress, setFetchProgress] = useState<number>(0);
  const [fetchedBill, setFetchedBill] = useState<any>(null);
  const [fetchErrors, setFetchErrors] = useState<Record<string, string>>({});
  const [lastFetchedProviderId, setLastFetchedProviderId] = useState<string | null>(null);

  // New state for expanded category
  const [expandedCategoryType, setExpandedCategoryType] = useState<string | null>(null);

  // Add new state for houses
  const [houses, setHouses] = useState<House[]>([]);
  const [selectedHouseId, setSelectedHouseId] = useState<string | null>(null);

  // Centralized filtered providers by selected property
  const filteredProviders = selectedHouseId
    ? providers.filter((p) => p.house_id === selectedHouseId)
    : providers;

  // De-duplicate providers by name and type, preferring the one with the latest bill (with a valid amount)
  const dedupedProviders = Array.from(
    filteredProviders.reduce((map, provider) => {
      const key = `${provider.name.toLowerCase()}|${provider.type.toLowerCase()}`;
      const existing = map.get(key);
      // Prefer the provider with a latest_bill with a valid amount
      const hasValidBill = (p: any) => p && p.latest_bill && p.latest_bill.amount && p.latest_bill.amount !== 'N/A';
      if (!existing) {
        map.set(key, provider);
      } else if (hasValidBill(provider) && !hasValidBill(existing)) {
        map.set(key, provider);
      } else if (hasValidBill(provider) && hasValidBill(existing)) {
        // Prefer the one with the most recent date
        const dateA = new Date((provider.latest_bill && provider.latest_bill.date) || 0);
        const dateB = new Date((existing.latest_bill && existing.latest_bill.date) || 0);
        if (dateA > dateB) map.set(key, provider);
      }
      return map;
    }, new Map()).values()
  );

  // Enhanced user ID validation and token management
  const getUserId = (): string | null => {
    // First try URL params
    const urlUserId = searchParams.get('user_id');
    if (urlUserId && urlUserId !== 'null' && urlUserId !== 'undefined') {
      return urlUserId;
    }

    // Fallback to JWT token
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        const decodedToken: DecodedToken = jwtDecode(token);
        
        // Check if token is expired
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

  const validUserId = getUserId();

  const redirectToLogin = () => {
    localStorage.removeItem('auth_token');
    router.push('/login');
  };

  // Function to fetch dashboard data including providers
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
      // Merge fetched providers with saved data, preferring saved latest_bill data
      const mergedProviders = dashboardData.providers.map((p: Provider) => {
        const provider = {
          ...p,
          id: typeof p._id === 'object' && p._id !== null && '$oid' in p._id
            ? p._id.$oid
            : (p._id || p.id || '') as string
        };
        // Find saved provider data
        const savedProvider = savedProviders.find(sp => sp.id === provider.id);
        // Merge with saved latest_bill if available
        return savedProvider?.latest_bill 
          ? { ...provider, latest_bill: savedProvider.latest_bill }
          : provider;
      });
      setProviders(mergedProviders);
      setDashboardData(dashboardData);
    } catch (err: any) {
      console.error('Dashboard fetch error:', err);
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

  // Function to handle provider deletion
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
      
      // Remove from local state
      setProviders((prev) => prev.filter((p) => p.id !== deleteConfirmation.providerId));
      setFetchErrors(prev => {
        const copy = { ...prev };
        delete copy[deleteConfirmation.providerId!];
        return copy;
      });
      
      toast.success(
        'Provider Deleted',
        `${deleteConfirmation.providerName} has been successfully removed.`
      );
      
      // Pull fresh providers list from backend to keep state in sync
      await fetchDashboard();
      
      setDeleteConfirmation({ isOpen: false, providerId: null, providerName: '' });
    } catch (err: any) {
      console.error('Delete provider error:', err);
      
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

  // Function to check bill status
  const checkBillStatus = () => {
    if (!providers || !automationResults) {
      return { availableBills: [], missingBills: [], totalProviders: 0 };
    }

    const allProviders = providers;
    const availableBills: Provider[] = [];
    const missingBills: Provider[] = [];

    allProviders.forEach(provider => {
      // Check if this provider has automation results
      const hasResults = automationResults.some(result => 
        result.providerName.toLowerCase().includes(provider.name.toLowerCase()) ||
        provider.name.toLowerCase().includes(result.providerName.toLowerCase()) ||
        (result.providerType.toLowerCase() === provider.type.toLowerCase())
      );

      if (hasResults) {
        availableBills.push(provider);
      } else {
        missingBills.push(provider);
      }
    });

    return {
      availableBills,
      missingBills,
      totalProviders: allProviders.length
    };
  };

  

  // ------------------------------------------------------------------
  // 📑 Build table rows for Utility Bills Summary
  // ------------------------------------------------------------------
  const billTableData = dedupedProviders
    .map((p) => {
      // Try multiple sources for bill data: fetched bill, latest_bill, or automation results
      let bill = null;
      let amount = null;
      let date = null;
      let paid = 'Unpaid';
      
      // First try the most recently fetched bill
      if (lastFetchedProviderId === p.id && fetchedBill) {
        bill = fetchedBill;
        amount = bill.current_bill_amount || bill.amount;
        date = bill.due_date || bill.date;
        paid = bill.paid_status || 'Unpaid';
      }
      // Then try the provider's latest_bill
      else if (p.latest_bill) {
        bill = p.latest_bill;
        amount = bill.amount;
        date = bill.date;
        paid = 'Unpaid'; // Default for saved bills
      }
      // Finally try automation results
      else {
        const automationResult = automationResults.find(result => result.providerId === p.id);
        if (automationResult && automationResult.extractedTransactions?.length > 0) {
          // Get the most recent transaction
          const sortedTransactions = [...automationResult.extractedTransactions].sort((a, b) => {
            const dateA = new Date(a.date);
            const dateB = new Date(b.date);
            return dateB.getTime() - dateA.getTime();
          });
          const recentTransaction = sortedTransactions[0];
          amount = recentTransaction.amount;
          date = recentTransaction.date;
          paid = 'Unpaid';
        }
      }
      
      // If amount is missing, mark as 'N/A' so we still show the row
      if (!amount) {
        amount = 'N/A';
      }

      // If date is missing, fallback to today's date
      if (!date || date === 'N/A') {
        date = new Date().toISOString().split('T')[0];
      }
      
      return {
        id: p.id,
        type: p.type,
        name: p.name,
        date,
        amount,
        paid,
      };
    });

  useEffect(() => {
    const initializePage = async () => {
      // Load automation results and dashboard data
      loadAutomationResults();
      await fetchDashboard();
    };

    initializePage();
  }, [searchParams]);

  // Bill status calculation
  const billStatus = checkBillStatus();

  const loadAutomationResults = () => {
    let results: AutomationResult[] = [];

    // Check if we're coming from automation results
    const resultData = searchParams.get('result');
    const providerId = searchParams.get('providerId');
    const providerName = searchParams.get('providerName');
    const providerType = searchParams.get('providerType');

    if (resultData && providerId && providerName) {
      try {
        const parsed = JSON.parse(decodeURIComponent(resultData));
        const newResult: AutomationResult = {
          taskId: `temp_${Date.now()}`,
          providerId,
          providerName,
          providerType: providerType || 'utility',
          status: 'completed',
          analysisResult: parsed.step7_table_extraction || 'No analysis available',
          extractedTransactions: parsed.extracted_transactions || [],
          completedAt: new Date().toISOString()
        };
        results = [newResult];
        setSelectedResult(newResult);
        
        // Save this new result to localStorage
        const savedResults = localStorage.getItem('automationResults');
        let existingResults: AutomationResult[] = [];
        if (savedResults) {
          try {
            existingResults = JSON.parse(savedResults);
          } catch (error) {
            console.error('Error parsing saved results:', error);
          }
        }
        
        // Remove any existing result for this provider and add the new one
        const updatedResults = [...existingResults.filter(r => r.providerId !== providerId), newResult];
        localStorage.setItem('automationResults', JSON.stringify(updatedResults));
        results = updatedResults;
      } catch (error) {
        console.error('Error parsing result data:', error);
      }
    } else {
      // Load saved automation results from localStorage
      const savedResults = localStorage.getItem('automationResults');
      if (savedResults) {
        try {
          results = JSON.parse(savedResults);
        } catch (error) {
          console.error('Error loading saved results:', error);
        }
      }
    }

    // Remove duplicates based on provider name and type, keeping the most recent
    const uniqueResults = results.filter((result, index, self) => {
      const latestIndex = self.findLastIndex(r => r.providerName === result.providerName && r.providerType === result.providerType);
      return index === latestIndex;
    });

    setAutomationResults(uniqueResults);
    processCategories(uniqueResults);
    setLoading(false);
  };

  const processCategories = (results: AutomationResult[]) => {
    const categoryMap = new Map<string, AutomationResult[]>();

    // Extract number of tenants from URL parameters
    const tenants = parseInt(searchParams.get('tenants') || '1');
    
    // Group results by category, but only keep the latest per provider
    const latestProviderResults = new Map<string, AutomationResult>();
    
    results.forEach(result => {
      const providerKey = `${result.providerName}_${result.providerType}`;
      const existing = latestProviderResults.get(providerKey);
      
      if (!existing || new Date(result.completedAt) > new Date(existing.completedAt)) {
        latestProviderResults.set(providerKey, result);
      }
    });

    // Now group the latest results by category
    Array.from(latestProviderResults.values()).forEach(result => {
      const category = result.providerType.toLowerCase();
      if (!categoryMap.has(category)) {
        categoryMap.set(category, []);
      }
      categoryMap.get(category)!.push(result);
    });

    // Create category summaries
    const categorySummaries: CategorySummary[] = Array.from(categoryMap.entries()).map(([type, categoryResults]) => {
      // Use the most recent bill amount for each provider (reverted from sum)
      const totalAmount = categoryResults.reduce((sum, result) => {
        const mostRecentAmount = extractMostRecentBillAmount(result);
        return sum + mostRecentAmount;
      }, 0);

      const billCount = categoryResults.reduce((sum, result) => {
        return sum + (result.extractedTransactions?.length || 0);
      }, 0);

      // Average = total amount / number of tenants
      const avgAmount = totalAmount / Math.max(tenants, 1);

      return {
        type: type.charAt(0).toUpperCase() + type.slice(1),
        icon: getCategoryIcon(type),
        totalAmount, // Now shows most recent bill amount per provider
        billCount,
        avgAmount, // Now divided by number of tenants
        trend: 'stable' as const, // Could be calculated based on historical data
        results: categoryResults,
        isExpanded: categoryResults.length === 1 // Auto-expand if only one category
      };
    });

    setCategories(categorySummaries.sort((a, b) => b.totalAmount - a.totalAmount));
  };

  const extractMostRecentBillAmount = (result: AutomationResult): number => {
    // First try to get from extracted transactions (most accurate)
    if (result.extractedTransactions && result.extractedTransactions.length > 0) {
      // Sort transactions by date to get the most recent
      const sortedTransactions = [...result.extractedTransactions].sort((a, b) => {
        const dateA = new Date(a.date);
        const dateB = new Date(b.date);
        return dateB.getTime() - dateA.getTime(); // Most recent first
      });
      
      // Get the amount from the most recent transaction
      const mostRecentTransaction = sortedTransactions[0];
      if (mostRecentTransaction?.amount) {
        const amount = parseFloat(mostRecentTransaction.amount.replace(/[$,]/g, ''));
        if (!isNaN(amount)) {
          return Math.abs(amount); // Use absolute value to handle negative amounts
        }
      }
    }
    
    // Fallback to analysis text parsing if no transactions available
    return extractTotalAmount(result.analysisResult);
  };

  const extractTotalAmount = (analysisText: string): number => {
    const matches = analysisText.match(/\$(\d+\.?\d*)/g);
    if (matches) {
      return matches.reduce((sum, match) => {
        const amount = parseFloat(match.replace('$', ''));
        return sum + (isNaN(amount) ? 0 : amount);
      }, 0);
    }
    return 0;
  };

  const toggleCategory = (index: number) => {
    setCategories(prev => prev.map((cat, i) => 
      i === index ? { ...cat, isExpanded: !cat.isExpanded } : cat
    ));
  };

  const formatAmount = (amount: number) => {
    return `$${amount.toFixed(2)}`;
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  // DELETE FUNCTIONALITY
  const handleDeleteResult = (taskId: string, resultName: string) => {
    setShowDeleteModal({
      show: true,
      type: 'result',
      target: taskId,
      name: resultName
    });
  };

  const handleDeleteCategory = (categoryType: string) => {
    setShowDeleteModal({
      show: true,
      type: 'category',
      target: categoryType,
      name: categoryType
    });
  };

  const handleDeleteAll = () => {
    setShowDeleteModal({
      show: true,
      type: 'all',
      name: 'All Bills'
    });
  };

  const confirmDelete = () => {
    const { type, target } = showDeleteModal;

    if (type === 'result' && target) {
      // Delete specific automation result
      const updatedResults = automationResults.filter(result => result.taskId !== target);
      setAutomationResults(updatedResults);
      processCategories(updatedResults);
      
      // Update localStorage
      localStorage.setItem('automationResults', JSON.stringify(updatedResults));
      
      // Close selected result if it was deleted
      if (selectedResult?.taskId === target) {
        setSelectedResult(null);
      }
    } else if (type === 'category' && target) {
      // Delete entire category
      const updatedResults = automationResults.filter(result => 
        result.providerType.toLowerCase() !== target.toLowerCase()
      );
      setAutomationResults(updatedResults);
      processCategories(updatedResults);
      
      // Update localStorage
      localStorage.setItem('automationResults', JSON.stringify(updatedResults));
      
      // Close selected result if it was in deleted category
      if (selectedResult && selectedResult.providerType.toLowerCase() === target.toLowerCase()) {
        setSelectedResult(null);
      }
    } else if (type === 'all') {
      // Delete all results
      setAutomationResults([]);
      setCategories([]);
      setSelectedResult(null);
      
      // Clear localStorage
      localStorage.removeItem('automationResults');
    }

    setShowDeleteModal({ show: false, type: 'result' });
  };

  const cancelDelete = () => {
    setShowDeleteModal({ show: false, type: 'result' });
  };

  // Unified handler to fetch bills for a provider (used by card & table)
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
      // Get JWT token for authentication
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('Authentication Required', 'Please log in to fetch bills');
        redirectToLogin();
        return;
      }

      // 1. Start the job via shared API helper
      const { job_id } = await billFetcher.start(provider.id, forceRefresh);

      // 2. Poll for status
      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 2000));
        const statusData = await billFetcher.status(job_id);
        setFetchProgress(statusData.progress || 0);

        if (statusData.status === 'done') {
          // Save the fetched bill data
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

          // Update automation results in state and localStorage
          const updatedResults = [...automationResults.filter(r => r.providerId !== provider.id), automationResult];
          setAutomationResults(updatedResults);
          localStorage.setItem('automationResults', JSON.stringify(updatedResults));
          
          // Update provider with latest bill data and save to localStorage
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
          
          // Save updated providers to localStorage for persistence
          localStorage.setItem('providers_data', JSON.stringify(updatedProviders));
          
          // Process categories to update the display
          processCategories(updatedResults);
          
          toast.success('Bill Extracted', `Successfully extracted bill for ${provider.name}`);
          await fetchDashboard();
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

  // Load saved providers data on component mount
  useEffect(() => {
    const loadSavedProviders = () => {
      try {
        const savedProviders = localStorage.getItem('providers_data');
        if (savedProviders) {
          const parsedProviders = JSON.parse(savedProviders);
          // Merge with fetched providers, preferring saved data for latest_bill
          setProviders(prevProviders => {
            const mergedProviders = prevProviders.map(provider => {
              const savedProvider = parsedProviders.find((p: Provider) => p.id === provider.id);
              return savedProvider?.latest_bill ? { ...provider, latest_bill: savedProvider.latest_bill } : provider;
            });
            return mergedProviders;
          });
        }
      } catch (error) {
        console.error('Error loading saved providers:', error);
      }
    };
    // Load saved providers after initial data fetch
    const timer = setTimeout(loadSavedProviders, 100);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    setHouses(getHouses());
  }, []);

  useEffect(() => {
    if (houses.length > 0 && !selectedHouseId) {
      setSelectedHouseId(houses[0].id);
    }
  }, [houses, selectedHouseId]);

  // Add a new function to delete all providers permanently
  const handleDeleteAllProviders = async () => {
    setDeleteLoading(true);
    try {
      // Delete each provider via API
      for (const provider of providers) {
        if (provider.id) {
          await providersApi.delete(provider.id);
        }
      }
      // Clear from local state and localStorage
      setProviders([]);
      localStorage.removeItem('providers_data');
      toast.success('All Providers Deleted', 'All provider records have been permanently removed.');
      setShowDeleteModal({ show: false, type: 'result' });
      // Optionally, refresh dashboard data
      await fetchDashboard();
    } catch (err) {
      toast.error('Delete Failed', 'Failed to delete all providers.');
    } finally {
      setDeleteLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500 mx-auto"></div>
            <p className="mt-4 text-white">Loading billing data...</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Sum latest amounts across active utility types (one per provider)
  const totalAmount = billTableData.reduce((sum, row) => {
    const amt = parseFloat(String(row.amount).replace(/[$,]/g, ''));
    return sum + (isNaN(amt) ? 0 : amt);
  }, 0);

  const totalBills = billTableData.length;

  // Placeholder (to be replaced once Plaid integration provides real data)
  const tenantsPaidAmount = 0;

  // Extract number of tenants from URL for display
  const tenants = parseInt(searchParams.get('tenants') || '1');

  return (
    <Layout>
      <div className="mb-16 mt-8 px-4 md:px-12 lg:px-24 xl:px-32">
        <div className="rounded-3xl bg-gray-900/70 border border-gray-700/60 shadow-xl p-8 md:p-12">
          <h2 className="text-4xl font-bold text-white mb-10">Connect to Your Providers</h2>
          {/* House Selector */}
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
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-10">
            {/* Water Card */}
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 text-center hover:border-pink-500 transition-all duration-300 group hover:bg-gray-800">
              <div className="mb-6">
                <div className="w-24 h-24 mx-auto mb-6 flex items-center justify-center">
                  <svg className="w-16 h-16 text-blue-400 group-hover:text-pink-400 transition-colors" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Water</h3>
              <p className="text-gray-400 text-sm mb-6">Track your water utility bills and usage patterns</p>
              <button 
                onClick={() => router.push(`/providers/add?user_id=${userId}&type=water&house_id=${selectedHouseId}`)}
                className="w-full bg-pink-600 hover:bg-pink-500 text-white py-3 px-6 rounded-xl transition duration-200 font-bold"
              >
                MANAGE WATER BILLS
              </button>
              <p className="text-xs text-gray-500 mt-3">FROM WATER UTILITIES</p>
            </div>
            {/* Electricity Card */}
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 text-center hover:border-pink-500 transition-all duration-300 group hover:bg-gray-800">
              <div className="mb-6">
                <div className="w-24 h-24 mx-auto mb-6 flex items-center justify-center">
                  <svg className="w-16 h-16 text-yellow-400 group-hover:text-pink-400 transition-colors" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Electricity</h3>
              <p className="text-gray-400 text-sm mb-6">Monitor your electric bills and energy consumption</p>
              <button 
                onClick={() => router.push(`/providers/add?user_id=${userId}&type=electric&house_id=${selectedHouseId}`)}
                className="w-full bg-pink-600 hover:bg-pink-500 text-white py-3 px-6 rounded-xl transition duration-200 font-bold"
              >
                MANAGE ELECTRIC BILLS
              </button>
              <p className="text-xs text-gray-500 mt-3">FROM ELECTRIC PROVIDERS</p>
            </div>
            {/* Gas Card */}
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 text-center hover:border-pink-500 transition-all duration-300 group hover:bg-gray-800">
              <div className="mb-6">
                <div className="w-24 h-24 mx-auto mb-6 flex items-center justify-center">
                  <svg className="w-16 h-16 text-orange-400 group-hover:text-pink-400 transition-colors" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Gas</h3>
              <p className="text-gray-400 text-sm mb-6">Track your natural gas bills and heating costs</p>
              <button 
                onClick={() => router.push(`/providers/add?user_id=${userId}&type=gas&house_id=${selectedHouseId}`)}
                className="w-full bg-pink-600 hover:bg-pink-500 text-white py-3 px-6 rounded-xl transition duration-200 font-bold"
              >
                MANAGE GAS BILLS
              </button>
              <p className="text-xs text-gray-500 mt-3">FROM GAS COMPANIES</p>
            </div>
            {/* Internet Card */}
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 text-center hover:border-pink-500 transition-all duration-300 group hover:bg-gray-800">
              <div className="mb-6">
                <div className="w-24 h-24 mx-auto mb-6 flex items-center justify-center">
                  <svg className="w-16 h-16 text-purple-400 group-hover:text-pink-400 transition-colors" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 4a1 1 0 011-1h12a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1V8zm8 2a1 1 0 100 2h2a1 1 0 100-2h-2z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Internet</h3>
              <p className="text-gray-400 text-sm mb-6">Monitor your internet and cable service bills</p>
              <button 
                onClick={() => router.push(`/providers/add?user_id=${userId}&type=internet&house_id=${selectedHouseId}`)}
                className="w-full bg-pink-600 hover:bg-pink-500 text-white py-3 px-6 rounded-xl transition duration-200 font-bold"
              >
                MANAGE INTERNET BILLS
              </button>
              <p className="text-xs text-gray-500 mt-3">FROM ISP PROVIDERS</p>
            </div>
            {/* Add More Card */}
            <div className="bg-gray-900 border-2 border-dashed border-gray-600 rounded-2xl p-8 text-center hover:border-pink-500 hover:bg-gray-800 transition-all duration-300">
              <div className="mb-6">
                <div className="w-24 h-24 mx-auto mb-6 flex items-center justify-center">
                  <svg className="w-16 h-16 text-gray-500 hover:text-pink-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </div>
              </div>
              <h3 className="text-2xl font-bold text-gray-300 mb-3">Add More</h3>
              <p className="text-gray-500 text-sm mb-6">Add other utility types or custom providers</p>
              <button 
                onClick={() => router.push(`/providers/add?user_id=${userId}&house_id=${selectedHouseId}`)}
                className="w-full bg-gray-700 hover:bg-pink-600 text-white py-3 px-6 rounded-xl transition duration-200 font-bold"
              >
                ADD CUSTOM PROVIDER
              </button>
              <p className="text-xs text-gray-500 mt-3">OTHER BILL TYPES</p>
            </div>
          </div>
          {/* Add gap below utility cards */}
          <div className="mb-12" />
          {/* Your Connected Providers Section (show all providers for the user) */}
          {providers.length > 0 && (
            <div className="mb-16 bg-gray-900/70 border border-gray-700/60 rounded-3xl shadow-xl p-8 md:p-12">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-4xl font-bold text-white">Your Connected Providers</h2>
                <button
                  onClick={() => setShowDeleteModal({ show: true, type: 'all', name: 'All Providers' })}
                  className="bg-red-600 hover:bg-red-500 text-white px-6 py-2 rounded-2xl transition-all duration-300 font-medium shadow-lg hover:shadow-red-500/20 hover:scale-105"
                  title="Delete All Providers"
                >
                  <span className="flex items-center space-x-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span>Delete All</span>
                  </span>
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {providers.map((provider) => {
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
                          onClick={() => handleFetch(provider, false)}
                          className="group/btn w-full bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white px-6 py-4 rounded-2xl transition-all duration-300 font-bold text-base shadow-lg hover:shadow-pink-500/30 hover:scale-105 relative overflow-hidden mb-2"
                        >
                          <span className="relative z-10 flex items-center justify-center space-x-2">
                            <span className="text-xl group-hover/btn:scale-110 transition-transform">🔍</span>
                            <span>{fetchingProviderId === provider.id ? 'Fetching...' : 'View Bills'}</span>
                          </span>
                        </button>
                        {fetchingProviderId === provider.id && (
                          <div className="w-full flex flex-col items-center">
                            <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                              <div className="bg-pink-500 h-3 rounded-full transition-all duration-300" style={{ width: `${fetchProgress}%` }} />
                            </div>
                            <span className="text-pink-300 text-sm font-semibold">{fetchProgress}%</span>
                          </div>
                        )}
                        <div className="flex space-x-2 w-full mt-2">
                          <button
                            onClick={async () => {
                              await handleFetch(provider, false);
                              router.push(`/bills?user_id=${userId}&provider_id=${provider.id}`);
                            }}
                            disabled={fetchingProviderId === provider.id}
                            className={`flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 px-4 py-2 rounded-lg transition duration-200 text-sm font-medium ${fetchingProviderId === provider.id ? 'opacity-60 cursor-not-allowed' : ''}`}
                          >
                            {fetchingProviderId === provider.id ? 'Fetching...' : 'View Bills'}
                          </button>
                        </div>
                      </div>
                      {/* Enhanced Delete Button */}
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
          )}
          {/* Bill Analysis section starts here, visually grouped with providers */}
          {providers.length > 0 && (
            <div className="mt-16">
              {/* Header */}
              <div className="mb-12 flex justify-between items-center">
                <div className="space-y-2">
                  <h1 className="text-5xl font-bold bg-gradient-to-r from-white via-pink-100 to-pink-200 bg-clip-text text-transparent drop-shadow-2xl">
                    Bills Analysis
                  </h1>
                  <p className="text-gray-300 text-lg font-medium">
                    Interactive utility bill breakdown and insights
                    {tenants > 1 && <span className="ml-2 text-pink-400 font-semibold">• {tenants} tenants</span>}
                  </p>
                </div>
                <div className="flex items-center space-x-4">
                  {categories.length > 0 && (
                    <button
                      onClick={handleDeleteAll}
                      className="group bg-red-600 hover:bg-red-500 text-white px-6 py-3 rounded-2xl transition-all duration-300 font-medium shadow-lg hover:shadow-red-500/20 hover:scale-105"
                    >
                      <span className="flex items-center space-x-2">
                        <svg className="w-5 h-5 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        <span>Delete All</span>
                      </span>
                    </button>
                  )}
                </div>
              </div>
              {/* Summary Dashboard */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
                <div className="group relative bg-gradient-to-br from-pink-600 to-purple-600 rounded-3xl p-8 text-white shadow-2xl shadow-pink-500/20 hover:shadow-pink-500/40 transition-all duration-300 hover:scale-105">
                  <div className="absolute inset-0 bg-gradient-to-br from-pink-500/20 to-purple-500/20 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <div className="relative">
                    <div className="text-4xl font-bold mb-4">{formatAmount(totalAmount)}</div>
                    <div className="text-pink-100 text-lg font-semibold">This Month Bills</div>
                  </div>
                </div>
                <div className="group relative bg-gray-900/60 backdrop-blur-xl border border-gray-700/50 rounded-3xl p-8 text-white shadow-2xl shadow-gray-900/50 hover:shadow-gray-700/50 transition-all duration-300 hover:scale-105">
                  <div className="absolute inset-0 bg-gradient-to-br from-gray-700/10 to-gray-600/10 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <div className="relative">
                    <div className="text-4xl font-bold mb-4">{formatAmount(tenantsPaidAmount)}</div>
                    <div className="text-gray-300 text-lg font-semibold">Tenants Total Paid Amount</div>
                  </div>
                </div>
              </div>
              {/* Active Utility Types Section */}
              {dedupedProviders.length > 0 && (
                <div className="bg-gray-900/60 backdrop-blur-xl border border-gray-700/50 rounded-3xl shadow-2xl shadow-gray-900/50 mb-16">
                  <div className="px-8 py-6 border-b border-gray-700/50 bg-gradient-to-r from-gray-800/50 to-gray-900/50 rounded-t-3xl">
                    <h2 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-200 bg-clip-text text-transparent">
                      Active Utility Types
                    </h2>
                    <p className="text-gray-400 text-base mt-2 font-medium">
                      Your connected utility accounts and their billing status
                    </p>
                  </div>
                  <div className="p-10">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                      {dedupedProviders.map((provider) => {
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
                        return (
                          <div 
                            key={provider.id} 
                              className={`group relative bg-gradient-to-br ${getProviderGradient(provider.type)} backdrop-blur-xl border border-gray-600/50 hover:border-pink-500/50 rounded-2xl p-10 flex flex-col items-center justify-between min-h-[340px] transition-all duration-300 hover:scale-105 shadow-xl`}
                            >
                              <div className="flex flex-col items-center mb-6 w-full">
                                <div className="text-5xl bg-gray-800/60 rounded-2xl p-5 mb-4">{getProviderIcon(provider.type)}</div>
                                <h3 className="font-bold text-white text-2xl mb-1 truncate text-center w-full">{provider.name}</h3>
                                <p className="text-gray-400 text-base font-medium capitalize mb-2 text-center">{provider.type}</p>
                                  </div>
                              <div className="w-full flex flex-col items-center">
                                <div className="mt-4 flex flex-col space-y-2">
                                  <button
                                    onClick={() => handleFetch(provider, false)}
                                    className="group/btn w-full bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white px-6 py-4 rounded-2xl transition-all duration-300 font-bold text-base shadow-lg hover:shadow-pink-500/30 hover:scale-105 relative overflow-hidden mb-2"
                                  >
                                    <span className="relative z-10 flex items-center justify-center space-x-2">
                                      <span className="text-xl group-hover/btn:scale-110 transition-transform">🔍</span>
                                      <span>{fetchingProviderId === provider.id ? 'Fetching...' : 'View Bills'}</span>
                                    </span>
                                  </button>
                                  {fetchingProviderId === provider.id && (
                                    <div className="w-full flex flex-col items-center">
                                      <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                                        <div className="bg-pink-500 h-3 rounded-full transition-all duration-300" style={{ width: `${fetchProgress}%` }} />
                                      </div>
                                      <span className="text-pink-300 text-sm font-semibold">{fetchProgress}%</span>
                                    </div>
                                  )}
                                  <div className="flex space-x-2 w-full mt-2">
                                    <button
                                      onClick={async () => {
                                        await handleFetch(provider, false);
                                        router.push(`/bills?user_id=${userId}&provider_id=${provider.id}`);
                                      }}
                                      disabled={fetchingProviderId === provider.id}
                                      className={`flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 px-4 py-2 rounded-lg transition duration-200 text-sm font-medium ${fetchingProviderId === provider.id ? 'opacity-60 cursor-not-allowed' : ''}`}
                                    >
                                      {fetchingProviderId === provider.id ? 'Fetching...' : 'View Bills'}
                                    </button>
                                  </div>
                                </div>
                                {/* Show latest bill if already saved in provider or freshly fetched */}
                                { (provider.latest_bill || (lastFetchedProviderId === provider.id && fetchedBill)) && (
                                  <div className="mt-4 w-full bg-gray-800/60 rounded-xl p-4 border border-gray-700/50">
                                    <h4 className="text-base font-bold text-pink-400 mb-2 flex items-center space-x-2">
                                      <span>📄</span>
                                      <span>Latest Bill</span>
                                    </h4>
                                    <table className="w-full text-sm">
                                      <tbody>
                                        <tr>
                                          <td className="py-2 pr-4 font-bold text-gray-300">Amount</td>
                                          <td className="py-2 text-pink-200 font-mono">{(provider.latest_bill || (lastFetchedProviderId === provider.id && fetchedBill))?.current_bill_amount || (provider.latest_bill || (lastFetchedProviderId === provider.id && fetchedBill))?.amount}</td>
                                        </tr>
                                        <tr>
                                          <td className="py-2 pr-4 font-bold text-gray-300">Due Date</td>
                                          <td className="py-2 text-pink-200 font-mono">{(provider.latest_bill || (lastFetchedProviderId === provider.id && fetchedBill))?.due_date}</td>
                                        </tr>
                                        {/* Add more fields as needed */}
                                      </tbody>
                                    </table>
                                      </div>
                                    )}
                                {fetchErrors[provider.id!] && <div className="text-red-400 mt-4 text-center">Error: {fetchErrors[provider.id!]}</div>}
                              </div>
                            {/* Delete Provider Button */}
                              <button
                              onClick={() => {
                                if (provider.id) handleDeleteProvider(provider.id, provider.name);
                              }}
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
              )}

              {/* Interactive Category Tree */}
              <div className="space-y-6">
                <h2 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-200 bg-clip-text text-transparent mb-8">
                📋 Utility Bills Summary
                </h2>
                
              {/* Utility Bills Summary Table */}
              <div className="overflow-x-auto mb-12">
                <table className="min-w-full text-sm text-left">
                  <thead>
                    <tr className="border-b border-gray-700/50">
                      <th className="px-4 py-3 text-gray-400 font-bold"> </th>
                      <th className="px-4 py-3 text-gray-400 font-bold">Bill Type</th>
                      <th className="px-4 py-3 text-gray-400 font-bold">Bill Name</th>
                      <th className="px-4 py-3 text-gray-400 font-bold">Bill Date</th>
                      <th className="px-4 py-3 text-gray-400 font-bold text-right">Bill Amount</th>
                      <th className="px-4 py-3 text-gray-400 font-bold text-right">Paid Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {billTableData.map((row) => {
                      const category = categories.find(cat => cat.type.toLowerCase() === row.type.toLowerCase());
                      const isExpanded = expandedCategoryType === row.type;
                      return [
                        <tr
                          key={row.id}
                          className="border-b border-gray-700/30 hover:bg-gray-800/20 transition-colors cursor-pointer"
                          onClick={() => setExpandedCategoryType(isExpanded ? null : row.type)}
                        >
                          <td className="px-4 py-4">
                            <div className="flex flex-col items-center">
                              <button
                                onClick={e => { e.stopPropagation(); handleFetch(row as unknown as Provider, true); }}
                                disabled={fetchingProviderId === row.id}
                                className="text-pink-400 hover:text-pink-200 disabled:opacity-50"
                                title="Refresh bill"
                              >
                                {fetchingProviderId === row.id ? '⏳' : '🔄'}
                              </button>
                              {fetchingProviderId === row.id && (
                                <div className="mt-1 w-16 h-1 bg-gray-700 rounded-full overflow-hidden">
                                  <div
                                    className="h-1 bg-pink-500"
                                    style={{ width: `${fetchProgress}%` }}
                                  />
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-4 capitalize text-white font-bold">{row.type}</td>
                          <td className="px-4 py-4 text-gray-300">{row.name}</td>
                          <td className="px-4 py-4 text-gray-300">{row.date || '-'}</td>
                          <td className="px-4 py-4 text-right font-mono text-pink-400 font-semibold">{row.amount || '-'}</td>
                          <td className="px-4 py-4 text-right text-gray-300">{row.paid}</td>
                        </tr>,
                        isExpanded && category && (
                          <tr key={row.id + '-expanded'}>
                            <td colSpan={6} className="p-0 bg-transparent">
                              <div className="bg-gray-900/60 backdrop-blur-xl border border-gray-700/50 rounded-3xl overflow-hidden shadow-2xl shadow-gray-900/50 hover:shadow-gray-700/50 transition-all duration-300 my-4 mx-2">
                                {/* Category Header */}
                                <div className="p-8 bg-gradient-to-r from-gray-800/50 to-gray-900/50">
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center space-x-6">
                                      <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${getCategoryGradient(category.type)} flex items-center justify-center text-3xl shadow-lg`}>
                                        {category.icon}
                                      </div>
                                      <div>
                                        <h3 className="text-3xl font-bold text-white">{category.type}</h3>
                                        <p className="text-gray-300 text-lg font-medium mt-1">
                                          {category.results.length} provider{category.results.length !== 1 ? 's' : ''} • {category.billCount} transaction{category.billCount !== 1 ? 's' : ''}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="flex items-center space-x-6">
                                      <div className="text-right">
                                        <div className="text-3xl font-bold text-white">{formatAmount(category.totalAmount)}</div>
                                        <div className="text-base text-gray-400 font-medium">Avg: {formatAmount(category.avgAmount)}</div>
                                      </div>
                                      <button
                                        onClick={e => { e.stopPropagation(); handleDeleteCategory(category.type); }}
                                        className="bg-red-600 hover:bg-red-500 text-white rounded-full p-2 transition-all duration-200 hover:scale-110 hover:shadow-lg"
                                        title={`Delete all ${category.type} bills`}
                                      >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                      </button>
                                      <div 
                                        className={`transform transition-all duration-300 cursor-pointer p-2 rounded-xl hover:bg-gray-700/50 ${isExpanded ? 'rotate-180' : ''}`}
                                        onClick={e => { e.stopPropagation(); setExpandedCategoryType(null); }}
                                      >
                                        <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                                {/* Category Content */}
                                <div className="p-8">
                                  <div className="space-y-4">
                                    {category.results.map((result, index) => (
                                      <div key={index} className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/30">
                                        <div className="flex items-center justify-between mb-3">
                                          <h4 className="text-lg font-bold text-white">{result.providerName}</h4>
                                          <button
                                            onClick={() => handleDeleteResult(result.taskId, result.providerName)}
                                            className="text-red-400 hover:text-red-300 transition-colors"
                                            title="Delete this result"
                                          >
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                          </button>
                                        </div>
                                        <div className="text-sm text-gray-300 mb-3">
                                          <p><strong>Status:</strong> {result.status}</p>
                                          <p><strong>Completed:</strong> {formatDate(result.completedAt)}</p>
                                        </div>
                                        {result.extractedTransactions && result.extractedTransactions.length > 0 && (
                                          <div>
                                            <h5 className="text-md font-bold text-pink-400 mb-2">Extracted Transactions:</h5>
                                            <div className="space-y-2">
                                              {result.extractedTransactions.slice(0, 3).map((transaction, tIndex) => (
                                                <div key={tIndex} className="bg-gray-700/30 rounded-lg p-3">
                                                  <div className="flex justify-between items-center">
                                                    <span className="text-gray-300">{transaction.description}</span>
                                                    <span className="text-pink-200 font-mono">{transaction.amount}</span>
                                                  </div>
                                                  <div className="text-xs text-gray-400 mt-1">{transaction.date}</div>
                                                </div>
                                              ))}
                                              {result.extractedTransactions.length > 3 && (
                                                <div className="text-sm text-gray-400 text-center">
                                                  +{result.extractedTransactions.length - 3} more transactions
                                                </div>
                                              )}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )
                      ];
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
      {/* Provider Delete Confirmation Modal */}
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
      {/* Add ConfirmModal for Delete All Providers */}
      {showDeleteModal.show && showDeleteModal.type === 'all' && (
        <ConfirmModal
          isOpen={showDeleteModal.show}
          title="Delete All Providers?"
          message="This will permanently remove all providers and their associated bills. This action cannot be undone."
          loading={deleteLoading}
          onConfirm={handleDeleteAllProviders}
          onCancel={cancelDelete}
          confirmText="Delete All"
          cancelText="Cancel"
          type="danger"
        />
      )}
    </Layout>
  );
}