/* The graph panel: what depends on what.
 *
 * Two views. The map ranks by IN-degree — a file twenty others import is
 * load-bearing, while one that imports twenty is merely busy — and a
 * neighbourhood shows both directions, because "who imports this" is the half
 * a reader cannot get by opening the file.
 *
 * No node-link drawing. A force layout of 1200 files is a hairball that answers
 * nothing; the useful questions are "what is load-bearing" and "what touches
 * this", and both are lists.
 */
import { api } from "./api.js";
import type { GraphMap, Neighbourhood } from "./contracts.js";
import { el, fill } from "./dom.js";

export interface GraphPanel {
  overview(): Promise<void>;
  node(file: string): Promise<void>;
}

export function graphPanel(host: HTMLElement, repo: () => string | undefined,
                           onOpen: (file: string) => void): GraphPanel {
  return {
    async overview(): Promise<void> {
      fill(host, el("p", { class: "dim" }, "building the graph…"));
      fill(host, ...renderMap(await api.graph(repo()), onOpen));
    },
    async node(file: string): Promise<void> {
      fill(host, el("p", { class: "dim" }, `${file}…`));
      fill(host, ...renderNode(await api.node(file, repo()), onOpen));
    },
  };
}

function renderMap(view: GraphMap, onOpen: (file: string) => void): HTMLElement[] {
  const largest = view.communities[0];
  return [
    el("div", { class: "result-head" },
      el("strong", {}, `${view.files} files`),
      el("span", { class: "dim" },
         ` · ${view.links.length} dependencies · ${view.communities.length} clusters`
         + ` · ${view.ms}ms`)),
    el("h4", {}, "most depended upon"),
    el("ul", { class: "hubs" }, ...view.hubs.filter((hub) => hub.in_degree > 0).map((hub) =>
      el("li", { onclick: () => onOpen(hub.file) },
         el("span", { class: "count" }, String(hub.in_degree)), hub.file))),
    // Said out loud rather than drawn as if it meant something: label
    // propagation floods through a hub, so on a hub-heavy repository one
    // cluster swallows nearly everything. A panel that presents that as
    // structure is a panel that lies.
    largest && largest.size > view.files * 0.6
      ? el("p", { class: "dim" },
           `clustering is degenerate on this repository (one cluster holds `
           + `${largest.size} of ${view.files} files) — read the hubs instead`)
      : el("ul", { class: "clusters" }, ...view.communities.slice(0, 12).map((community) =>
          el("li", {}, el("span", { class: "count" }, String(community.size)),
             community.files.slice(0, 4).join(", ")))),
  ];
}

function renderNode(view: Neighbourhood, onOpen: (file: string) => void): HTMLElement[] {
  const list = (files: string[], arrow: string) =>
    el("ul", { class: "outline" }, ...files.map((file) =>
      el("li", { onclick: () => onOpen(file) },
         el("span", { class: "dim" }, `${arrow} `), file)));
  return [
    el("div", { class: "file-head" }, el("strong", {}, view.file)),
    el("h4", {}, `imports (${view.imports.length})`), list(view.imports, "→"),
    el("h4", {}, `imported by (${view.imported_by.length})`),
    list(view.imported_by, "←"),
  ];
}
