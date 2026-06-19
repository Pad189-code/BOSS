import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        boss: {
          primary: "#0f172a",
          accent: "#2563eb",
          muted: "#64748b",
          surface: "#f8fafc",
          border: "#e2e8f0",
        },
      },
    },
  },
  plugins: [],
};

export default config;
