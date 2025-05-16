#!/usr/bin/env node

/**
 * This script performs security checks before building the application for production
 * It ensures that sensitive information is not accidentally exposed
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Check if .env.local exists but .env.production doesn't
const envLocalPath = path.join(__dirname, '..', '.env.local');
const envProdPath = path.join(__dirname, '..', '.env.production');

console.log('🔒 Running pre-build security checks...');

// Ensure .env files are properly set up
if (fs.existsSync(envLocalPath) && !fs.existsSync(envProdPath)) {
  console.log('⚠️  Warning: You have a .env.local file but no .env.production file');
  console.log('   For production builds, consider creating a separate .env.production file');
  console.log('   with appropriate production settings.');
}

// Check for potential API key leaks in the codebase
console.log('🔍 Checking for potential API key leaks in code...');

try {
  // Look for potential API keys in source code
  const result = execSync('grep -r "sk-" --include="*.{js,ts,tsx,jsx}" src').toString();
  if (result) {
    console.error('❌ Error: Potential API key found in source code:');
    console.error(result);
    console.error('Please remove API keys from source code and use environment variables instead.');
    process.exit(1);
  }
} catch (error) {
  // grep returns exit code 1 if no matches, which is what we want
  if (error.status !== 1) {
    console.error('Error running security check:', error.message);
  } else {
    console.log('✅ No API keys found in source code');
  }
}

// Verify next.config.js doesn't expose API keys
console.log('🔍 Checking Next.js config for exposed secrets...');

try {
  const nextConfig = fs.readFileSync(path.join(__dirname, '..', 'next.config.js'), 'utf8');
  if (nextConfig.includes('OPENAI_API_KEY')) {
    console.error('❌ Error: OPENAI_API_KEY appears to be exposed in next.config.js');
    console.error('This would expose your API key to clients. Please remove it.');
    process.exit(1);
  } else {
    console.log('✅ No API keys exposed in Next.js config');
  }
} catch (error) {
  console.error('Error checking Next.js config:', error.message);
  process.exit(1);
}

// All checks passed, run the build
console.log('✅ Security checks passed');
console.log('🏗️  Building production application...');

try {
  execSync('npm run build', { stdio: 'inherit' });
  console.log('✅ Build completed successfully');
} catch (error) {
  console.error('❌ Build failed:', error.message);
  process.exit(1);
} 