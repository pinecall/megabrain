/* The simulation: state, physics, camera. No drawing, no DOM.
 *
 * Force-directed, hand-written, no library. The repulsion runs INSIDE each
 * community rather than globally — the communities already pre-cluster the
 * graph, so the O(n²) sweep a generic layout does is wasted work — and the
 * community centroids repel each other so the clusters separate as wholes.
 *
 * Links and groups hold NODE REFERENCES, never indices into `nodes`. Index
 * arithmetic across four modules is where an off-by-one draws a line between
 * the wrong two files and nobody can see that it is wrong.
 */
export interface SimNode {
  file: string;
  community: number;
  degree: number;
  r: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  fixed: boolean;
  /* A community bubble in overview mode, rather than a file. */
  bubble?: boolean;
  label?: string;
  size?: number;
  /* A route endpoint: always labelled, always glowing. */
  big?: boolean;
}

export interface SimLink {
  one: SimNode;
  two: SimNode;
  semantic: boolean;
  /* Overview: how many file-level dependencies this bubble-to-bubble line
   * stands for, which is its thickness. */
  count?: number;
  /* Path mode: the hop's position, its label, and the TRUE call direction —
   * `from`/`to` come from the hop's own use/def evidence, so they can point
   * against the walk, which is exactly how a meeting looks. */
  hop?: number;
  via?: string;
  symbols?: string[];
  from?: SimNode | undefined;
  to?: SimNode | undefined;
}

export type SimMode = "overview" | "community" | "subgraph" | "path";

export interface Sim {
  nodes: SimNode[];
  links: SimLink[];
  byFile: Map<string, SimNode>;
  groups: SimNode[][];
  gods: Set<string>;
  labels: Record<number, string>;
  mode: SimMode;
  width: number;
  height: number;
  dpr: number;
  alpha: number;
  tx: number;
  ty: number;
  scale: number;
  /* The camera is the user's the moment they touch it. */
  owned: boolean;
  hover: string | null;
  selected: string | null;
}

const V_MAX = 24;

export function tick(sim: Sim): void {
  const alpha = sim.alpha = Math.max(0.011, sim.alpha * 0.985);
  for (const group of sim.groups) repelWithin(group, alpha);
  const centres = sim.groups.map(centroid);
  repelGroups(sim, centres, alpha);
  pullToCentroid(sim, centres, alpha);
  springs(sim, alpha);
  integrate(sim, alpha);
}

function repelWithin(group: SimNode[], alpha: number): void {
  // A big community samples pairs instead of walking all of them: the point is
  // separation, and separation converges long before exactness does.
  const stride = group.length > 260 ? 2 : 1;
  const force = 620 * (1 + Math.sqrt(group.length) / 6);
  for (let a = 0; a < group.length; a += 1) {
    for (let b = a + stride; b < group.length; b += stride) {
      const one = group[a];
      const two = group[b];
      if (one && two) push(one, two, force, alpha);
    }
  }
}

function push(one: SimNode, two: SimNode, force: number, alpha: number): void {
  let dx = one.x - two.x;
  let dy = one.y - two.y;
  let d2 = dx * dx + dy * dy;
  if (d2 < 1) {                       // exactly coincident: nudge them apart
    dx = Math.random() - 0.5;
    dy = Math.random() - 0.5;
    d2 = 1;
  }
  const scaled = Math.min(3, force / d2) * alpha;
  const d = Math.sqrt(d2);
  dx /= d;
  dy /= d;
  if (!one.fixed) { one.vx += dx * scaled; one.vy += dy * scaled; }
  if (!two.fixed) { two.vx -= dx * scaled; two.vy -= dy * scaled; }
}

type Centre = { x: number; y: number; weight: number };

function centroid(group: SimNode[]): Centre {
  let x = 0;
  let y = 0;
  for (const node of group) { x += node.x; y += node.y; }
  const size = Math.max(1, group.length);
  return { x: x / size, y: y / size, weight: group.length };
}

function repelGroups(sim: Sim, centres: Centre[], alpha: number): void {
  for (let a = 0; a < centres.length; a += 1) {
    for (let b = a + 1; b < centres.length; b += 1) {
      const one = centres[a];
      const two = centres[b];
      const first = sim.groups[a];
      const second = sim.groups[b];
      if (!one || !two || !first || !second) continue;
      let dx = one.x - two.x;
      let dy = one.y - two.y;
      const d2 = Math.max(400, dx * dx + dy * dy);
      const d = Math.sqrt(d2);
      const force = Math.min(2.2,
        (24000 * Math.sqrt(Math.min(one.weight, two.weight))) / d2) * alpha;
      dx /= d;
      dy /= d;
      for (const node of first) if (!node.fixed) { node.vx += dx * force; node.vy += dy * force; }
      for (const node of second) if (!node.fixed) { node.vx -= dx * force; node.vy -= dy * force; }
    }
  }
}

function pullToCentroid(sim: Sim, centres: Centre[], alpha: number): void {
  sim.groups.forEach((group, position) => {
    const centre = centres[position];
    if (!centre) return;
    for (const node of group) {
      if (node.fixed) continue;
      node.vx += (centre.x - node.x) * 0.012 * alpha;
      node.vy += (centre.y - node.y) * 0.012 * alpha;
    }
  });
}

function springs(sim: Sim, alpha: number): void {
  for (const link of sim.links) {
    const { one, two } = link;
    const dx = two.x - one.x;
    const dy = two.y - one.y;
    const d = Math.max(1, Math.sqrt(dx * dx + dy * dy));
    const want = sim.mode === "overview" ? one.r + two.r + 70 : link.semantic ? 150 : 70;
    // Gentle on purpose: a stiff spring between two far-apart nodes throws them
    // across the canvas and the layout oscillates instead of settling.
    const force = ((d - want) / d) * (link.semantic ? 0.004 : 0.02) * alpha;
    if (!one.fixed) { one.vx += dx * force; one.vy += dy * force; }
    if (!two.fixed) { two.vx -= dx * force; two.vy -= dy * force; }
  }
}

function integrate(sim: Sim, alpha: number): void {
  const gx = sim.width / 2;
  const gy = sim.height / 2;
  for (const node of sim.nodes) {
    if (node.fixed) continue;
    node.vx += (gx - node.x) * 0.004 * alpha;
    node.vy += (gy - node.y) * 0.004 * alpha;
    node.vx = Math.max(-V_MAX, Math.min(V_MAX, node.vx * 0.82));
    node.vy = Math.max(-V_MAX, Math.min(V_MAX, node.vy * 0.82));
    node.x += node.vx;
    node.y += node.vy;
    if (!isFinite(node.x) || !isFinite(node.y)) {
      // Never let a numerical blowup show as a blank canvas.
      node.x = gx + (Math.random() - 0.5) * 60;
      node.y = gy + (Math.random() - 0.5) * 60;
      node.vx = 0;
      node.vy = 0;
    }
  }
}
