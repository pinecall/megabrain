/* The side panel: what the canvas cannot say in shapes.
 *
 * Every mode has its own panel, and the overview's is the one that teaches the
 * view: what a bubble is, and how to get from it to a file. Below that go the
 * three findings a drawing cannot carry — the clusters with their names, the
 * core files with their in/out split, and the twins that never met.
 */
import type { Community, GodNode, GraphMap, NodeView, Surprise } from "../contracts.js";
import { el } from "../dom.js";
import { communityColour } from "./draw.js";

export interface PanelHandlers {
  openFile(file: string): void;
  openCommunity(id: number): void;
}

export function overviewPanel(view: GraphMap, handlers: PanelHandlers): HTMLElement[] {
  const multi = view.communities.filter((community) => community.size > 1);
  const singles = view.communities.filter((community) => community.size === 1);
  return [
    el("div", { class: "info-bar" },
      "Each bubble is a community: files that import or call each other, or talk "
      + "about the same thing. Click one to open just that part. Or type "
      + "a → b to see how two files connect."),
    card("COMMUNITIES", [
      ...multi.map((community) => communityRow(community, handlers)),
      ...(singles.length ? [standalone(singles, handlers)] : []),
    ]),
    card("THE CORE — WHERE A CHANGE LANDS HARDEST",
         view.god_nodes.length ? view.god_nodes.map((god) => godRow(god, handlers))
           : [el("p", { class: "dim" }, "no structural edges yet")]),
    ...(view.surprises.length
      ? [card("TWINS THAT NEVER MET — SIMILAR CODE, NO DEPENDENCY",
              view.surprises.map((surprise) => surpriseRow(surprise, handlers)))]
      : []),
  ];
}

export function nodePanel(view: NodeView, handlers: PanelHandlers,
                          onBack: () => void): HTMLElement[] {
  const head = el("div", { class: "t2-card" },
    el("div", { class: "file-path mono" }, view.file),
    el("div", { class: "pill-row" },
      el("span", { class: "chip",
                   style: `border-color:${communityColour(view.community, 0.5)};`
                          + `color:${communityColour(view.community)}` },
         `● ${view.community_label}`),
      el("span", { class: "file-pill mono" }, `degree ${view.degree}`),
      ...(view.resolved_from !== view.file
        ? [el("span", { class: "file-pill mono" }, `← "${view.resolved_from}"`)]
        : [])),
    el("button", { class: "chip", onclick: onBack }, "← back"));
  return [
    head,
    ...(view.imports.length
      ? [card("OUTGOING", view.imports.map((edge) =>
          fileRow(edge.file, edge.kind, handlers)))]
      : []),
    ...(view.imported_by.length
      ? [card("INCOMING", view.imported_by.map((edge) =>
          fileRow(edge.file, edge.kind, handlers)))]
      : []),
    ...(view.semantic.length
      ? [card("SEMANTICALLY CLOSE", view.semantic.map((tie) =>
          fileRow(tie.file, `~${tie.score}`, handlers)))]
      : []),
    ...(view.symbols.length
      ? [card("SYMBOLS", view.symbols.slice(0, 40).map((symbol) =>
          el("div", { class: "flag-row" },
             el("div", { class: "flag-reason" }, symbol.kind),
             el("span", { class: "mono" }, symbol.name))))]
      : []),
  ];
}

export function communityPanel(view: GraphMap, id: number,
                               handlers: PanelHandlers): HTMLElement[] {
  const found = view.communities.find((community) => community.id === id);
  if (!found) return overviewPanel(view, handlers);
  const degrees = new Map(view.nodes.map((node) => [node.file, node.degree]));
  return [card(found.label.toUpperCase(), found.files.map((file) =>
    fileRow(file, `deg ${degrees.get(file) ?? 0}`, handlers)))];
}

export function subgraphPanel(query: string, files: { file: string; score: number }[],
                              handlers: PanelHandlers): HTMLElement[] {
  return [
    el("div", { class: "info-bar" },
      `Real retrieval — the same engine as Search — drawn as its subgraph. Only `
      + `these files and the links between them are on the canvas.`),
    card(`RELEVANT TO "${query}"`, files.map((hit) =>
      fileRow(hit.file, hit.score.toFixed(2), handlers))),
  ];
}

export function card(label: string, rows: HTMLElement[]): HTMLElement {
  return el("div", { class: "t2-card" },
    el("div", { class: "section-label" }, label),
    el("div", { class: "row-stack" }, ...rows));
}

function communityRow(community: Community, handlers: PanelHandlers): HTMLElement {
  return el("button", { class: "flag-row",
                        onclick: () => handlers.openCommunity(community.id) },
    el("span", { class: "com-dot",
                 style: `background:${communityColour(community.id)}` }),
    el("span", { style: "flex:1" }, community.label),
    el("span", { class: "mono dim" }, String(community.size)));
}

function standalone(singles: Community[], handlers: PanelHandlers): HTMLElement {
  const body = el("div", { class: "row-stack" }, ...singles.flatMap((community) => {
    const only = community.files[0];
    return only ? [fileRow(only, "", handlers)] : [];
  }));
  const summary = el("summary", { class: "mono dim" },
    `+${singles.length} standalone files (docs, configs — no code links)`);
  return el("details", {}, summary, body);
}

function godRow(god: GodNode, handlers: PanelHandlers): HTMLElement {
  return el("button", { class: "flag-row", onclick: () => handlers.openFile(god.file) },
    el("div", { class: "flag-reason" }, `${god.in_degree} in · ${god.out_degree} out`),
    el("span", { class: "mono", style: "flex:1" }, god.file));
}

function surpriseRow(surprise: Surprise, handlers: PanelHandlers): HTMLElement {
  return el("div", { class: "flag-row" },
    el("button", { class: "mono link", onclick: () => handlers.openFile(surprise.a) },
       surprise.a.split("/").pop() ?? surprise.a),
    el("span", { class: "mono accent" }, `~${surprise.score}~`),
    el("button", { class: "mono link", onclick: () => handlers.openFile(surprise.b) },
       surprise.b.split("/").pop() ?? surprise.b));
}

function fileRow(file: string, mark: string, handlers: PanelHandlers): HTMLElement {
  return el("button", { class: "flag-row", onclick: () => handlers.openFile(file) },
    ...(mark ? [el("div", { class: "flag-reason" }, mark)] : []),
    el("span", { class: "mono", style: "flex:1" }, file));
}
