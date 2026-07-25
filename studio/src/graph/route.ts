/* The route panel: the connection, told in words and then in code.
 *
 * Three parts, in the order a reader needs them. The hop list — where the route
 * goes. HOW IT CONNECTS — one sentence per hop, built from the real use/def
 * sides: who calls what, from inside which function, and where it lives. Then
 * the storyboard: every hop's call and definition, one click from the editor.
 *
 * And the warning, when it applies. A route that is not a call chain gets said
 * so loudly, because the diagram alone reads like a flow.
 */
import type { GraphPath, Hop } from "../contracts.js";
import { el } from "../dom.js";
import { card } from "./panel.js";

export interface RouteHandlers {
  openFile(file: string): void;
  openAt(file: string, line: number): void;
  play(): void;
  back(): void;
}

const base = (file: string): string => file.split("/").pop() ?? file;

export function routePanel(path: GraphPath, handlers: RouteHandlers): HTMLElement[] {
  const head = el("div", { class: "t2-card" },
    el("div", { class: "panel-title" },
       path.found ? `Path — ${path.hops.length} hops` : "Path — not found"),
    el("div", { class: "mono dim" }, `${path.source} → ${path.target}`),
    ...(path.flipped
      ? [el("div", { class: "accent small" },
           "↻ shown in call-flow order — the calls run this way, opposite to how "
           + "you asked")]
      : []),
    ...(path.chain ? [] : [meeting(path)]),
    el("div", { class: "row-stack" },
       ...(path.found ? path.hops.map((hop, step) => hopRow(hop, step, handlers))
         : [el("p", { class: "dim" },
              "no route — the endpoints live on disconnected islands")])),
    el("div", { class: "pill-row" },
      ...(path.found && path.hops.length > 1
        ? [el("button", { class: "btn-primary", onclick: handlers.play },
             "▶ Run the connection")]
        : []),
      el("button", { class: "chip", onclick: handlers.back }, "← overview")));
  const story = path.found ? path.hops.slice(1).map(sentence) : [];
  return [
    head,
    ...(story.length ? [card("HOW IT CONNECTS", [el("ul", { class: "story" },
      ...story.map((line) => el("li", {}, ...line)))])] : []),
    ...(path.found ? path.hops.slice(1)
      .flatMap((hop, step) => {
        const previous = path.hops[step];
        const built = previous ? storyboard(hop, step, previous.file, handlers) : null;
        return built ? [built] : [];
      }) : []),
  ];
}

function meeting(path: GraphPath): HTMLElement {
  const shared = base(path.meet ?? "a shared file");
  return el("div", { class: "warn-bar" },
    el("b", {}, "not a call chain"),
    ` — ${base(path.source)} and ${base(path.target)} never call each other. `,
    path.meet_kind === "caller"
      ? `${shared} calls BOTH sides — it is the shared orchestrator.`
      : `Both connect INTO ${shared}.`,
    " Follow the arrowheads.");
}

function hopRow(hop: Hop, step: number, handlers: RouteHandlers): HTMLElement {
  const carriers = hop.symbols ?? [];
  return el("button", { class: "flag-row wrap",
                        onclick: () => handlers.openFile(hop.file) },
    el("div", { class: "flag-reason" },
       step === 0 ? "start" : hop.via.split("/")[0] || "hop"),
    el("span", { class: "mono", style: "flex:1" }, hop.file),
    ...(carriers.length
      ? [el("span", { class: "mono accent hop-via" }, `via ${carriers.join(" · ")}`)]
      : []));
}

/* One bullet per hop, from the hop's own evidence. A semantic hop says it has
 * NO code link rather than pretending to one — that honesty is the difference
 * between a map and a guess. */
function sentence(hop: Hop): (Node | string)[] {
  const code = hop.code;
  const strong = (text: string): HTMLElement => el("b", {}, text);
  if (code?.use && code.definition) {
    return [
      strong(base(code.use.file)),
      code.use.in_symbol ? ` — from inside ${code.use.in_symbol}() —` : "",
      " calls ", el("b", { class: "accent" }, `${code.symbol}()`),
      ", which lives in ", strong(base(code.definition.file)),
      code.verified ? "" : " · inferred (variable receiver — unverified)",
    ];
  }
  if (/^semantic/.test(hop.via)) {
    return [strong(base(hop.file)), " has no code link here — it is related by "
            + `meaning (${hop.via})`];
  }
  return [`reaches `, strong(base(hop.file)), ` via ${hop.via}`];
}

function storyboard(hop: Hop, step: number, from: string,
                    handlers: RouteHandlers): HTMLElement | null {
  const code = hop.code;
  if (!code || (!code.use && !code.definition)) return null;
  const title = `${base(code.use?.file ?? from)} → `
    + `${base(code.definition?.file ?? hop.file)} · ${code.symbol}()`;
  const rows = [code.use, code.definition]
    .map((snip, which) => (snip
      ? el("button", { class: "flag-row",
                       onclick: () => handlers.openAt(snip.file,
                                                     snip.start_line + (snip.hi_rows[0] ?? 0)) },
          el("div", { class: "flag-reason accent" }, which ? "definition" : "the call"),
          el("span", { class: "mono" },
             `${snip.in_symbol ? `inside ${snip.in_symbol}() · ` : ""}`
             + `${snip.file}:${snip.start_line + (snip.hi_rows[0] ?? 0)}`))
      : null))
    .filter((row): row is HTMLElement => row !== null);
  const details = el("details", { class: "t2-card" },
    el("summary", {},
       el("div", { class: "flag-reason" }, `step ${step + 1}`),
       el("span", { class: "mono" }, title)),
    el("div", { class: "pill-row" }, ...(hop.symbols ?? []).map((symbol) =>
       el("span", { class: "file-pill mono" }, symbol))),
    el("div", { class: "row-stack" }, ...rows));
  if (step === 0) details.setAttribute("open", "");
  return details;
}
