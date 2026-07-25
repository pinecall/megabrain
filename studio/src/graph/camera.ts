/* The camera: fit, zoom, and the static layouts that depend on canvas size.
 *
 * `fitAll` only ever zooms OUT (capped at 1). Node radii already encode meaning
 * — degree, community size — so scaling past 1 to "fill" a wide pane ballooned
 * four bubbles across the whole screen. Zooming in is the + button's job, on
 * demand, and taking the camera is the user's decision.
 */
import type { Sim } from "./sim.js";

export const MIN_SCALE = 0.15;
export const MAX_SCALE = 5;

export function fitAll(sim: Sim, padding = 70): void {
  if (!sim.nodes.length) return;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const node of sim.nodes) {
    x0 = Math.min(x0, node.x - node.r);
    y0 = Math.min(y0, node.y - node.r);
    x1 = Math.max(x1, node.x + node.r);
    y1 = Math.max(y1, node.y + node.r);
  }
  const pad = sim.mode === "path" ? Math.max(padding, 130) : padding;  // end labels
  const scale = Math.min(1, Math.max(MIN_SCALE,
    Math.min(sim.width / (x1 - x0 + pad * 2), sim.height / (y1 - y0 + pad * 2))));
  sim.scale = scale;
  sim.tx = sim.width / 2 - ((x0 + x1) / 2) * scale;
  sim.ty = sim.height / 2 - ((y0 + y1) / 2) * scale;
}

export function zoomBy(sim: Sim, factor: number): void {
  sim.owned = true;                        // a manual zoom pauses the auto-fit
  const next = clamp(sim.scale * factor);
  sim.tx = sim.width / 2 - ((sim.width / 2 - sim.tx) / sim.scale) * next;
  sim.ty = sim.height / 2 - ((sim.height / 2 - sim.ty) / sim.scale) * next;
  sim.scale = next;
}

export function zoomAt(sim: Sim, factor: number, x: number, y: number): void {
  sim.owned = true;
  const next = clamp(sim.scale * factor);
  sim.tx = x - ((x - sim.tx) / sim.scale) * next;
  sim.ty = y - ((y - sim.ty) / sim.scale) * next;
  sim.scale = next;
}

export function clamp(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

/* A route is laid out, not simulated: a clean zigzag reads as a sequence, and a
 * force layout of five nodes wanders. Re-run on every resize — mount-time
 * positions go stale and push nodes out of the viewport. The margin ADAPTS,
 * because a fixed 110px on a narrow pane exceeds half the width and the span
 * goes negative, which renders the route backwards. */
export function layoutRoute(sim: Sim): void {
  if (sim.mode !== "path") return;
  const margin = Math.min(110, sim.width * 0.15);
  const span = Math.max(1, sim.nodes.length - 1);
  sim.nodes.forEach((node, step) => {
    node.x = margin + (sim.width - 2 * margin) * (step / span);
    node.y = sim.height / 2 + (step % 2 ? 60 : -60);
  });
}
