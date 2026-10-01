/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        graphite: {
          DEFAULT: '#F8FAFC',
          surface: '#F8FAFC',
          container: '#FFFFFF',
          elevated: '#F1F5F9',
          subtle: '#E2E8F0',
        },
        canvas: '#F8FAFC',
        surface: '#FFFFFF',
        panel: '#FFFFFF',
        elevated: '#F1F5F9',
        subtle: '#F8FAFC',
        accent: {
          DEFAULT: '#0284C7',
          hover: '#0369A1',
          light: '#E0F2FE',
          muted: 'rgba(2, 132, 199, 0.08)',
          spatial: '#2563EB',
          cyan: '#0EA5E9',
        },
        status: {
          critical: '#DC2626',
          warning: '#D97706',
          success: '#16A34A',
          ai: '#7C3AED',
        },
        critical: '#DC2626',
        warning: '#D97706',
        success: '#16A34A',
        ai: '#7C3AED',
        muted: '#64748B',
        faint: '#94A3B8',
        paper: '#0F172A',
        content: '#1E293B',
        border: {
          DEFAULT: '#E2E8F0',
          subtle: '#F1F5F9',
          strong: '#CBD5E1',
        },
      },
      fontFamily: {
        sans: ['Geist', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 1px 2px -1px rgba(15, 23, 42, 0.04), 0 0 0 1px rgba(226, 232, 240, 0.8)',
        'card-hover': '0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04), 0 0 0 1px rgba(2, 132, 199, 0.25)',
        'card-3d': '0 20px 30px -10px rgba(15, 23, 42, 0.08), 0 10px 15px -5px rgba(15, 23, 42, 0.04), 0 0 0 1px rgba(226, 232, 240, 0.9)',
        'floating': '0 25px 50px -12px rgba(15, 23, 42, 0.15), 0 0 0 1px rgba(226, 232, 240, 0.8)',
        'inner-bevel': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.9)',
      },
    },
  },
  plugins: [],
};
