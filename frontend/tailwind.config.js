/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["Fraunces", "Times New Roman", "serif"],
        sans: ["Geist", "system-ui", "-apple-system", "sans-serif"],
        mono: ["Geist Mono", "SF Mono", "ui-monospace", "monospace"],
      },
      colors: {
        brass: {
          DEFAULT: "hsl(var(--brass))",
          soft: "hsl(var(--brass-soft))",
          deep: "hsl(var(--brass-deep))",
        },
        moss: "hsl(var(--moss))",
        rust: "hsl(var(--rust))",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        hrv: {
          DEFAULT: "hsl(var(--hrv))",
          foreground: "hsl(var(--hrv-foreground))",
          muted: "hsl(var(--hrv-muted))",
        },
        sleep: {
          DEFAULT: "hsl(var(--sleep))",
          foreground: "hsl(var(--sleep-foreground))",
          muted: "hsl(var(--sleep-muted))",
        },
        heart: {
          DEFAULT: "hsl(var(--heart))",
          foreground: "hsl(var(--heart-foreground))",
          muted: "hsl(var(--heart-muted))",
        },
        steps: {
          DEFAULT: "hsl(var(--steps))",
          foreground: "hsl(var(--steps-foreground))",
          muted: "hsl(var(--steps-muted))",
        },
        stress: {
          DEFAULT: "hsl(var(--stress))",
          foreground: "hsl(var(--stress-foreground))",
          muted: "hsl(var(--stress-muted))",
        },
        weight: {
          DEFAULT: "hsl(var(--weight))",
          foreground: "hsl(var(--weight-foreground))",
          muted: "hsl(var(--weight-muted))",
        },
        workout: {
          DEFAULT: "hsl(var(--workout))",
          foreground: "hsl(var(--workout-foreground))",
          muted: "hsl(var(--workout-muted))",
        },
        whoop: {
          DEFAULT: "hsl(var(--whoop))",
          foreground: "hsl(var(--whoop-foreground))",
          muted: "hsl(var(--whoop-muted))",
        },
        "whoop-strain": {
          DEFAULT: "hsl(var(--whoop-strain))",
          foreground: "hsl(var(--whoop-strain-foreground))",
          muted: "hsl(var(--whoop-strain-muted))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "calc(var(--radius) + 4px)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "fade-in-up": "fade-in-up 0.3s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        shimmer: "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [],
};
