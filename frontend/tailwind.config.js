/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        faculty: ['"Faculty Glyphic"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        'lookup-rise': {
          '0%': { transform: 'translateY(4px)', opacity: '0' },
          '12%': { opacity: '0.5' },
          '78%': { opacity: '0.25' },
          '100%': { transform: 'translateY(-20px)', opacity: '0' },
        },
        'lookup-drift': {
          '0%, 100%': { transform: 'translateX(0)' },
          '50%': { transform: 'translateX(6px)' },
        },
      },
      animation: {
        'lookup-rise': 'lookup-rise 2.4s ease-in-out infinite',
        'lookup-drift': 'lookup-drift 3s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
