/* The canvas stage: the element, the frame loop, the tooltip, the zoom buttons.
 *
 * One owner for the animation frame and one owner for the sizing. The canvas
 * shares its row with the panel, so when that opens or closes — or the window
 * resizes — the buffer has to be re-measured or the whole drawing skews. A
 * ResizeObserver does it; the CSS size is set alongside the device-pixel buffer,
 * because without it the canvas displays its full 2× buffer and overflows.
 */
import type { GraphMap, GraphPath } from "../contracts.js";
import { el } from "../dom.js";
import { fitAll, layoutRoute, zoomBy } from "./camera.js";
import { communityColour, draw } from "./draw.js";
import { bindCanvas } from "./input.js";
import { buildSim, type Options } from "./layout.js";
import type { Sim, SimMode, SimNode } from "./sim.js";
import { tick } from "./sim.js";
import { advance, walkSteps, type Walk } from "./play.js";
import { paintCard } from "./playcard.js";

export interface Stage {
  root: HTMLElement;
  mount(view: GraphMap, mode: SimMode, options: Options): void;
  select(file: string): void;
  /* Starts the walkthrough, or reports that this route has no code to walk —
   * a semantic-only path is a real answer, and pretending otherwise with an
   * empty card is worse than saying so. */
  play(route: GraphPath | null): boolean;
}

export interface StageOptions {
  onFile(file: string): void;
  onCommunity(id: number): void;
  labelOf(id: number): string;
  isGod(file: string): boolean;
  /* The walkthrough hands a step to the editor for full-file reading. */
  openInEditor(file: string, line: number): void;
  /* Called when the walkthrough starts or stops, so the view can hide the panel
   * the card is taking the place of. */
  onWalk(running: boolean): void;
}

const FRAME = 1 / 60;

export function canvasStage(options: StageOptions): Stage {
  const canvas = el("canvas", { class: "graph-canvas-el" }) as HTMLCanvasElement;
  const tip = el("div", { class: "graph-tip mono" });
  const card = el("div", { class: "graph-play" });
  let sim: Sim | null = null;
  let walk: Walk | null = null;
  let frame = 0;
  const wrap = el("div", { class: "graph-canvas" }, canvas, tip,
                  zoomButtons(() => sim), legend());

  const repaintCard = (): void => paintCard(card, walk, {
    toggleAuto: () => { if (walk) { walk.auto = !walk.auto; walk.elapsed = 0; }
                        repaintCard(); },
    step: (to) => {
      if (!walk) return;
      walk.at = Math.max(0, Math.min(walk.steps.length - 1, to));
      walk.elapsed = 0;
      walk.auto = false;              // stepping by hand means driving by hand
      repaintCard();
    },
    stop: () => { walk = null; repaintCard(); options.onWalk(false); },
    openInEditor: options.openInEditor,
  });

  bindCanvas(() => sim, canvas, {
    onFile: options.onFile,
    onCommunity: options.onCommunity,
    onHover: (node, x, y) => showTip(tip, wrap, node, x, y, options),
  });

  const resize = (): void => {
    if (!sim) return;
    const width = wrap.clientWidth;
    const height = wrap.clientHeight;
    if (!width || !height || (width === sim.width && height === sim.height)) return;
    sim.width = width;
    sim.height = height;
    size(canvas, sim);
    layoutRoute(sim);
    if (!sim.owned) fitAll(sim);
  };
  new ResizeObserver(resize).observe(wrap);

  const loop = (): void => {
    frame = requestAnimationFrame(loop);
    const live = sim;
    if (!live) return;
    if (live.alpha > 0.012 && !document.hidden) tick(live);
    // Every frame until the user takes the camera. Gating this on the alpha left
    // late drift uncorrected, and a bbox pass is nothing next to the draw.
    if (!live.owned) fitAll(live);
    // The card repaints only when the step CHANGES, not every frame: the code
    // block is real DOM, and rebuilding it sixty times a second for an animation
    // that did not move is how a smooth canvas ends up feeling slow.
    if (walk && !document.hidden && advance(walk, FRAME)) repaintCard();
    const context = canvas.getContext("2d");
    if (context) draw(live, context, walk);
  };

  return {
    root: el("div", { class: "graph-stage" }, wrap, card),
    mount(view, mode, opts) {
      cancelAnimationFrame(frame);
      walk = null;
      repaintCard();
      sim = buildSim(view, mode, {
        width: wrap.clientWidth || 800, height: wrap.clientHeight || 500,
        dpr: window.devicePixelRatio || 1,
      }, opts);
      size(canvas, sim);
      layoutRoute(sim);
      fitAll(sim);
      loop();
    },
    select(file) {
      if (sim) sim.selected = file;
    },
    play(route) {
      const steps = walkSteps(route);
      walk = steps.length ? { steps, at: 0, elapsed: 0, auto: true } : null;
      repaintCard();
      options.onWalk(Boolean(walk));
      return Boolean(walk);
    },
  };
}

function size(canvas: HTMLCanvasElement, sim: Sim): void {
  canvas.width = sim.width * sim.dpr;
  canvas.height = sim.height * sim.dpr;
  canvas.style.width = `${sim.width}px`;
  canvas.style.height = `${sim.height}px`;
}

function showTip(tip: HTMLElement, wrap: HTMLElement, node: SimNode | null,
                 clientX: number, clientY: number, options: StageOptions): void {
  if (!node) {
    tip.style.display = "none";
    return;
  }
  const box = wrap.getBoundingClientRect();
  tip.replaceChildren(...(node.bubble
    ? [el("b", {}, node.label ?? ""), ` · ${node.size} files`,
       el("div", { class: "dim" }, "click to open this community")]
    : [el("b", {}, node.file),
       el("div", { style: `color:${communityColour(node.community)}` },
          `● ${options.labelOf(node.community)}`),
       `${node.degree} link${node.degree === 1 ? "" : "s"}`
       + (options.isGod(node.file) ? " · ★ core file" : ""),
       el("div", { class: "dim" }, "click for neighbours + code")]));
  tip.style.display = "block";
  tip.style.left = `${Math.min(clientX - box.left + 14, box.width - 300)}px`;
  tip.style.top = `${clientY - box.top + 12}px`;
}

/* The buttons read the LIVE simulation through the accessor rather than closing
 * over one: `mount` replaces the simulation on every mode change, and a captured
 * reference would keep zooming the previous graph. */
function zoomButtons(sim: () => Sim | null): HTMLElement {
  const zoom = (label: string, title: string, factor: number): HTMLElement =>
    el("button", { class: "chip zoom-btn mono", title,
                   onclick: () => { const live = sim(); if (live) zoomBy(live, factor); } },
       label);
  return el("div", { class: "zoom-stack" },
    zoom("+", "zoom in", 1.25), zoom("−", "zoom out", 0.8),
    el("button", { class: "chip zoom-btn mono", title: "fit everything",
                   onclick: () => {
                     const live = sim();
                     if (!live) return;
                     live.owned = false;     // hand the camera back to auto-fit
                     fitAll(live);
                   } }, "⊙"));
}

function legend(): HTMLElement {
  return el("div", { class: "graph-legend mono" },
    el("b", {}, "solid"), " import/call · ", el("b", {}, "dashed"), " semantic"
    + " · drag · wheel zoom · click a file for neighbours + code");
}
