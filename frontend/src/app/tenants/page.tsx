'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import { useToast } from '@/hooks/useToast';
import { ToastContainer } from '@/components/ui/Toast';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { jwtDecode } from 'jwt-decode';
import { 
  getHouses, 
  getTenants,
  getTenantsByHouseId,
  addTenant,
  deleteTenant,
  type House, 
  type Tenant 
} from '@/lib/housesData';

interface DecodedToken {
  sub: string;
  exp: number;
}

interface AddTenantModal {
  isOpen: boolean;
  editingTenant?: Tenant;
}

export default function TenantsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  
  const [houses, setHouses] = useState<House[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedHouse, setSelectedHouse] = useState<House | null>(null);
  const [loading, setLoading] = useState(true);
  const [addTenantModal, setAddTenantModal] = useState<AddTenantModal>({ isOpen: false });
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    isOpen: boolean;
    tenantId: string | null;
    tenantName: string;
  }>({ isOpen: false, tenantId: null, tenantName: '' });
  const [newTenant, setNewTenant] = useState({
    name: '',
    email: '',
    payment_amount: '',
  });

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

  // Load data
  const loadData = () => {
    try {
      const housesData = getHouses();
      const tenantsData = getTenants();
      setHouses(housesData);
      setTenants(tenantsData);
      
      // Set the first house as selected by default, or from URL params
      const houseIdParam = searchParams.get('house_id');
      if (houseIdParam) {
        const house = housesData.find(h => h.id === houseIdParam);
        if (house) {
          setSelectedHouse(house);
        }
      } else if (housesData.length > 0) {
        setSelectedHouse(housesData[0]);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Error', 'Failed to load data.');
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Listen for data updates
    const handleHousesUpdated = (event: CustomEvent) => {
      setHouses(event.detail);
    };

    const handleTenantsUpdated = (event: CustomEvent) => {
      setTenants(event.detail);
    };

    window.addEventListener('houses-updated', handleHousesUpdated as EventListener);
    window.addEventListener('tenants-updated', handleTenantsUpdated as EventListener);

    return () => {
      window.removeEventListener('houses-updated', handleHousesUpdated as EventListener);
      window.removeEventListener('tenants-updated', handleTenantsUpdated as EventListener);
    };
  }, [userId]);

  const getHouseTypeIcon = (type: string) => {
    switch (type) {
      case 'single_family': return '🏠';
      case 'duplex': return '🏘️';
      case 'apartment': return '🏢';
      case 'condo': return '🏗️';
      case 'townhouse': return '🏘️';
      default: return '🏠';
    }
  };

  const handleAddTenant = () => {
    if (!selectedHouse) {
      toast.warning('No Property Selected', 'Please select a property first.');
      return;
    }

    setNewTenant({
      name: '',
      email: '',
      payment_amount: '',
    });
    setAddTenantModal({ isOpen: true });
  };

  const handleSaveTenant = () => {
    if (!selectedHouse) {
      toast.warning('No Property Selected', 'Please select a property first.');
      return;
    }

    // Validate form
    if (!newTenant.name || !newTenant.email || !newTenant.payment_amount) {
      toast.warning('Missing Information', 'Please fill in all required fields.');
      return;
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(newTenant.email)) {
      toast.warning('Invalid Email', 'Please enter a valid email address.');
      return;
    }

    // Validate payment amount
    const paymentAmount = parseFloat(newTenant.payment_amount);
    if (isNaN(paymentAmount) || paymentAmount <= 0) {
      toast.warning('Invalid Payment Amount', 'Please enter a valid payment amount.');
      return;
    }

    try {
      const tenant: Tenant = {
        id: Date.now().toString(),
        name: newTenant.name,
        email: newTenant.email,
        payment_amount: paymentAmount,
        house_id: selectedHouse.id,
        created_at: new Date().toISOString()
      };

      const updatedTenants = addTenant(tenant);
      setTenants(updatedTenants);
      setAddTenantModal({ isOpen: false });
      
      toast.success(
        'Tenant Added',
        `${newTenant.name} has been successfully added to ${selectedHouse.name}.`
      );
    } catch (error) {
      console.error('Error adding tenant:', error);
      toast.error('Error', 'Failed to add tenant. Please try again.');
    }
  };

  const confirmDeleteTenant = () => {
    if (!deleteConfirmation.tenantId) return;
    
    try {
      const updatedTenants = deleteTenant(deleteConfirmation.tenantId);
      setTenants(updatedTenants);
      
      toast.success(
        'Tenant Removed',
        `${deleteConfirmation.tenantName} has been removed from the property.`
      );
      
      setDeleteConfirmation({ isOpen: false, tenantId: null, tenantName: '' });
    } catch (error) {
      console.error('Error deleting tenant:', error);
      toast.error('Error', 'Failed to remove tenant. Please try again.');
    }
  };

  const houseTenants = selectedHouse ? getTenantsByHouseId(selectedHouse.id) : [];
  const totalPayments = houseTenants.reduce((sum, tenant) => sum + tenant.payment_amount, 0);

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500 mx-auto"></div>
            <p className="mt-4 text-white">Loading tenants...</p>
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
              Please log in to view tenants
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
          <h1 className="text-4xl font-bold text-white drop-shadow-lg">Tenant Management</h1>
          <p className="text-gray-200 drop-shadow">
            Manage tenants across your rental properties
          </p>
        </div>

        {houses.length === 0 ? (
          <div className="text-center py-16">
            <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-3xl p-12">
              <div className="text-6xl mb-6">🏠</div>
              <h3 className="text-2xl font-bold text-white mb-4">No properties found</h3>
              <p className="text-gray-300 mb-8">Add properties first to manage tenants</p>
              <button
                onClick={() => router.push(`/houses?user_id=${userId}`)}
                className="bg-pink-600 hover:bg-pink-500 text-white px-8 py-4 rounded-xl transition duration-200 font-bold"
              >
                Go to Properties
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Property Selector */}
            <div className="lg:col-span-1">
              <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-2xl p-6 shadow-2xl">
                <h2 className="text-xl font-bold text-white mb-4">Select Property</h2>
                <div className="space-y-3">
                  {houses.map((house) => (
                    <button
                      key={house.id}
                      onClick={() => setSelectedHouse(house)}
                      className={`w-full p-4 rounded-xl border-2 transition duration-200 text-left ${
                        selectedHouse?.id === house.id
                          ? 'border-pink-500 bg-pink-500 bg-opacity-20'
                          : 'border-gray-600 hover:border-gray-500 bg-gray-800 bg-opacity-50'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="text-2xl">{getHouseTypeIcon(house.type)}</div>
                        <div className="flex-1">
                          <div className="text-white font-medium">{house.name}</div>
                          <div className="text-gray-400 text-sm">{house.address}</div>
                          <div className="text-gray-400 text-xs mt-1">
                            {house.tenant_count} tenant{house.tenant_count !== 1 ? 's' : ''}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Tenant Management */}
            <div className="lg:col-span-2">
              {selectedHouse ? (
                <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-2xl p-6 shadow-2xl">
                  {/* Property Header */}
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-4">
                      <div className="text-3xl">{getHouseTypeIcon(selectedHouse.type)}</div>
                      <div>
                        <h2 className="text-2xl font-bold text-white">{selectedHouse.name}</h2>
                        <p className="text-gray-400">{selectedHouse.address}</p>
                      </div>
                    </div>
                    <button
                      onClick={handleAddTenant}
                      className="bg-pink-600 hover:bg-pink-500 text-white px-4 py-2 rounded-lg transition duration-200 font-medium flex items-center space-x-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      <span>Add Tenant</span>
                    </button>
                  </div>

                  {/* Property Stats */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-gray-800 bg-opacity-50 rounded-xl p-4 text-center">
                      <div className="text-lg font-bold text-white">{houseTenants.length}</div>
                      <div className="text-xs text-gray-400">Current Tenants</div>
                    </div>
                    <div className="bg-gray-800 bg-opacity-50 rounded-xl p-4 text-center">
                      <div className="text-lg font-bold text-white">{selectedHouse.bedrooms}</div>
                      <div className="text-xs text-gray-400">Max Capacity</div>
                    </div>
                    <div className="bg-gray-800 bg-opacity-50 rounded-xl p-4 text-center">
                      <div className="text-lg font-bold text-green-400">${totalPayments.toLocaleString()}</div>
                      <div className="text-xs text-gray-400">Total Payments</div>
                    </div>
                    <div className="bg-gray-800 bg-opacity-50 rounded-xl p-4 text-center">
                      <div className="text-lg font-bold text-blue-400">${selectedHouse.monthly_rent.toLocaleString()}</div>
                      <div className="text-xs text-gray-400">Monthly Rent</div>
                    </div>
                  </div>

                  {/* Tenants List */}
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-4">Tenants</h3>
                    {houseTenants.length === 0 ? (
                      <div className="text-center py-8">
                        <div className="text-4xl mb-4">👥</div>
                        <p className="text-gray-400 mb-4">No tenants added yet</p>
                        <button
                          onClick={handleAddTenant}
                          className="bg-pink-600 hover:bg-pink-500 text-white px-6 py-3 rounded-lg transition duration-200 font-medium"
                        >
                          Add First Tenant
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {houseTenants.map((tenant) => (
                          <div key={tenant.id} className="bg-gray-800 bg-opacity-50 rounded-xl p-4 border border-gray-600">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-4">
                                <div className="w-10 h-10 bg-pink-600 rounded-full flex items-center justify-center text-white font-bold">
                                  {tenant.name.charAt(0).toUpperCase()}
                                </div>
                                <div>
                                  <div className="text-white font-medium">{tenant.name}</div>
                                  <div className="text-gray-400 text-sm">{tenant.email}</div>
                                  <div className="text-green-400 text-sm font-medium">
                                    ${tenant.payment_amount.toLocaleString()}/month
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center space-x-2">
                                <span className="text-gray-500 text-xs">
                                  Added {new Date(tenant.created_at).toLocaleDateString()}
                                </span>
                                <button
                                  onClick={() => setDeleteConfirmation({ 
                                    isOpen: true, 
                                    tenantId: tenant.id, 
                                    tenantName: tenant.name 
                                  })}
                                  className="bg-red-600 hover:bg-red-500 text-white rounded-full p-2 transition-all duration-200 hover:scale-110"
                                  title="Remove Tenant"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-2xl p-12 shadow-2xl text-center">
                  <div className="text-4xl mb-4">🏠</div>
                  <h3 className="text-xl font-bold text-white mb-2">Select a Property</h3>
                  <p className="text-gray-400">Choose a property from the left to manage its tenants</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Add Tenant Modal */}
        {addTenantModal.isOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-75 overflow-y-auto h-full w-full z-50">
            <div className="relative top-10 mx-auto p-6 border border-gray-600 max-w-md shadow-2xl rounded-2xl bg-gray-900">
              <div className="mb-6">
                <h3 className="text-2xl font-bold text-white mb-2">Add New Tenant</h3>
                <p className="text-gray-400">Add a tenant to {selectedHouse?.name}</p>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Full Name *</label>
                  <input
                    type="text"
                    value={newTenant.name}
                    onChange={(e) => setNewTenant(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="John Smith"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Email Address *</label>
                  <input
                    type="email"
                    value={newTenant.email}
                    onChange={(e) => setNewTenant(prev => ({ ...prev, email: e.target.value }))}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="john.smith@email.com"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Monthly Payment Amount *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newTenant.payment_amount}
                    onChange={(e) => setNewTenant(prev => ({ ...prev, payment_amount: e.target.value }))}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="1200.00"
                  />
                </div>
              </div>

              <div className="flex space-x-4 mt-8">
                <button
                  onClick={handleSaveTenant}
                  className="bg-pink-600 hover:bg-pink-500 text-white px-6 py-3 rounded-xl transition duration-200 flex-1 font-bold"
                >
                  Add Tenant
                </button>
                <button
                  onClick={() => setAddTenantModal({ isOpen: false })}
                  className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-6 py-3 rounded-xl transition duration-200 font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        <ConfirmModal
          isOpen={deleteConfirmation.isOpen}
          title="Remove Tenant"
          message={`Are you sure you want to remove "${deleteConfirmation.tenantName}" from this property? This action cannot be undone.`}
          confirmText="Remove Tenant"
          cancelText="Cancel"
          type="danger"
          onConfirm={confirmDeleteTenant}
          onCancel={() => setDeleteConfirmation({ isOpen: false, tenantId: null, tenantName: '' })}
        />

        <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
      </div>
    </Layout>
  );
} 