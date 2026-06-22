/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx,vue,svelte}'],
  theme: {
    extend: {
      colors: {
        'sys-bg':      '#0a0a0a',
        'sys-surface': '#111111',
        'sys-border':  '#1a1a1a',
        'sys-text':    '#f0f6fc',
        'sys-muted':   '#8b949e',
        'sys-accent-1': '#00ffcc',
        'sys-accent-2': '#a855f7',
        'sys-accent-3': '#ec4899',
        'sys-accent-4': '#f59e0b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
