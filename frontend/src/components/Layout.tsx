'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

interface LayoutProps {
  children: React.ReactNode;
}

interface House {
  id: string;
  name: string;
  address: string;
  type: string;
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeHouse, setActiveHouse] = useState<House | null>(null);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const userId = searchParams.get('user_id');

  // Load active house from localStorage
  useEffect(() => {
    const savedHouse = localStorage.getItem('activeHouse');
    if (savedHouse) {
      try {
        setActiveHouse(JSON.parse(savedHouse));
      } catch (error) {
        console.error('Error parsing active house:', error);
      }
    }

    // Listen for active house being cleared when a house is deleted
    const handleActiveHouseCleared = () => {
      setActiveHouse(null);
    };

    window.addEventListener('active-house-cleared', handleActiveHouseCleared);

    return () => {
      window.removeEventListener('active-house-cleared', handleActiveHouseCleared);
    };
  }, []);

  const navigation = [
    { name: 'Dashboard', href: `/dashboard?user_id=${userId}`, icon: '📊', level: 0 },
    { name: 'Properties', href: `/houses?user_id=${userId}`, icon: '🏠', level: 0 },
    { name: 'Utilities & Bills', href: `/bills?user_id=${userId}`, icon: '💡', level: 1 },
    { name: 'Tenants', href: `/tenants?user_id=${userId}`, icon: '👥', level: 1 },
  ];

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('activeHouse');
    window.location.href = '/';
  };

  const clearActiveHouse = () => {
    localStorage.removeItem('activeHouse');
    setActiveHouse(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-gray-900 to-pink-900">
      {/* Header */}
      <header className="bg-black bg-opacity-40 backdrop-blur-md border-b border-gray-700 border-opacity-50 lg:fixed lg:w-full lg:z-10 lg:pl-64 shadow-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 rounded-md text-white hover:text-pink-400 hover:bg-gray-800 hover:bg-opacity-50 transition-colors"
              >
                <span className="sr-only">Open sidebar</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <Link href={`/dashboard?user_id=${userId}`} className="flex items-center">
                <span className="text-2xl font-bold text-white drop-shadow-lg">AutoBilling</span>
              </Link>
              
              {/* Active House Indicator */}
              {activeHouse && (
                <div className="hidden md:flex items-center space-x-2 bg-gray-800 bg-opacity-50 rounded-lg px-3 py-2 border border-gray-600">
                  <div className="text-lg">🏠</div>
                  <div>
                    <div className="text-white text-sm font-medium">{activeHouse.name}</div>
                    <div className="text-gray-400 text-xs">{activeHouse.address}</div>
                  </div>
                  <button
                    onClick={clearActiveHouse}
                    className="text-gray-400 hover:text-red-400 transition-colors"
                    title="Clear active house"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={handleLogout}
                className="text-white hover:text-pink-400 px-4 py-2 rounded-lg text-sm font-medium bg-gray-800 bg-opacity-50 hover:bg-pink-600 hover:bg-opacity-20 transition-all duration-200 backdrop-blur-sm"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <div className={`${sidebarOpen ? 'block' : 'hidden'} lg:block lg:w-64 lg:fixed lg:inset-y-0 lg:pt-16`}>
          <div className="h-full bg-black bg-opacity-40 backdrop-blur-md border-r border-gray-700 border-opacity-50">
            <nav className="mt-8 px-4">
              <div className="space-y-2">
              {navigation.map((item) => {
                const isActive = pathname === item.href.split('?')[0];
                  
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`${
                      isActive
                          ? 'bg-pink-600 bg-opacity-30 border-l-4 border-pink-400 text-white shadow-lg'
                          : 'border-l-4 border-transparent text-white hover:bg-gray-800 hover:bg-opacity-50 hover:text-pink-400 hover:border-pink-500'
                      } group flex items-center px-4 py-3 text-sm font-medium rounded-r-lg transition-all duration-200`}
                  >
                      <span className="mr-4 text-lg">{item.icon}</span>
                      <span className={`${item.level === 1 ? 'pl-4 text-sm' : ''}`}>{item.name}</span>
                  </Link>
                );
              })}
            </div>
              
              {/* Active House Card in Sidebar */}
              {activeHouse && (
                <div className="mt-6 px-4">
                  <div className="bg-gradient-to-r from-pink-600 to-pink-500 bg-opacity-20 rounded-xl p-4 border border-pink-500 border-opacity-30">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-pink-400 text-sm font-medium">Active Property</div>
                      <button
                        onClick={clearActiveHouse}
                        className="text-pink-300 hover:text-white transition-colors"
                        title="Clear selection"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <div className="text-white text-sm font-medium">{activeHouse.name}</div>
                    <div className="text-pink-200 text-xs">{activeHouse.address}</div>
                  </div>
                </div>
              )}
              
              {/* Sidebar decoration */}
              <div className="mt-6 px-4">
                <div className="bg-gradient-to-r from-gray-800 to-gray-700 bg-opacity-50 rounded-xl p-6 border border-gray-600 border-opacity-30">
                  <div className="text-gray-300 text-sm font-medium mb-2">✨ Multi-Property</div>
                  <div className="text-gray-400 text-xs">
                    Manage utilities across all your rental properties
                  </div>
                </div>
              </div>
          </nav>
          </div>
        </div>

        {/* Main content */}
        <div className="lg:pl-64 flex-1 lg:pt-16">
          <main>
            {children}
          </main>
        </div>
      </div>
      
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 z-20 bg-black bg-opacity-50"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
} 