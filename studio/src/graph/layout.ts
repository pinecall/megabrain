/* Building the simulation for one mode.
 *
 * This is the module that answers the hairball objection, and it answers it by
 * NOT drawing the repository. The overview draws one bubble per community — a
 * dozen circles whose size is the cluster's size and whose lines are how many
 * dependencies cross between them. A reader sees the shape of the codebase at a
 * glance and clicks into the part they care about; only then are files drawn,
 * and by then there are twenty of them rather than twelve hundred.
 *
 * Four modes, one shape: overview (bubbles), community (one cluster's files),
 * subgraph (a search result's files), path (a route, laid out as a zigzag).
 */
import type { GraphMap, GraphPath } from "../contracts.js";
import { layoutRoute } from "./camera.js";
import type { Sim, SimLink, SimMode, SimNode } from "./sim.js";

export interface Frame {
  width: number;
  height: number;
  dpr: number;
}

export interface Options {
  community?: number | undefined;
  files?: string[] | undefined;
  route?: GraphPath | null | undefined;
}

export function buildSim(view: GraphMap, mode: SimMode, frame: Frame,
                         options: Options): Sim {
  const built = mode === "overview" ? bubbles(view, frame)
    : mode === "path" ? route(view, options.route ?? null, frame)
    : files(view, wanted(view, mode, options), frame);
  const byFile = new Map(built.nodes.map((node) => [node.file, node]));
  const sim: Sim = {
    ...built, byFile, mode,
    groups: group(built.nodes),
    gods: new Set(view.god_nodes.map((god) => god.file)),
    labels: Object.fromEntries(view.communities.map((one) => [one.id, one.label])),
    width: frame.width, height: frame.height, dpr: frame.dpr,
    alpha: mode === "path" ? 0 : 1,     // a laid-out route needs no simulation
    tx: 0, ty: 0, scale: 1, owned: false, hover: null, selected: null,
  };
  layoutRoute(sim);
  return sim;
}

function wanted(view: GraphMap, mode: SimMode, options: Options): Set<string> {
  if (mode === "community" && options.community != null) {
    const found = view.communities.find((one) => one.id === options.community);
    return new Set(found ? found.files : []);
  }
  return new Set(options.files ?? []);
}

function bubbles(view: GraphMap, frame: Frame): { nodes: SimNode[]; links: SimLink[] } {
  // Single-file communities are left out: a lone dot with a label is noise on a
  // map whose job is showing the parts that have internal life. The panel lists
  // them, so nothing is hidden — just not drawn.
  const multi = view.communities.filter((community) => community.size > 1);
  const nodes = multi.map((community) => ({
    file: `com:${community.id}`, community: community.id, degree: community.size,
    size: community.size, label: community.label, bubble: true,
    r: 22 + Math.min(60, Math.sqrt(community.size) * 7),
    x: frame.width / 2 + (Math.random() - 0.5) * 120,
    y: frame.height / 2 + (Math.random() - 0.5) * 120,
    vx: 0, vy: 0, fixed: false,
  }));
  return { nodes, links: crossLinks(view, nodes) };
}

function crossLinks(view: GraphMap, bubbleNodes: SimNode[]): SimLink[] {
  const communityOf = new Map(view.nodes.map((node) => [node.file, node.community]));
  const byCommunity = new Map(bubbleNodes.map((node) => [node.community, node]));
  const counted = new Map<string, { one: SimNode; two: SimNode; count: number }>();
  for (const link of view.links) {
    const first = byCommunity.get(communityOf.get(link.source) ?? -1);
    const second = byCommunity.get(communityOf.get(link.target) ?? -1);
    if (!first || !second || first === second) continue;
    const key = [first.community, second.community].sort().join("-");
    const seen = counted.get(key);
    if (seen) seen.count += 1;
    else counted.set(key, { one: first, two: second, count: 1 });
  }
  return [...counted.values()].map((entry) => ({ ...entry, semantic: false }));
}

function files(view: GraphMap, keep: Set<string>,
               frame: Frame): { nodes: SimNode[]; links: SimLink[] } {
  const shown = view.nodes.filter((node) => keep.has(node.file));
  const radius = Math.min(frame.width, frame.height) * 0.34;
  const nodes = shown.map((node, position) => {
    const angle = (position / Math.max(1, shown.length)) * Math.PI * 2;
    return {
      file: node.file, community: node.community, degree: node.degree,
      r: 4 + Math.min(9, Math.sqrt(node.degree) * 1.6),
      x: frame.width / 2 + radius * Math.cos(angle),
      y: frame.height / 2 + radius * Math.sin(angle),
      vx: 0, vy: 0, fixed: false,
    };
  });
  const byFile = new Map(nodes.map((node) => [node.file, node]));
  const links = view.links.flatMap((link) => {
    const one = byFile.get(link.source);
    const two = byFile.get(link.target);
    return one && two ? [{ one, two, semantic: link.kind === "semantic" }] : [];
  });
  return { nodes, links };
}

function route(view: GraphMap, path: GraphPath | null,
               frame: Frame): { nodes: SimNode[]; links: SimLink[] } {
  const hops = path?.found ? path.hops : [];
  const nodes = hops.map((hop) => {
    const known = view.nodes.find((node) => node.file === hop.file);
    return {
      file: hop.file, community: known ? known.community : 0, degree: 0,
      r: 9, big: true, x: 0, y: frame.height / 2, vx: 0, vy: 0, fixed: true,
    };
  });
  const byFile = new Map(nodes.map((node) => [node.file, node]));
  const links = hops.slice(1).flatMap((hop, step) => {
    const one = nodes[step];
    const two = nodes[step + 1];
    if (!one || !two) return [];
    return [{
      one, two, hop: step, semantic: /^semantic/.test(hop.via),
      via: hop.via, symbols: hop.symbols ?? [],
      // The TRUE call direction, from the hop's own evidence — the arrowheads
      // are what let a meeting read as `→ ←` at a glance.
      from: hop.code?.use ? byFile.get(hop.code.use.file) : undefined,
      to: hop.code?.definition ? byFile.get(hop.code.definition.file) : undefined,
    }];
  });
  return { nodes, links };
}

function group(nodes: SimNode[]): SimNode[][] {
  const grouped = new Map<string, SimNode[]>();
  nodes.forEach((node, position) => {
    // A bubble is its own group: bubbles must repel each OTHER, and putting them
    // all in one community group would only pull them together.
    const key = node.bubble ? `b${position}` : String(node.community);
    const found = grouped.get(key);
    if (found) found.push(node);
    else grouped.set(key, [node]);
  });
  return [...grouped.values()];
}
