import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/bills/:path*',
        destination: 'http://localhost:8000/bills/:path*',
      },
      {
        source: '/dashboard/:path*',
        destination: 'http://localhost:8000/dashboard/:path*',
      },
      {
        source: '/users/:path*',
        destination: 'http://localhost:8000/users/:path*',
      },
      {
        source: '/tenants/:path*',
        destination: 'http://localhost:8000/tenants/:path*',
      },
      {
        source: '/email/:path*',
        destination: 'http://localhost:8000/email/:path*',
      },
    ];
  },
};

export default nextConfig;
