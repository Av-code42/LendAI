/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f5ff",
          100: "#dfe9fe",
          200: "#c6d8fd",
          300: "#9fbdfb",
          400: "#7098f7",
          500: "#4a72f0",
          600: "#3352e3",
          700: "#2a3fc8",
          800: "#26379f",
          900: "#1b2760",
          950: "#0f1633",
        },
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5d9e2",
          300: "#b1b8c8",
          400: "#8690a8",
          500: "#66708c",
          600: "#515a73",
          700: "#42495d",
          800: "#2f3444",
          900: "#1c1f2a",
          950: "#111319",
        },
        success: {
          50: "#ecfdf5",
          100: "#d1fae5",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
        },
        warning: {
          50: "#fffbeb",
          100: "#fef3c7",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
        },
        danger: {
          50: "#fef2f2",
          100: "#fee2e2",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(17 19 25 / 0.04), 0 1px 6px -1px rgb(17 19 25 / 0.06)",
      },
    },
  },
  plugins: [],
};
