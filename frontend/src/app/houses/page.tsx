'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import { useToast } from '@/hooks/useToast';
import { ToastContainer } from '@/components/ui/Toast';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { handleApiError, shouldRedirectToLogin } from '@/lib/errorHandler';
import { jwtDecode } from 'jwt-decode';
import { 
  getHouses, 
  addHouse, 
  deleteHouse, 
  updateHouse,
  calculatePortfolioTotals, 
  type House,
  getProviders,
  type Provider
} from '@/lib/housesData';

interface AddHouseModal {
  isOpen: boolean;
  editingHouse?: House;
}

interface DecodedToken {
  sub: string;
  exp: number;
}

interface TenantManagementModal {
  isOpen: boolean;
  house: House | null;
  tenantCount: number;
}

export default function HousesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  
  const [houses, setHouses] = useState<House[]>([]);
  const [loading, setLoading] = useState(true);
  const [addHouseModal, setAddHouseModal] = useState<AddHouseModal>({ isOpen: false });
  const [tenantModal, setTenantModal] = useState<TenantManagementModal>({ 
    isOpen: false, 
    house: null, 
    tenantCount: 0 
  });
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    isOpen: boolean;
    houseId: string | null;
    houseName: string;
  }>({ isOpen: false, houseId: null, houseName: '' });
  const [newHouse, setNewHouse] = useState({
    name: '',
    address: '',
    type: 'single_family' as const,
    bedrooms: 1,
    bathrooms: 1,
    sqft: '',
    monthly_rent: '',
    tenant_count: 0,
  });
  const [providers, setProviders] = useState<Provider[]>([]);

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

  const redirectToLogin = () => {
    localStorage.removeItem('auth_token');
    router.push('/login');
  };

  // Load houses from centralized data management
  const loadHouses = () => {
    try {
      const housesData = getHouses();
      setHouses(housesData);
      setLoading(false);
    } catch (error) {
      console.error('Error loading houses:', error);
      toast.error('Error', 'Failed to load properties data.');
      setLoading(false);
    }
  };

  // Listen for data updates from other components
  useEffect(() => {
    loadHouses();

    // Listen for houses data updates
    const handleHousesUpdated = (event: CustomEvent) => {
      setHouses(event.detail);
    };

    // Listen for active house clearing
    const handleActiveHouseCleared = () => {
      // The Layout component will handle this via event listener
      // No need to force a reload
    };

    window.addEventListener('houses-updated', handleHousesUpdated as EventListener);
    window.addEventListener('active-house-cleared', handleActiveHouseCleared);

    return () => {
      window.removeEventListener('houses-updated', handleHousesUpdated as EventListener);
      window.removeEventListener('active-house-cleared', handleActiveHouseCleared);
    };
  }, [userId]);

  useEffect(() => {
    setProviders(getProviders());
  }, []);

  // Helper to calculate total bills for a house (current month only, matching Bill Analysis)
  const getTotalBillsForHouse = (houseId: string) => {
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();
    const houseProviders = providers.filter((p) => p.house_id === houseId);
    return houseProviders.reduce((sum, p) => {
      if (p.latest_bill && p.latest_bill.amount && p.latest_bill.date) {
        const billDate = new Date(p.latest_bill.date);
        if (billDate.getMonth() === currentMonth && billDate.getFullYear() === currentYear) {
          const amt = parseFloat(String(p.latest_bill.amount).replace(/[$,]/g, ''));
          return sum + (isNaN(amt) ? 0 : amt);
        }
      }
      return sum;
    }, 0);
  };

  const formatAmount = (amount: number) => `$${amount.toFixed(2)}`;

  const getHouseTypeIcon = (type: string) => {
    switch (type) {
      case 'single_family':
        return '🏠';
      case 'duplex':
        return '🏘️';
      case 'apartment':
        return '🏢';
      case 'condo':
        return '🏗️';
      case 'townhouse':
        return '🏘️';
      default:
        return '🏠';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'occupied':
        return 'bg-green-900 text-green-400 border-green-600';
      case 'vacant':
        return 'bg-orange-900 text-orange-400 border-orange-600';
      case 'maintenance':
        return 'bg-red-900 text-red-400 border-red-600';
      default:
        return 'bg-gray-900 text-gray-400 border-gray-600';
    }
  };

  const handleAddHouse = () => {
    setNewHouse({
      name: '',
      address: '',
      type: 'single_family',
      bedrooms: 1,
      bathrooms: 1,
      sqft: '',
      monthly_rent: '',
      tenant_count: 0,
    });
    setAddHouseModal({ isOpen: true });
  };

  const handleSaveHouse = () => {
    // Validate form
    if (!newHouse.name || !newHouse.address || !newHouse.monthly_rent) {
      toast.warning('Missing Information', 'Please fill in all required fields.');
      return;
    }

    try {
      // Automatically determine status based on tenant count
      const status: 'occupied' | 'vacant' | 'maintenance' = newHouse.tenant_count > 0 ? 'occupied' : 'vacant';
      
      const house: House = {
        id: Date.now().toString(),
        name: newHouse.name,
        address: newHouse.address,
        type: newHouse.type,
        bedrooms: newHouse.bedrooms,
        bathrooms: newHouse.bathrooms,
        sqft: newHouse.sqft ? parseInt(newHouse.sqft) : undefined,
        monthly_rent: parseFloat(newHouse.monthly_rent),
        status: status,
        tenant_count: newHouse.tenant_count,
        monthly_bills: 0,
        created_at: new Date().toISOString()
      };

      const updatedHouses = addHouse(house);
      setHouses(updatedHouses);
      setAddHouseModal({ isOpen: false });
      
      const statusMessage = newHouse.tenant_count > 0 ? 'occupied' : 'vacant';
      toast.success(
        'Property Added',
        `${newHouse.name} has been successfully added to your portfolio as ${statusMessage}.`
      );
    } catch (error) {
      console.error('Error adding house:', error);
      toast.error('Error', 'Failed to add property. Please try again.');
    }
  };

  const confirmDelete = () => {
    if (!deleteConfirmation.houseId) return;
    
    try {
      const updatedHouses = deleteHouse(deleteConfirmation.houseId);
      setHouses(updatedHouses);
      
      toast.success(
        'Property Deleted',
        `${deleteConfirmation.houseName} has been permanently removed from your portfolio.`
      );
      
      setDeleteConfirmation({ isOpen: false, houseId: null, houseName: '' });
    } catch (error) {
      console.error('Error deleting house:', error);
      toast.error('Error', 'Failed to delete property. Please try again.');
    }
  };

  // Calculate totals using the centralized function
  const totals = calculatePortfolioTotals();

  const getOccupancyDisplay = (house: House) => {
    if (house.tenant_count === 0) {
      return 'No tenants';
    }
    
    // Show tenant ratio (e.g., "1/4" for 1 tenant in 4 bedroom property)
    const ratio = `${house.tenant_count}/${house.bedrooms}`;
    const plural = house.tenant_count > 1 ? 's' : '';
    return `${house.tenant_count} tenant${plural} (${ratio})`;
  };

  const handleOpenTenantModal = (house: House) => {
    setTenantModal({
      isOpen: true,
      house: house,
      tenantCount: house.tenant_count
    });
  };

  const handleSaveTenantCount = () => {
    if (!tenantModal.house) return;

    try {
      // Determine new status based on tenant count
      const newStatus: 'occupied' | 'vacant' | 'maintenance' = tenantModal.tenantCount > 0 ? 'occupied' : 'vacant';
      
      // Use the centralized updateHouse function
      const updatedHouses = updateHouse(tenantModal.house.id, {
        tenant_count: tenantModal.tenantCount,
        status: newStatus
      });
      
      // Update local state
      setHouses(updatedHouses);
      
      // Close modal
      setTenantModal({ isOpen: false, house: null, tenantCount: 0 });
      
      const statusMessage = tenantModal.tenantCount > 0 ? 'occupied' : 'vacant';
      toast.success(
        'Tenants Updated',
        `${tenantModal.house.name} is now ${statusMessage} with ${tenantModal.tenantCount} tenant${tenantModal.tenantCount !== 1 ? 's' : ''}.`
      );
    } catch (error) {
      console.error('Error updating tenant count:', error);
      toast.error('Error', 'Failed to update tenant count. Please try again.');
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500 mx-auto"></div>
            <p className="mt-4 text-white">Loading properties...</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-4xl font-bold text-white drop-shadow-lg">Property Portfolio</h1>
            <p className="text-gray-200 drop-shadow">
              Manage your rental properties and their utilities
            </p>
          </div>
          <button
            onClick={handleAddHouse}
            className="bg-pink-600 hover:bg-pink-500 text-white px-6 py-3 rounded-xl transition duration-200 font-medium flex items-center space-x-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Add Property</span>
          </button>
        </div>

        {/* Properties Grid */}
        {houses.length === 0 ? (
          <div className="text-center py-16">
            <div className="bg-gray-900 bg-opacity-50 backdrop-blur-md border border-gray-700 rounded-3xl p-12">
              <div className="text-6xl mb-6">🏠</div>
              <h3 className="text-2xl font-bold text-white mb-4">No properties yet</h3>
              <p className="text-gray-300 mb-8">Add your first rental property to get started with utility management</p>
              <button
                onClick={handleAddHouse}
                className="bg-pink-600 hover:bg-pink-500 text-white px-8 py-4 rounded-xl transition duration-200 font-bold"
              >
                Add Your First Property
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {houses.map((house) => (
              <div key={house.id} className="relative bg-gray-900 border border-gray-700 rounded-3xl overflow-hidden shadow-2xl hover:border-pink-500 transition-all duration-300 group">
                {/* House Image Placeholder */}
                <div className="h-48 bg-gradient-to-br from-gray-800 to-gray-700 flex items-center justify-center">
                  <div className="text-6xl group-hover:scale-110 transition-transform duration-300">
                    {getHouseTypeIcon(house.type)}
                  </div>
                </div>

                {/* Delete button icon */}
                <button
                  onClick={() => setDeleteConfirmation({ isOpen: true, houseId: house.id, houseName: house.name })}
                  className="absolute top-4 right-4 bg-red-600 hover:bg-red-500 text-white rounded-full p-2 transition-all duration-200 hover:scale-110 hover:shadow-lg shadow-red-500/20 group"
                  title="Delete Property"
                >
                  <svg 
                    className="w-4 h-4 group-hover:scale-110 transition-transform duration-200" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" 
                    />
                  </svg>
                </button>

                {/* House Details */}
                <div className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-xl font-bold text-white mb-1">{house.name}</h3>
                      <p className="text-gray-400 text-sm">{house.address}</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${getStatusColor(house.status)}`}>
                      {house.status.charAt(0).toUpperCase() + house.status.slice(1)}
                    </span>
                  </div>

                  {/* Property Stats */}
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="text-center">
                      <div className="text-lg font-bold text-white">{house.bedrooms}bd/{house.bathrooms}ba</div>
                      <div className="text-xs text-gray-400">Bedrooms/Baths</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-white">{house.sqft ? `${house.sqft.toLocaleString()}` : 'N/A'}</div>
                      <div className="text-xs text-gray-400">Square Feet</div>
                    </div>
                  </div>

                  {/* Monthly Bills & Tenants */}
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-2">
                      <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                      </svg>
                      <span className="text-gray-400 text-sm">
                        {getOccupancyDisplay(house)}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-pink-400">{formatAmount(getTotalBillsForHouse(house.id))}</div>
                      <div className="text-xs text-gray-400">Monthly Bills</div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-3">
                    <button
                      onClick={() => router.push(`/property/${house.id}?user_id=${userId}`)}
                      className="w-full bg-pink-600 hover:bg-pink-500 text-white px-4 py-3 rounded-xl transition duration-200 font-medium"
                    >
                      🏠 Property Details
                    </button>
                    <div className="grid grid-cols-1 gap-3">
                      <button
                        onClick={() => handleOpenTenantModal(house)}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition duration-200 text-sm"
                      >
                        👥 Add Tenants
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add House Modal */}
        {addHouseModal.isOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-75 overflow-y-auto h-full w-full z-50">
            <div className="relative top-10 mx-auto p-6 border border-gray-600 max-w-2xl shadow-2xl rounded-2xl bg-gray-900">
              <div className="mb-6">
                <h3 className="text-2xl font-bold text-white mb-2">Add New Property</h3>
                <p className="text-gray-400">Enter the details for your rental property</p>
              </div>
              
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Property Name *</label>
                    <input
                      type="text"
                      value={newHouse.name}
                      onChange={(e) => setNewHouse(prev => ({ ...prev, name: e.target.value }))}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                      placeholder="e.g., Downtown Duplex"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Property Type</label>
                    <select
                      value={newHouse.type}
                      onChange={(e) => setNewHouse(prev => ({ ...prev, type: e.target.value as any }))}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    >
                      <option value="single_family">Single Family Home</option>
                      <option value="duplex">Duplex</option>
                      <option value="apartment">Apartment</option>
                      <option value="condo">Condominium</option>
                      <option value="townhouse">Townhouse</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Address *</label>
                  <input
                    type="text"
                    value={newHouse.address}
                    onChange={(e) => setNewHouse(prev => ({ ...prev, address: e.target.value }))}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="123 Main St, City, State 12345"
                  />
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Bedrooms</label>
                    <input
                      type="number"
                      min="1"
                      value={newHouse.bedrooms}
                      onChange={(e) => setNewHouse(prev => ({ ...prev, bedrooms: parseInt(e.target.value) || 1 }))}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Bathrooms</label>
                    <input
                      type="number"
                      min="1"
                      step="0.5"
                      value={newHouse.bathrooms}
                      onChange={(e) => setNewHouse(prev => ({ ...prev, bathrooms: parseFloat(e.target.value) || 1 }))}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Square Feet</label>
                    <input
                      type="number"
                      value={newHouse.sqft}
                      onChange={(e) => setNewHouse(prev => ({ ...prev, sqft: e.target.value }))}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                      placeholder="1200"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Monthly Rent *</label>
                    <input
                      type="number"
                      value={newHouse.monthly_rent}
                      onChange={(e) => setNewHouse(prev => ({ ...prev, monthly_rent: e.target.value }))}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                      placeholder="2500"
                    />
                  </div>
                </div>

                {/* Tenant Management Section */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                  <h4 className="text-lg font-semibold text-white mb-4 flex items-center">
                    <svg className="w-5 h-5 mr-2 text-pink-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                    </svg>
                    Tenant Management
                  </h4>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">Number of Tenants</label>
                      <input
                        type="number"
                        min="0"
                        max={newHouse.bedrooms}
                        value={newHouse.tenant_count}
                        onChange={(e) => setNewHouse(prev => ({ ...prev, tenant_count: parseInt(e.target.value) || 0 }))}
                        className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        Max: {newHouse.bedrooms} tenants ({newHouse.bedrooms} bedrooms)
                      </p>
                    </div>
                    
                    <div className="flex items-center">
                      <div className="bg-gray-700 rounded-xl p-4 w-full">
                        <div className="text-sm text-gray-400">Status Preview</div>
                        <div className="flex items-center space-x-2 mt-2">
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${
                            newHouse.tenant_count > 0 
                              ? 'bg-green-900 text-green-400 border-green-600' 
                              : 'bg-orange-900 text-orange-400 border-orange-600'
                          }`}>
                            {newHouse.tenant_count > 0 ? 'Occupied' : 'Vacant'}
                          </span>
                          {newHouse.tenant_count > 0 && (
                            <span className="text-gray-300 text-sm">
                              {newHouse.tenant_count}/{newHouse.bedrooms} capacity
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex space-x-4 mt-8">
                <button
                  onClick={handleSaveHouse}
                  className="bg-pink-600 hover:bg-pink-500 text-white px-6 py-3 rounded-xl transition duration-200 flex-1 font-bold"
                >
                  Add Property
                </button>
                <button
                  onClick={() => setAddHouseModal({ isOpen: false })}
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
          title="Delete Property"
          message={`Are you sure you want to delete "${deleteConfirmation.houseName}"? This will also delete all associated utilities, bills, and tenant data. This action cannot be undone.`}
          confirmText="Delete Property"
          cancelText="Cancel"
          type="danger"
          onConfirm={confirmDelete}
          onCancel={() => setDeleteConfirmation({ isOpen: false, houseId: null, houseName: '' })}
        />

        {/* Tenant Management Modal */}
        {tenantModal.isOpen && tenantModal.house && (
          <div className="fixed inset-0 bg-black bg-opacity-75 overflow-y-auto h-full w-full z-50">
            <div className="relative top-10 mx-auto p-6 border border-gray-600 max-w-md shadow-2xl rounded-2xl bg-gray-900">
              <div className="mb-6">
                <h3 className="text-2xl font-bold text-white mb-2 flex items-center">
                  <svg className="w-6 h-6 mr-2 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                  </svg>
                  Manage Tenants
                </h3>
                <p className="text-gray-400">Update tenant count for {tenantModal.house.name}</p>
              </div>
              
              <div className="space-y-6">
                {/* Property Info */}
                <div className="bg-gray-800 rounded-xl p-4">
                  <div className="text-sm text-gray-400 mb-2">Property Details</div>
                  <div className="text-white font-medium">{tenantModal.house.name}</div>
                  <div className="text-gray-300 text-sm">{tenantModal.house.bedrooms} bedrooms • {tenantModal.house.bathrooms} bathrooms</div>
                  <div className="text-gray-400 text-xs mt-1">Maximum capacity: {tenantModal.house.bedrooms} tenants</div>
                </div>

                {/* Tenant Count Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Number of Tenants</label>
                  <input
                    type="number"
                    min="0"
                    max={tenantModal.house.bedrooms}
                    value={tenantModal.tenantCount}
                    onChange={(e) => setTenantModal(prev => ({ ...prev, tenantCount: parseInt(e.target.value) || 0 }))}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                {/* Status Preview */}
                <div className="bg-gray-800 rounded-xl p-4">
                  <div className="text-sm text-gray-400 mb-2">Status Preview</div>
                  <div className="flex items-center space-x-2">
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${
                      tenantModal.tenantCount > 0 
                        ? 'bg-green-900 text-green-400 border-green-600' 
                        : 'bg-orange-900 text-orange-400 border-orange-600'
                    }`}>
                      {tenantModal.tenantCount > 0 ? 'Occupied' : 'Vacant'}
                    </span>
                    {tenantModal.tenantCount > 0 && (
                      <span className="text-gray-300 text-sm">
                        {tenantModal.tenantCount}/{tenantModal.house.bedrooms} capacity
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex space-x-4 mt-8">
                <button
                  onClick={handleSaveTenantCount}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl transition duration-200 flex-1 font-bold"
                >
                  Update Tenants
                </button>
                <button
                  onClick={() => setTenantModal({ isOpen: false, house: null, tenantCount: 0 })}
                  className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-6 py-3 rounded-xl transition duration-200 font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
      </div>
    </Layout>
  );
} 