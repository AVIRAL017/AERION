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
          DEFAULT: '#0B0F14',
          surface: '#0B0F14',
          container: '#11161D',
          elevated: '#171D25',
          subtle: '#1F2630',
        },
        panel: "#11161D",
        elevated: "#171D25",
        subtle: "#1F2630",
        accent: {
          DEFAULT: '#38D5F5',
          muted: 'rgba(56, 213, 245, 0.12)',
        },
        status: {
          critical: '#EF5669',
          warning: '#E8B34A',
          success: '#48C995',
          ai: '#9A8BEF',
        },
        critical: '#EF5669',
        warning: '#E8B34A',
        success: '#48C995',
        ai: '#9A8BEF',
        muted: '#8D9CAE',
        faint: '#4C5868',
        paper: '#EDF2F7',
        content: '#EDF1F5',
      },
      fontFamily: {
        sans: ['Geist', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
