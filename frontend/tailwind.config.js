/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1f2a37',
        amber: {
          DEFAULT: '#C8942A',
          dark: '#a87a1f',
        },
        neutralbg: '#f6f5f2',
      },
    },
  },
  plugins: [],
};
