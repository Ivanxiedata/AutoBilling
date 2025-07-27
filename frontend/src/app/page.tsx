import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">AutoBilling</h1>
          <p className="text-gray-600 mb-8">Automated utility billing for landlords and roommates</p>
          
          <div className="space-y-4">
            <Link 
              href="/login" 
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-200 block text-center"
            >
              Login
            </Link>
            <Link 
              href="/register" 
              className="w-full bg-gray-200 text-gray-800 py-2 px-4 rounded-md hover:bg-gray-300 transition duration-200 block text-center"
            >
              Register
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
