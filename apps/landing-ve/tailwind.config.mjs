/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx,vue,svelte}'],
  theme: {
    extend: {
      colors: {
        've-bg':          '#0a0612',
        've-surface':     '#140a23',
        've-border':      '#2a1840',
        've-text':        '#f4f1ff',
        've-muted':       '#8a7ba8',
        've-purple':      '#7c3aed',
        've-purple-deep': '#5b21b6',
        've-purple-soft': '#a78bfa',
        've-purple-pale': '#ede9fe',
        'cat-t1': '#00ffcc',
        'cat-t2': '#3b82f6',
        'cat-t3': '#f59e0b',
        'cat-t4': '#ec4899',
        'cat-t5': '#06b6d4',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
