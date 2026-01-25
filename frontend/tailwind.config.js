/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Base colors - Dark terminal theme
        'terminal-dark': '#0f1419',
        'terminal-panel': '#1a1f2e',
        'terminal-border': '#2d3548',
        
        // Text colors
        'terminal-text': '#e6e8f0',
        'terminal-text-dim': '#8b92b0',
        
        // Accent colors
        'positive': '#10b981',
        'negative': '#ef4444',
        'neutral': '#3b82f6',
        'warning': '#f59e0b',
        'critical': '#dc2626',
        
        // Chart colors
        'chart-blue': '#60a5fa',
        'chart-purple': '#a78bfa',
        'chart-pink': '#f472b6',
        'chart-cyan': '#22d3ee',
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        'mono': ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
}
