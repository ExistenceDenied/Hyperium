/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        brand: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
        },
      },
      fontFamily: {
        // Inter is the Hyperium corporate typeface; Arial/sans-serif is the
        // technical fallback only.
        sans: ['Inter', 'Arial', 'sans-serif'],
      },
      keyframes: {
        'slide-in-left': { from: { transform: 'translateX(-100%)' }, to: { transform: 'translateX(0)' } },
        'slide-in-right': { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'rise-in': { from: { opacity: '0', transform: 'translateY(4px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
      animation: {
        'slide-in-left': 'slide-in-left .2s ease-out',
        'slide-in-right': 'slide-in-right .22s cubic-bezier(0.16,1,0.3,1)',
        'fade-in': 'fade-in .15s ease-out',
        'rise-in': 'rise-in .2s ease-out',
      },
    },
  },
  plugins: [],
}
