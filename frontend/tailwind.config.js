/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        white: 'var(--soft-white)',
        // Light mode: mapped to CSS variables
        light: {
          bg: 'var(--bg)',
          surface: 'var(--surface)',
          elevated: 'var(--elevated)',
          border: 'var(--border)',
          text: 'var(--text)',
          'text-muted': 'var(--text-muted)',
          'text-soft': 'var(--text-soft)',
          accent: 'var(--accent)',
          'accent-hover': 'var(--accent-hover)',
          link: 'var(--link)',
        },
        // Dark mode: mapped to CSS variables
        dark: {
          bg: 'var(--bg)',
          surface: 'var(--surface)',
          elevated: 'var(--elevated)',
          border: 'var(--border)',
          text: 'var(--text)',
          'text-muted': 'var(--text-muted)',
          'text-soft': 'var(--text-soft)',
          accent: 'var(--accent)',
          'accent-hover': 'var(--accent-hover)',
          link: 'var(--link)',
        },
        sepia: {
          bg: 'var(--bg)',
          surface: 'var(--surface)',
          text: 'var(--text)',
          accent: 'var(--accent)',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        serif: ['"Source Serif Pro"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Reader sizes (configurable)
        'reader-xs': ['14px', { lineHeight: '1.5' }],
        'reader-sm': ['16px', { lineHeight: '1.6' }],
        'reader-base': ['18px', { lineHeight: '1.7' }],
        'reader-lg': ['20px', { lineHeight: '1.8' }],
        'reader-xl': ['24px', { lineHeight: '1.9' }],
        'reader-2xl': ['28px', { lineHeight: '2.0' }],
      },
      boxShadow: {
        'soft': '0 1px 2px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.04)',
        'elevated': '0 4px 12px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06)',
      },
      borderRadius: {
        'sm': '4px',
        'md': '6px',
        'lg': '8px',
        'xl': '12px',
        '2xl': '16px',
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 300ms ease-out',
        'slide-down': 'slideDown 200ms ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/typography')]
};
