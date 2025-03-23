/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      "./src/**/*.{js,jsx,ts,tsx}",
      "./public/index.html"
    ],
    theme: {
      extend: {
        colors: {
          gray: {
            900: '#121218', // primary-bg
            800: '#1e1e26', // secondary-bg
            700: '#282836', // tertiary-bg
          },
          purple: {
            600: '#9d4edd', // accent-purple
          },
          pink: {
            500: '#ff5baa', // accent-pink 
          },
          blue: {
            400: '#3db4f2', // accent-blue
          },
        },
        borderRadius: {
          'full': '9999px',
        },
        boxShadow: {
          md: '0 4px 12px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    plugins: [],
  }