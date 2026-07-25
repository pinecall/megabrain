/* Inline SVG, because an icon that 404s is worse than no icon.
 *
 * The engine ships one self-contained bundle: no sprite sheet to fetch, no
 * font, nothing that can arrive late or not at all behind a reverse proxy.
 * Built with createElementNS rather than innerHTML — SVG in an HTML string is
 * parsed in the wrong namespace and renders as nothing.
 */
const PATHS: Record<string, string> = {
  brain: "M12 3a3 3 0 0 0-3 3 3 3 0 0 0-2 5.2A3 3 0 0 0 9 17a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0 2-5.8A3 3 0 0 0 15 6a3 3 0 0 0-3-3z",
  search: "M11 4a7 7 0 1 0 4.2 12.6L20 21l1-1-4.8-4.8A7 7 0 0 0 11 4zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10z",
  plus: "M12 5v14M5 12h14",
  gear: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM4 12l-1.5-1 1-2.5 1.8.3M20 12l1.5-1-1-2.5-1.8.3M12 4l1-1.5h-2L12 4zm0 16l1 1.5h-2l1-1.5z",
  menu: "M4 7h16M4 12h16M4 17h16",
  chevron: "M9 6l6 6-6 6",
  file: "M6 3h8l4 4v14H6V3zm8 0v4h4",
  graph: "M6 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm12 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm-1 1.7L7 14m6-4.3L17 14",
  spark: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6z",
};

export function icon(name: keyof typeof PATHS | string, size = 15): SVGElement {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", PATHS[name] ?? PATHS["file"]!);
  svg.append(path);
  return svg;
}
