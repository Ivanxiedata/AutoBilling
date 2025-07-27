'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import Link from 'next/link';
import { useToast } from '@/hooks/useToast';
import { ToastContainer } from '@/components/ui/Toast';
import { jwtDecode } from 'jwt-decode';
import { 
  getHouses, 
  getProviders, 
  calculatePortfolioTotals, 
  type House, 
  type Provider 
} from '@/lib/housesData';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';

interface DecodedToken {
  sub: string;
  exp: number;
}

export default function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  
  const [houses, setHouses] = useState<House[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [selectedHouseId, setSelectedHouseId] = useState<string | null>(null);

  // Enhanced user ID validation
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

  // Load data from centralized data management
  const loadDashboardData = async () => {
    try {
      const housesData = getHouses();
      const providersData = getProviders();
      
      setHouses(housesData);
      setProviders(providersData);
      setLoading(false);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      loadDashboardData();
    } else {
      setLoading(false);
    }

    // Listen for data updates from other components
    const handleHousesUpdated = (event: CustomEvent) => {
      setHouses(event.detail);
    };

    const handleProvidersUpdated = (event: CustomEvent) => {
      setProviders(event.detail);
    };

    window.addEventListener('houses-updated', handleHousesUpdated as EventListener);
    window.addEventListener('providers-updated', handleProvidersUpdated as EventListener);

    return () => {
      window.removeEventListener('houses-updated', handleHousesUpdated as EventListener);
      window.removeEventListener('providers-updated', handleProvidersUpdated as EventListener);
    };
  }, [userId]);

  // Set default selected house when houses are loaded
  useEffect(() => {
    if (houses.length > 0 && !selectedHouseId) {
      setSelectedHouseId(houses[0].id);
    }
  }, [houses, selectedHouseId]);

  const getUpcomingBills = () => {
    return providers.filter(p => p.latest_bill).map(provider => {
      const house = houses.find(h => h.id === provider.house_id);
      return {
        ...provider,
        house_name: house?.name || 'Unknown Property',
        amount: provider.latest_bill?.amount || '0.00'
      };
    }).slice(0, 5); // Show top 5 upcoming bills
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

  // Calculate totals using the centralized function
  const totals = calculatePortfolioTotals();

  // ---------------------------------------------
  // Build monthly totals for chart (filtered by selected house)
  // ---------------------------------------------
  const filteredProviders = selectedHouseId
    ? providers.filter((p) => p.house_id === selectedHouseId)
    : providers;

  const monthlyTotals: { month: string; total: number }[] = Array.from({ length: 12 }).map((_, idx) => {
    const monthIndex = idx; // 0=Jan
    const label = new Date(0, monthIndex).toLocaleString('default', { month: 'short' });
    return { month: label, total: 0 };
  });

  filteredProviders.forEach((p) => {
    if (p.latest_bill?.date && p.latest_bill.amount) {
      const d = new Date(p.latest_bill.date);
      if (d.getFullYear() === selectedYear) {
        const m = d.getMonth();
        const amt = parseFloat(String(p.latest_bill.amount).replace(/[$,]/g, '')) || 0;
        monthlyTotals[m].total += amt;
      }
    }
  });

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500 mx-auto"></div>
            <p className="mt-4 text-white">Loading dashboard...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (!userId) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded max-w-md">
              Please log in to view your dashboard
            </div>
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
          <h1 className="text-4xl font-bold text-white drop-shadow-lg">Portfolio Dashboard</h1>
          <p className="text-gray-200 drop-shadow">
            Overview of all your rental properties and utilities
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-1 lg:grid-cols-1 gap-6 mb-8">
          <div className="bg-gradient-to-br from-pink-600 to-pink-500 rounded-2xl p-6 text-white shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold mb-1">{totals.totalProperties}</div>
                <div className="text-pink-100">Properties</div>
              </div>
              <div className="text-4xl opacity-80">🏠</div>
            </div>
          </div>
        </div>

        {/* Monthly Spend Chart */}
        <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-2xl p-6 shadow-2xl mb-10">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-4">
              <h2 className="text-2xl font-bold text-white">Monthly Utility Spend</h2>
              <select
                value={selectedHouseId || ''}
                onChange={e => setSelectedHouseId(e.target.value)}
                className="bg-gray-800 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm"
              >
                {houses.map(house => (
                  <option key={house.id} value={house.id}>{house.name}</option>
                ))}
              </select>
            </div>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              className="bg-gray-800 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm"
            >
              {Array.from({ length: 5 }).map((_, idx) => {
                const year = new Date().getFullYear() - idx;
                return (
                  <option key={year} value={year}>{year}</option>
                );
              })}
            </select>
          </div>
          <div style={{ width: '100%', height: 300 }}>
            <ResponsiveContainer>
              <LineChart data={monthlyTotals} margin={{ left: 0, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="month" stroke="#aaa" />
                <YAxis stroke="#aaa" tickFormatter={(v: number) => `$${v}`}/>
                <Tooltip formatter={(value: string | number | (string | number)[]) => `$${value}`} />
                <Line type="monotone" dataKey="total" stroke="#ec4899" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-1 gap-8">
          {/* Properties Overview */}
          <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-white">Properties</h2>
              <Link
                href={`/houses?user_id=${userId}`}
                className="bg-pink-600 hover:bg-pink-500 text-white px-4 py-2 rounded-lg transition duration-200 text-sm font-medium"
              >
                Manage Properties
              </Link>
            </div>
            
            {houses.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-gray-400 text-sm mb-4">No properties added yet</div>
                <Link
                  href={`/houses?user_id=${userId}`}
                  className="text-pink-400 hover:text-pink-300 text-sm inline-block"
                >
                  Add your first property →
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {houses.map((house) => (
                  <div key={house.id} className="bg-gray-800 bg-opacity-50 rounded-xl p-4 border border-gray-600">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <div className="text-2xl">{getPropertyTypeIcon(house.type)}</div>
                        <div>
                          <div className="text-white font-medium">{house.name}</div>
                          <div className="text-gray-400 text-sm">{house.address}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-red-400 font-bold">${house.monthly_bills.toFixed(2)}</div>
                        <div className="text-gray-400 text-sm">Monthly Bills</div>
                      </div>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        house.status === 'occupied' ? 'bg-green-900 text-green-400' : 'bg-orange-900 text-orange-400'
                      }`}>
                        {house.status}
                      </span>
                      <span className="text-gray-400">
                        {house.tenant_count === 0 ? 'No tenants' : `${house.tenant_count} tenant${house.tenant_count > 1 ? 's' : ''}`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
} 
