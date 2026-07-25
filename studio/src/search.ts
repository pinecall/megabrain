/* The search panel: a question in, a code map out.
 *
 * Renders the two tiers the way the engine means them — CORE with full code,
 * RELATED as a MAP. That split is the product: RELATED holds 45% of the gold
 * files, so it cannot be dropped, but ~95% of its volume is code bodies that
 * flood a reader. Here it is a list you click, not a wall you scroll.
 */
import { api } from "./api.js";
import type { Bundle, Tier1File, Tier2File } from "./contracts.js";
import { code, el, fill } from "./dom.js";

export interface SearchPanel {
  run(query: string, content?: "code" | "docs"): Promise<void>;
}

export function searchPanel(host: HTMLElement, repo: () => string | undefined,
                            onOpen: (file: string, symbol?: string) => void): SearchPanel {
  return {
    async run(query: string, content?: "code" | "docs"): Promise<void> {
      fill(host, el("p", { class: "dim" }, "searching…"));
      const bundle = await api.search(query, repo(), content);
      fill(host, header(bundle), ...bundle.tier1.map((f) => core(f, onOpen)),
           ...related(bundle.tier2, onOpen));
    },
  };
}

function header(bundle: Bundle): HTMLElement {
  return el("div", { class: "result-head" },
    el("strong", {}, `${bundle.tier1.length} core`),
    el("span", { class: "dim" },
       ` · ${bundle.tier2.length} related · ${bundle.ms}ms · ${bundle.repo}`));
}

function core(file: Tier1File, onOpen: (file: string, symbol?: string) => void): HTMLElement {
  const body = el("div", { class: "chunks" });
  for (const chunk of file.chunks) {
    body.append(
      el("div", { class: "chunk-head" },
         el("span", { class: "name" }, chunk.name ?? chunk.kind),
         el("span", { class: "dim" }, ` L${chunk.start_line}-${chunk.end_line}`)),
      code(chunk.text, chunk.start_line));
  }
  return el("section", { class: "card core" },
    el("h3", { class: "file", onclick: () => onOpen(file.file) }, file.file),
    el("span", { class: "score" }, file.score.toFixed(2)),
    body,
    file.neighbors.length
      ? el("p", { class: "dim linked" }, `linked: ${file.neighbors.join(", ")}`)
      : el("span"));
}

function related(files: Tier2File[],
                 onOpen: (file: string, symbol?: string) => void): HTMLElement[] {
  if (!files.length) return [];
  return [
    el("h2", { class: "tier" }, "RELATED"),
    el("p", { class: "dim" }, "the map: click a file for its code"),
    ...files.map((file) => el("section", { class: "card map" },
      el("h4", { class: "file", onclick: () => onOpen(file.file) }, file.file),
      el("span", { class: "score" }, file.score.toFixed(2)),
      file.via_graph ? el("span", { class: "tag" }, "via graph") : el("span"),
      file.doc ? el("p", { class: "doc" }, file.doc) : el("span"),
      el("ul", { class: "outline" }, ...file.symbols.map((symbol) =>
        el("li", { onclick: () => onOpen(file.file, symbol.name) },
           symbol.signature ?? symbol.name))))),
  ];
}
