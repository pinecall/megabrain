/* The graph view: what a change lands on, and what one file touches.
 *
 * Lists, not a force layout. A hairball of 1200 nodes answers nothing, and the
 * two questions people actually bring here — "what is load-bearing" and "what
 * touches this" — are both lists. It also says out loud when the clustering is
 * degenerate rather than drawing a 1180-file blob as if it meant something.
 */
import { api } from "../api.js";
import type { GraphMap } from "../contracts.js";
import { el, fill } from "../dom.js";
import { icon } from "../icons.js";

export interface GraphView {
  root: HTMLElement;
  focus(): void;
  load(): Promise<void>;
}

export function graphView(repo: () => string | undefined,
                          onOpen: (file: string) => void,
                          onError: (failure: unknown) => void): GraphView {
  const body = el("div", {});
  return {
    root: el("div", { class: "view-wrap" }, body),
    focus: () => {},
    async load(): Promise<void> {
      fill(body, el("div", { class: "empty" }, el("div", { class: "spinner" }),
                    "building the graph…"));
      try {
        fill(body, ...render(await api.graph(repo()), onOpen));
      } catch (failure) {
        onError(failure);
      }
    },
  };
}

function render(view: GraphMap, onOpen: (file: string) => void): HTMLElement[] {
  const largest = view.communities[0];
  const degenerate = largest && largest.size > view.files * 0.6;
  return [
    el("div", { class: "stats-row" },
      el("b", {}, String(view.files)), " files", el("div", { class: "sdot" }),
      el("b", {}, String(view.links.length)), " dependencies",
      el("div", { class: "sdot" }), el("b", {}, `${view.ms}ms`)),
    el("div", { class: "section-head" },
      el("div", { class: "section-label" }, "MOST DEPENDED UPON"),
      el("div", { class: "section-rule" })),
    el("div", { style: "display:grid;gap:6px" },
      ...view.hubs.filter((hub) => hub.in_degree > 0).map((hub) => {
        const row = el("button", { class: "t2-card" },
          el("div", { style: "display:flex;gap:12px;align-items:center" },
            el("span", { class: "badge", style: "margin:0" }, String(hub.in_degree)),
            el("span", { class: "file-path mono", style: "flex:1;font-size:12px" },
               hub.file),
            icon("chevron", 13)));
        row.addEventListener("click", () => onOpen(hub.file));
        return row;
      })),
    el("div", { class: "section-head" },
      el("div", { class: "section-label" }, "CLUSTERS"),
      el("div", { class: "section-rule" })),
    degenerate
      ? el("div", { class: "info-bar" },
          el("div", { class: "chip-ic" }, icon("graph", 11)),
          `clustering is degenerate on this repository — one cluster holds `
          + `${largest.size} of ${view.files} files. Read the hubs instead.`)
      : el("div", { class: "split-2" },
          ...view.communities.slice(0, 12).map((community) =>
            el("div", { class: "t2-card" },
              el("div", { style: "display:flex;gap:10px" },
                el("span", { class: "kind-pill on" }, `${community.size}`),
                el("span", { class: "mono", style: "font-size:11.5px" },
                   community.files.slice(0, 3).join(", ")))))),
  ];
}
