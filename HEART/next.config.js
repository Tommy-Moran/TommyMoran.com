/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: [],
  },
  // Configure the base path for the app to be /HEART
  basePath: '/HEART',
  // Environment variables that should be available to the client
  // Be careful not to expose sensitive information here
  env: {
    OPENAI_ASSISTANT_ID: process.env.OPENAI_ASSISTANT_ID,
    NEXT_PUBLIC_AUDIT_API_URL: process.env.NEXT_PUBLIC_AUDIT_API_URL || 'https://heart-audit-api.onrender.com',
  },
  // Server-side environment variables don't need to be explicitly listed here
  // OPENAI_API_KEY will remain server-side only
}

module.exports = nextConfig 