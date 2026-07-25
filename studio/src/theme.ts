/* Light and dark, remembered.
 *
 * Both themes are in the stylesheet — the tokens flip on `data-theme` at the
 * root — so this is only the switch and the memory. Read BEFORE first paint so
 * a light-theme user does not get a dark flash on every load.
 */
const KEY = "mb-theme";           // the key the previous studio used: switching
                                  // names would silently reset everyone's choice

export type Theme = "dark" | "light";

export function currentTheme(): Theme {
  return localStorage.getItem(KEY) === "light" ? "light" : "dark";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(KEY, theme);
}

export function toggleTheme(): Theme {
  const next: Theme = currentTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
