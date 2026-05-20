/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1117",
          card: "#1a1d27",
          hover: "#22263a",
          border: "#2a2d3e",
        },
        accent: {
          DEFAULT: "#6366f1",
          hover: "#4f51cc",
        },
      },
    },
  },
  plugins: [],
};
