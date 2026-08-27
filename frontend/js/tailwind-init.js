tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        /* Smart Convers – palette inspirée de smartconvers.com */
        smartconvers: {
          primary: "#0EA5E9",   /* Sky – CTA principal */
          primaryDark: "#0284C7",
          primaryLight: "#38BDF8",
          secondary: "#06B6D4", /* Cyan – accent */
          secondaryDark: "#0891B2",
          surface: "#FAFBFC",
          surfaceDark: "#0f172a",
          navy: "#0f172a",
          navyLight: "#1e293b",
        },
        brand: {
          primary: "#2E69FF",
          secondary: "#06B6D4",
          muted: "#64748b",
          success: "#059669",
          warning: "#d97706",
          error: "#dc2626",
        },
      },
      boxShadow: {
        soft: "0 4px 24px -4px rgba(15, 23, 42, 0.08), 0 2px 8px -2px rgba(15, 23, 42, 0.04)",
        card: "0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)",
        cardHover: "0 12px 32px -8px rgba(15, 23, 42, 0.12), 0 4px 12px -4px rgba(15, 23, 42, 0.06)",
        glow: "0 0 0 1px rgba(14, 165, 233, 0.2), 0 8px 24px -4px rgba(14, 165, 233, 0.25)",
        inner: "inset 0 1px 2px 0 rgba(0,0,0,0.04)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #0EA5E9 0%, #06B6D4 100%)",
        "brand-gradient-hover": "linear-gradient(135deg, #38BDF8 0%, #22D3EE 100%)",
        "mesh-light": "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(14, 165, 233, 0.08), transparent), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(6, 182, 212, 0.06), transparent)",
        "mesh-dark": "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(14, 165, 233, 0.12), transparent), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(6, 182, 212, 0.08), transparent)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.25rem",
        "4xl": "1.5rem",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.35s ease-out",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
};
