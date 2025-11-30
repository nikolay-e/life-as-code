/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f0f4ff",
          100: "#e0e9fe",
          200: "#c7d6fd",
          300: "#a4bbfb",
          400: "#7f97f7",
          500: "#667eea",
          600: "#5165de",
          700: "#4352c4",
          800: "#38459e",
          900: "#333f7d",
        },
        accent: {
          500: "#764ba2",
        },
      },
    },
  },
  plugins: [],
};
