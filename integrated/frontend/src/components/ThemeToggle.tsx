import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const KEY = "contextswitch.theme";

export function ThemeToggle({ className }: { className?: string }) {
  const [dark, setDark] = useState(true);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem(KEY, next ? "dark" : "light"); } catch { /* storage unavailable */ }
  };

  return (
    <button onClick={toggle} className={className} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} title={dark ? "Light mode" : "Dark mode"}>
      {dark ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}
    </button>
  );
}
