/* Drawing one frame. Reads the simulation, writes pixels, decides nothing.
 *
 * Colour comes from the community through the golden angle, so neighbouring ids
 * never land on neighbouring hues. Solid lines are structure, dashed are
 * semantic — one legend, honoured everywhere, because a cosine drawn like an
 * import sends the reader looking for a call that does not exist.
 */
import type { Sim, SimLink, SimNode } from "./sim.js";
import type { Walk } from "./play.js";

export const communityColour = (id: number, alpha = 1): string =>
  `hsla(${(id * 137.508) % 360}, 58%, 62%, ${alpha})`;

const MONO = "ui-monospace, Menlo, monospace";

interface Palette {
  muted: string;
  text: string;
}

export function draw(sim: Sim, context: CanvasRenderingContext2D,
                     walk: Walk | null): void {
  const style = getComputedStyle(document.documentElement);
  const palette: Palette = {
    muted: style.getPropertyValue("--muted").trim() || "#7a7a84",
    text: style.getPropertyValue("--text").trim() || "#e9e9ec",
  };
  context.setTransform(sim.dpr, 0, 0, sim.dpr, 0, 0);
  context.clearRect(0, 0, sim.width, sim.height);
  context.translate(sim.tx, sim.ty);
  context.scale(sim.scale, sim.scale);
  for (const link of sim.links) drawLink(sim, context, link, palette, walk);
  context.setLineDash([]);
  context.globalAlpha = 1;
  for (const node of sim.nodes) drawNode(sim, context, node, palette.text);
  if (walk) ringActive(sim, context, walk);
  drawLabels(sim, context, palette);
}

function drawLink(sim: Sim, context: CanvasRenderingContext2D, link: SimLink,
                  palette: Palette, walk: Walk | null): void {
  const { one, two } = link;
  context.beginPath();
  context.moveTo(one.x, one.y);
  context.lineTo(two.x, two.y);
  context.setLineDash(link.semantic ? [3, 4] : []);
  if (sim.mode === "overview") {
    context.strokeStyle = palette.muted;
    context.globalAlpha = 0.35;
    context.lineWidth = Math.min(6, 1 + Math.log2(1 + (link.count ?? 1))) / sim.scale;
  } else if (sim.mode === "path") {
    drawRouteLink(sim, context, link, walk);
    context.beginPath();               // the outer stroke below is now a no-op
  } else {
    context.strokeStyle = link.semantic
      ? communityColour(one.community, 0.22) : palette.muted;
    context.globalAlpha = link.semantic ? 0.5 : 0.3;
    context.lineWidth = 1.1 / sim.scale;
  }
  context.stroke();
  if (sim.mode === "path" && link.via) labelHop(sim, context, link, palette.muted);
}

function drawRouteLink(sim: Sim, context: CanvasRenderingContext2D, link: SimLink,
                       walk: Walk | null): void {
  const current = walk ? currentHop(walk) : -1;
  const hop = link.hop ?? 0;
  const state = !walk ? "plain" : hop < current ? "done"
    : hop === current ? "now" : "future";
  context.strokeStyle = communityColour(link.one.community, 0.9);
  context.globalAlpha = state === "future" ? 0.15 : state === "now" ? 0.3 : 0.92;
  context.lineWidth = 2.5 / sim.scale;
  // The base line FIRST: a canvas path is not saved state, so the arrowhead's
  // `beginPath` below discards whatever has not been stroked yet.
  context.stroke();
  arrowhead(sim, context, link, state);
  if (state === "now" && walk) pulse(sim, context, link, walk);
}

const currentHop = (walk: Walk): number => {
  const step = walk.steps[walk.at];
  return step ? step.hop - 1 : -1;
};

function arrowhead(sim: Sim, context: CanvasRenderingContext2D, link: SimLink,
                   state: string): void {
  const { from, to } = link;
  if (!from || !to) return;            // no verified direction: no arrowhead
  const angle = Math.atan2(to.y - from.y, to.x - from.x);
  const size = 10 / sim.scale;
  const x = to.x - Math.cos(angle) * (to.r + 5);
  const y = to.y - Math.sin(angle) * (to.r + 5);
  context.globalAlpha = state === "future" ? 0.3 : 0.92;
  context.beginPath();
  context.moveTo(x, y);
  context.lineTo(x - size * Math.cos(angle - 0.42), y - size * Math.sin(angle - 0.42));
  context.lineTo(x - size * Math.cos(angle + 0.42), y - size * Math.sin(angle + 0.42));
  context.closePath();
  context.fillStyle = communityColour(link.one.community, 0.95);
  context.fill();
}

function pulse(sim: Sim, context: CanvasRenderingContext2D, link: SimLink,
               walk: Walk): void {
  // Travels the hop's true call direction, so the animation teaches the same
  // thing the arrowhead does instead of contradicting it.
  const from = link.from ?? link.one;
  const to = link.to ?? link.two;
  const at = Math.min(1, walk.elapsed / 3);
  const x = from.x + (to.x - from.x) * at;
  const y = from.y + (to.y - from.y) * at;
  const colour = communityColour(link.one.community, 0.95);
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(x, y);
  context.globalAlpha = 0.95;
  context.lineWidth = 3 / sim.scale;
  context.strokeStyle = colour;
  context.stroke();
  context.beginPath();
  context.arc(x, y, 5.5 / sim.scale, 0, Math.PI * 2);
  context.shadowColor = communityColour(link.one.community);
  context.shadowBlur = 16;
  context.fillStyle = colour;
  context.fill();
  context.shadowBlur = 0;
}

function labelHop(sim: Sim, context: CanvasRenderingContext2D, link: SimLink,
                  muted: string): void {
  const mx = (link.one.x + link.two.x) / 2;
  const my = (link.one.y + link.two.y) / 2;
  // Alternating above/below: every zigzag midpoint sits at the same height, so
  // same-side labels on adjacent hops collide.
  const above = (link.hop ?? 0) % 2 === 0;
  context.setLineDash([]);
  context.font = `italic 600 ${11 / sim.scale}px ${MONO}`;
  context.fillStyle = communityColour(link.one.community, 0.95);
  context.textAlign = "center";
  context.fillText(link.via ?? "", mx, my + (above ? -26 : 22) / sim.scale);
  if (link.symbols?.length) {
    context.font = `${10 / sim.scale}px ${MONO}`;
    context.fillStyle = muted;
    context.fillText(`via ${link.symbols.slice(0, 2).join(", ")}`,
                     mx, my + (above ? -10 : 38) / sim.scale);
  }
  context.textAlign = "left";
}

function drawNode(sim: Sim, context: CanvasRenderingContext2D, node: SimNode,
                  text: string): void {
  const hot = sim.selected === node.file || sim.hover === node.file;
  context.beginPath();
  context.arc(node.x, node.y, node.r + (hot ? 1.5 : 0), 0, Math.PI * 2);
  if (node.bubble) {
    context.fillStyle = communityColour(node.community, hot ? 0.5 : 0.3);
    context.fill();
    context.strokeStyle = communityColour(node.community, 0.95);
    context.lineWidth = (hot ? 2.4 : 1.6) / sim.scale;
    context.stroke();
    return;
  }
  if (sim.gods.has(node.file) || node.big) {
    context.shadowColor = communityColour(node.community);
    context.shadowBlur = 14;            // the core files glow: they ARE the map
  }
  context.fillStyle = communityColour(node.community, hot ? 1 : 0.85);
  context.fill();
  context.shadowBlur = 0;
  if (hot) {
    context.strokeStyle = text;
    context.lineWidth = 1.4 / sim.scale;
    context.stroke();
  }
}

function ringActive(sim: Sim, context: CanvasRenderingContext2D, walk: Walk): void {
  const step = walk.steps[walk.at];
  const node = step ? sim.byFile.get(step.file) : undefined;
  if (!node || !step) return;
  context.beginPath();
  context.arc(node.x, node.y, node.r + 6 / sim.scale, 0, Math.PI * 2);
  context.strokeStyle = communityColour(node.community, 0.95);
  context.lineWidth = 2 / sim.scale;
  context.setLineDash([4 / sim.scale, 3 / sim.scale]);
  context.stroke();
  context.setLineDash([]);
  context.textAlign = "center";
  context.font = `600 ${10.5 / sim.scale}px ${MONO}`;
  context.fillStyle = communityColour(node.community, 1);
  context.fillText(step.kind, node.x, node.y - node.r - 12 / sim.scale);
  context.textAlign = "left";
}

function drawLabels(sim: Sim, context: CanvasRenderingContext2D,
                    palette: Palette): void {
  context.textAlign = "center";
  if (sim.mode === "overview") bubbleLabels(sim, context, palette);
  else fileLabels(sim, context, palette);
  context.textAlign = "left";
}

function bubbleLabels(sim: Sim, context: CanvasRenderingContext2D,
                      palette: Palette): void {
  for (const node of sim.nodes) {
    context.font = `600 ${Math.max(11, Math.min(15, node.r / 3.2)) / sim.scale}px ${MONO}`;
    context.fillStyle = palette.text;
    context.fillText(node.label ?? "", node.x, node.y - 2);
    context.font = `${10 / sim.scale}px ${MONO}`;
    context.fillStyle = palette.muted;
    context.fillText(`${node.size} files`, node.x, node.y + 14 / sim.scale);
  }
}

function fileLabels(sim: Sim, context: CanvasRenderingContext2D,
                    palette: Palette): void {
  // These views are small by design, so every node gets its name. On a bigger
  // one only the core, the hovered node and the route keep labels until the
  // reader zooms in — a hundred overlapping filenames is not a label.
  const small = sim.nodes.length <= 60;
  for (const node of sim.nodes) {
    const hot = sim.selected === node.file || sim.hover === node.file;
    const always = small || hot || node.big || sim.gods.has(node.file);
    if (!always && sim.scale < 1.4) continue;
    context.font = `${node.big ? "600 " : ""}${(node.big ? 12 : 10.5) / sim.scale}px ${MONO}`;
    context.fillStyle = hot || node.big ? palette.text : palette.muted;
    context.fillText(node.file.split("/").pop() ?? "",
                     node.x, node.y + node.r + 12 / sim.scale);
  }
}
