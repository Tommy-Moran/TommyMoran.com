/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#23456a', // Logo blue
        secondary: '#2a437a', // Logo gradient blue
        accent: '#e87722',  // An orange accent color
        background: '#f8fafc',
        text: '#334155',
      },
    },
  },
  plugins: [],
} 