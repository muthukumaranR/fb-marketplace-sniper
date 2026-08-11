import type { Theme } from "../hooks/useTheme";

interface Props {
  theme: Theme;
  onToggle: () => void;
}

export default function ThemeToggle({ theme, onToggle }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="flex h-8 w-8 items-center justify-center rounded-[7px] border border-line bg-surface text-[13px] text-fg2 transition-colors duration-150 hover:border-line-hover hover:text-fg"
    >
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}
