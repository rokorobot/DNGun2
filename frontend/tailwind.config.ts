import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18211f",
        panel: "#f7f7f3",
        line: "#d8ddd5",
        moss: "#476454",
        rust: "#a85732",
        blue: "#2d5d7b"
      }
    }
  },
  plugins: []
};

export default config;
