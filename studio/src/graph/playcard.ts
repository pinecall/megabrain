/* The walkthrough card: one step's real code, beside the canvas.
 *
 * While it runs it TAKES the panel's place rather than squeezing in next to it.
 * The code is the step — a reader following a connection wants the call in front
 * of them, not a third of a column of it — and the canvas keeps the ring and the
 * pulse in sync so the two halves always talk about the same hop.
 */
import type { CodeSnip } from "../contracts.js";
import { el, fill } from "../dom.js";
import type { Walk } from "./play.js";

export interface CardHandlers {
  toggleAuto(): void;
  step(to: number): void;
  stop(): void;
  openInEditor(file: string, line: number): void;
}

export function paintCard(host: HTMLElement, walk: Walk | null,
                          handlers: CardHandlers): void {
  if (!walk) {
    host.classList.remove("on");
    return;
  }
  const step = walk.steps[walk.at];
  if (!step) return;
  host.classList.add("on");
  fill(host,
    controls(walk, handlers),
    el("div", { class: "play-label mono" },
       `hop ${step.hop} · `, el("b", { class: "accent" }, step.kind.toUpperCase()),
       ` — ${step.symbol}()`,
       step.inSymbol ? ` inside ${step.inSymbol}()` : "",
       ` · ${step.file.split("/").pop() ?? step.file}`),
    snippet(step.snip),
    el("button", { class: "chip accent-chip mono",
                   onclick: () => handlers.openInEditor(step.file, step.line) },
       "⤢ open this step in the editor — full file, clickable symbols"));
}

function controls(walk: Walk, handlers: CardHandlers): HTMLElement {
  const button = (label: string, enabled: boolean, action: () => void): HTMLElement => {
    const node = el("button", { class: "chip zoom-btn mono", onclick: action }, label);
    if (!enabled) node.setAttribute("disabled", "");
    return node;
  };
  return el("div", { class: "play-head" },
    el("div", { class: "flag-reason" }, `step ${walk.at + 1} / ${walk.steps.length}`),
    el("div", { style: "flex:1" }),
    button(walk.auto ? "⏸" : "▶", true, handlers.toggleAuto),
    button("‹", walk.at > 0, () => handlers.step(walk.at - 1)),
    button("›", walk.at < walk.steps.length - 1, () => handlers.step(walk.at + 1)),
    button("✕", true, handlers.stop));
}

/* Rows highlighted by the ROW NUMBERS the engine marked, not by matching the
 * symbol's text: a same-named local on another line would light up, and the
 * reader would take it for the call. */
function snippet(snip: CodeSnip): HTMLElement {
  const marked = new Set(snip.hi_rows);
  return el("div", { class: "play-code mono" },
    ...snip.text.split("\n").map((line, offset) =>
      el("div", { class: marked.has(offset) ? "play-row hi" : "play-row" },
         el("span", { class: "play-no" }, String(snip.start_line + offset)),
         el("span", { class: "play-src" }, line))));
}
