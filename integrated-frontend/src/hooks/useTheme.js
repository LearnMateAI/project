/**
 * Light/dark theme state.
 *
 * The theme itself is one class on <html>; everything visual follows from the token
 * overrides in index.css. So this hook is deliberately small: it owns *which* class is on
 * the element and where that choice is remembered, and nothing about how anything looks.
 *
 * The first application does not happen here. It happens in the inline script in
 * index.html, which runs before the first paint -- React mounts a beat later, and doing it
 * here would show a dark-theme user one white frame on every page load. This hook reads
 * the class that script already set, so the two cannot disagree on startup.
 */

import { useCallback, useEffect, useState } from "react";

// Shared with the inline script in index.html. If this string changes, change it there
// too, or a returning user's saved choice is silently ignored on the next load.
const STORAGE_KEY = "learnmate-theme";

const QUERY = "(prefers-color-scheme: dark)";

/** localStorage throws in Safari private mode rather than returning null. */
function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function useTheme() {
  const [theme, setTheme] = useState(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // Until the user makes a choice, the OS is the choice -- so a system switch at dusk is
  // followed live rather than only on the next reload. Once they have picked, this stops:
  // an explicit preference outranks the system one, which is why the stored value is
  // checked here rather than only when reading the initial state.
  useEffect(() => {
    if (readStored()) return undefined;
    const media = window.matchMedia(QUERY);
    const onChange = (event) => setTheme(event.matches ? "dark" : "light");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Private mode: the theme still switches for this session, it just will not be
        // remembered. Failing the toggle over a storage quota would be the worse trade.
      }
      return next;
    });
  }, []);

  return { theme, toggle, isDark: theme === "dark" };
}
