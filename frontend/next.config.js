// frontend/next.config.js

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  compiler: {
    styledComponents: true,
  },
  webpack: (config, { dev }) => {
    // On Windows, mixed drive-letter casing can poison filesystem cache keys
    // and cause React Client Manifest module lookup failures in dev mode.
    if (dev) {
      config.cache = false;
    }
    return config;
  },
  headers: async () => [
    {
      source: '/api/:path*',
      headers: [
        { key: 'Access-Control-Allow-Origin', value: '*' },
        { key: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, DELETE' },
        { key: 'Access-Control-Allow-Headers', value: 'Content-Type' },
      ],
    },
  ],
};

module.exports = nextConfig;
