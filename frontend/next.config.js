// frontend/next.config.js

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  compiler: {
    styledComponents: true,
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
