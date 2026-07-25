/* Mouse on canvas: hover, drag, pan, wheel-zoom, click.
 *
 * The one subtlety worth naming: a click with a couple of pixels of jitter is
 * still a click. Without that tolerance, opening a node by clicking it fails
 * about a third of the time — the pointer always moves a little — and the
 * interaction feels broken for a reason nobody can articulate.
 */
import { zoomAt } from "./camera.js";
import type { Sim, SimNode } from "./sim.js";

export interface Handlers {
  onFile(file: string): void;
  onCommunity(id: number): void;
  onHover(node: SimNode | null, clientX: number, clientY: number): void;
}

const JITTER = 4;

export function bindCanvas(sim: () => Sim | null, canvas: HTMLCanvasElement,
                           handlers: Handlers): void {
  let drag: { node: SimNode; x: number; y: number; moved: boolean } | null = null;
  let pan: { x: number; y: number } | null = null;

  const toWorld = (event: MouseEvent, live: Sim): [number, number] => {
    const box = canvas.getBoundingClientRect();
    return [(event.clientX - box.left - live.tx) / live.scale,
            (event.clientY - box.top - live.ty) / live.scale];
  };

  canvas.onmousedown = (event) => {
    const live = sim();
    if (!live) return;
    const found = hit(live, ...toWorld(event, live));
    if (found) {
      drag = { node: found, x: event.clientX, y: event.clientY, moved: false };
      found.fixed = true;
    } else {
      pan = { x: event.clientX - live.tx, y: event.clientY - live.ty };
    }
    canvas.style.cursor = "grabbing";
  };

  canvas.onmousemove = (event) => {
    const live = sim();
    if (!live) return;
    const [x, y] = toWorld(event, live);
    if (drag) {
      if (Math.abs(event.clientX - drag.x) + Math.abs(event.clientY - drag.y) > JITTER) {
        drag.moved = true;
      }
      if (drag.moved) {
        live.owned = true;
        drag.node.x = x;
        drag.node.y = y;
        live.alpha = Math.max(live.alpha, 0.25);   // wake the layout back up
      }
      return;
    }
    if (pan) {
      live.owned = true;
      live.tx = event.clientX - pan.x;
      live.ty = event.clientY - pan.y;
      handlers.onHover(null, event.clientX, event.clientY);
      return;
    }
    const found = hit(live, x, y);
    live.hover = found ? found.file : null;
    canvas.style.cursor = found ? "pointer" : "grab";
    handlers.onHover(found, event.clientX, event.clientY);
  };

  const release = (): void => {
    const live = sim();
    if (live && drag) {
      if (live.mode !== "path") drag.node.fixed = false;
      if (!drag.moved) {
        if (drag.node.bubble) handlers.onCommunity(drag.node.community);
        else handlers.onFile(drag.node.file);
      }
    }
    drag = null;
    pan = null;
    canvas.style.cursor = "grab";
  };

  canvas.onmouseup = release;
  canvas.onmouseleave = (event) => {
    release();
    const live = sim();
    if (live) live.hover = null;
    handlers.onHover(null, event.clientX, event.clientY);
  };

  canvas.onwheel = (event) => {
    const live = sim();
    if (!live) return;
    event.preventDefault();
    const box = canvas.getBoundingClientRect();
    zoomAt(live, event.deltaY < 0 ? 1.12 : 0.89,
           event.clientX - box.left, event.clientY - box.top);
  };
}

function hit(sim: Sim, x: number, y: number): SimNode | null {
  // Slack grows as the view zooms out, so a dot that is three pixels wide on
  // screen is still something a person can click.
  const slack = Math.max(4, 9 / sim.scale);
  // Back to front: the node drawn last is the one on top, so it is the one a
  // click on overlapping circles should land on.
  for (const node of [...sim.nodes].reverse()) {
    const dx = x - node.x;
    const dy = y - node.y;
    const reach = node.r + slack;
    if (dx * dx + dy * dy <= reach * reach) return node;
  }
  return null;
}
