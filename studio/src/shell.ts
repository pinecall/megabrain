/* The frame: rail on the left, topbar with the tabs, viewport under it.
 *
 * The markup mirrors the stylesheet's class names exactly, because the design
 * IS the stylesheet — rebuilding the DOM with different names would have meant
 * rewriting a design that already works, which is not an improvement.
 */
import type { Config, RepoEntry } from "./contracts.js";
import { el, fill } from "./dom.js";
import { icon } from "./icons.js";
import { currentTheme, toggleTheme } from "./theme.js";

export type TabName = "ask" | "brief" | "search" | "graph";

/* ASK first, and that ordering is the product's: it is the feature people come
 * for. Then the three in the order a reader actually needs them: BRIEF to
 * orient (what these files are and how they connect), SEARCH for the code
 * itself, GRAPH for the structure. Ask is built ON search — every walkthrough
 * is a retrieval the model then explains — and brief is that same retrieval
 * with the cards instead of the bodies. */
export const TABS: TabName[] = ["ask", "brief", "search", "graph"];

export interface Shell {
  viewport: HTMLElement;
  setRepos(entries: RepoEntry[], onPick: (entry: RepoEntry) => void): void;
  markRepo(path: string): void;
  setCrumb(text: string, detail?: string): void;
  setStale(summary: string): void;
  onTab(handler: (tab: TabName) => void): void;
  select(tab: TabName): void;
}

export function mountShell(host: HTMLElement, config: Config,
                           onIndex: () => void, onSettings: () => void): Shell {
  const rail = el("aside", { class: "rail" });
  const repos = el("div", { class: "rail-section" });
  const crumb = el("div", { class: "crumb mono" });
  const viewport = el("div", { class: "viewport" });
  const tabs = el("div", { class: "tabs" });
  let onTabPick: (tab: TabName) => void = () => {};

  const buttons = new Map<TabName, HTMLElement>();
  for (const name of TABS) {
    const button = el("button", { class: "tab" },
                      name[0]!.toUpperCase() + name.slice(1));
    button.addEventListener("click", () => onTabPick(name));
    buttons.set(name, button);
    tabs.append(button);
  }

  rail.append(brand(), repos, foot(config, onIndex, onSettings));
  const scrim = el("div", { class: "rail-scrim" });
  scrim.addEventListener("click", () => host.classList.remove("rail-open"));
  /* The topbar is `space-between` with exactly TWO children: everything you
   * navigate with on the left, the status chip on the right. Five direct
   * children spread across the bar instead, which is what left the tabs
   * floating away from the breadcrumb. */
  host.append(rail, scrim, el("div", { class: "main" },
    el("header", { class: "topbar" },
      el("div", { style: "display:flex;align-items:center;gap:14px;min-width:0;flex:1" },
         burger(host), crumb, el("div", { class: "divider" }), tabs),
      chip(config)),
    viewport));

  return {
    viewport,
    setRepos(entries, onPick) {
      fill(repos, el("div", { class: "rail-label" }, "REPOSITORIES"),
           ...entries.map((entry) => repoRow(entry, onPick)));
    },
    markRepo(path) {
      for (const row of Array.from(repos.querySelectorAll<HTMLElement>(".repo-row"))) {
        row.classList.toggle("active", row.dataset["path"] === path);
      }
    },
    setCrumb(text, detail) {
      fill(crumb, el("b", {}, text), ...(detail ? [` · ${detail}`] : []));
    },
    setStale(summary) {
      /* Appended to the breadcrumb rather than raised as a toast: it is a
       * FACT about what you are looking at, not an event that just happened,
       * and it should still be there in ten minutes. */
      crumb.append(el("span", { class: "index-tag chg", style: "margin-left:8px" },
                      summary));
    },
    onTab(handler) { onTabPick = handler; },
    select(tab) {
      for (const [name, button] of buttons) button.classList.toggle("active", name === tab);
    },
  };
}

function brand(): HTMLElement {
  return el("div", { class: "rail-brand" },
    el("div", { class: "logo" }, icon("brain")),
    el("div", {},
      el("div", { class: "rail-title" }, "megabrain"),
      el("div", { class: "rail-sub" }, "CODE INTELLIGENCE")));
}

function repoRow(entry: RepoEntry, onPick: (entry: RepoEntry) => void): HTMLElement {
  const row = el("button", { class: "repo-row" },
    el("div", { class: "repo-dot" }, entry.name.slice(0, 2)),
    el("div", { style: "min-width:0;flex:1" },
      el("div", { class: "repo-name" }, entry.name),
      el("div", { class: "repo-meta" }, `${entry.files} files · ${entry.chunks} chunks`)));
  row.dataset["path"] = entry.path;
  row.addEventListener("click", () => onPick(entry));
  return row;
}

function foot(config: Config, onIndex: () => void,
              onSettings: () => void): HTMLElement {
  const index = el("button", { class: "rail-foot-btn" }, icon("plus"), "Index a repo");
  index.addEventListener("click", onIndex);
  if (config.readonly) index.setAttribute("disabled", "true");
  const settings = el("button", { class: "rail-foot-btn" }, icon("gear"), "Settings");
  settings.addEventListener("click", onSettings);
  return el("div", { class: "rail-foot" }, index, themeButton(), settings);
}

function themeButton(): HTMLElement {
  const label = el("span", {}, currentTheme() === "dark" ? "Light theme" : "Dark theme");
  const button = el("button", { class: "rail-foot-btn" }, icon("spark"), label);
  button.addEventListener("click", () => {
    label.textContent = toggleTheme() === "dark" ? "Light theme" : "Dark theme";
  });
  return button;
}

function chip(config: Config): HTMLElement {
  return el("div", { class: "model-chip mono" },
    el("div", { class: "dotlive" }),
    el("span", { style: "font-size:11px" }, `v${config.version}`),
    ...(config.readonly ? [el("span", { class: "active-chip" }, "READ-ONLY")] : []));
}

function burger(host: HTMLElement): HTMLElement {
  const button = el("button", { class: "rail-burger" }, icon("menu"));
  button.addEventListener("click", () => host.classList.toggle("rail-open"));
  return button;
}
