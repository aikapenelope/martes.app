/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'sys-bg':       '#0a0a0a',
        'sys-surface':  '#111111',
        'sys-border':   '#222222',
        'sys-text':     '#e0e0e0',
        'sys-muted':    '#666666',
        'sys-accent-1': '#00ffcc',
        'sys-accent-2': '#b026ff',
        'sys-accent-3': '#ff3366',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['Inter', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-glow': 'conic-gradient(from 180deg at 50% 50%, #b026ff55 0deg, #00ffcc55 180deg, #b026ff55 360deg)',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        float:        'float 6s ease-in-out infinite',
        scanline:     'scanline 8s linear infinite',
      },
      keyframes: {
        float:    { '0%, 100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-20px)' } },
        scanline: { '0%': { transform: 'translateY(-100%)' }, '100%': { transform: 'translateY(100vh)' } },
      },
    },
  },
  plugins: [],
};
