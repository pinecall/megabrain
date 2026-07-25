/* The graph view: the repository as a map you can walk.
 *
 * The hairball objection is real, and the answer is not "draw lists instead" —
 * it is to draw the right thing at each zoom. The overview draws ONE BUBBLE PER
 * COMMUNITY, so a thousand-file repo is a dozen circles whose sizes and links
 * are the shape of the codebase. Click one and its files appear. Search and you
 * get the induced subgraph of a real retrieval. Ask for `a → b` and you get the
 * route, with the code at every hop.
 */
import { api } from "../api.js";
import type { GraphMap, GraphPath, NodeView } from "../contracts.js";
import { el, fill } from "../dom.js";
import { communityPanel, nodePanel, overviewPanel, subgraphPanel } from "../graph/panel.js";
import { routePanel } from "../graph/route.js";
import type { SimMode } from "../graph/sim.js";
import { canvasStage } from "../graph/stage.js";

export interface GraphView {
  root: HTMLElement;
  focus(): void;
  load(): Promise<void>;
}

interface State {
  map?: GraphMap | undefined;
  mode: SimMode;
  community?: number | undefined;
  subgraph?: { query: string; files: { file: string; score: number }[] } | undefined;
  route?: GraphPath | undefined;
  node?: NodeView | undefined;
}

export function graphView(repo: () => string | undefined,
                          onOpen: (file: string, line?: number) => void,
                          onError: (failure: unknown) => void): GraphView {
  const state: State = { mode: "overview" };
  const input = el("input", {
    class: "query-input", type: "search", autocomplete: "off", spellcheck: "false",
    placeholder: "search files or concepts…   or   a -> b   for the route between two",
  }) as HTMLInputElement;
  const panel = el("div", { class: "graph-panel" });
  const stats = el("div", { class: "stats-row" });
  const stage = canvasStage({
    onFile: (file) => void openNode(file),
    onCommunity: (id) => openCommunity(id),
    labelOf: (id) => state.map?.communities.find((one) => one.id === id)?.label
      ?? `Community ${id}`,
    isGod: (file) => Boolean(state.map?.god_nodes.some((god) => god.file === file)),
    openInEditor: (file, line) => onOpen(file, line),
    // The card takes the panel's place while it runs: two columns of code beside
    // each other is neither of them readable.
    onWalk: (running) => panel.classList.toggle("hidden", running),
  });

  const paint = (): void => {
    const map = state.map;
    if (!map) return;
    stage.mount(map, state.mode, {
      community: state.community,
      files: state.subgraph?.files.map((hit) => hit.file),
      route: state.route ?? null,
    });
    fill(panel, ...sidePanel(map));
    fill(stats, el("b", {}, String(map.files)), " files",
         el("div", { class: "sdot" }), el("b", {}, String(map.links.length)), " links",
         el("div", { class: "sdot" }), el("b", {}, `${map.ms}ms`));
  };

  const overview = (): void => {
    state.mode = "overview";
    state.node = undefined;
    state.route = undefined;
    state.subgraph = undefined;
    paint();
  };

  const openCommunity = (id: number): void => {
    state.mode = "community";
    state.community = id;
    state.node = undefined;
    paint();
  };

  const handlers = { openFile: (file: string) => void openNode(file),
                     openCommunity };

  function sidePanel(map: GraphMap): HTMLElement[] {
    if (state.node) return nodePanel(state.node, handlers, overview);
    if (state.mode === "path" && state.route) {
      return routePanel(state.route, {
        openFile: handlers.openFile,
        openAt: (file, line) => onOpen(file, line),
        play: () => {
          if (!stage.play(state.route ?? null)) {
            onError(new Error("no code steps on this route — it is linked by "
                              + "meaning only"));
          }
        },
        back: overview,
      });
    }
    if (state.mode === "community" && state.community != null) {
      return [back(overview), ...communityPanel(map, state.community, handlers)];
    }
    if (state.mode === "subgraph" && state.subgraph) {
      return [back(overview),
              ...subgraphPanel(state.subgraph.query, state.subgraph.files, handlers)];
    }
    return overviewPanel(map, handlers);
  }

  async function openNode(file: string): Promise<void> {
    try {
      state.node = await api.graphNode(file, repo());
      if (state.map) fill(panel, ...sidePanel(state.map));
      stage.select(state.node.file);
    } catch (failure) {
      onError(failure);
    }
  }

  async function run(): Promise<void> {
    const query = input.value.trim();
    if (!query || !state.map) return;
    const arrow = query.includes("->") ? "->" : query.includes("→") ? "→" : null;
    try {
      if (arrow) await routeQuery(query, arrow);
      else await subgraphQuery(query);
    } catch (failure) {
      onError(failure);
    }
  }

  async function routeQuery(query: string, arrow: string): Promise<void> {
    const [source, target] = query.split(arrow).map((side) => side.trim());
    if (!source || !target) return;
    state.route = await api.graphPath(source, target, repo());
    state.mode = "path";
    state.node = undefined;
    state.subgraph = undefined;
    paint();
  }

  /* Free text is REAL retrieval — the same engine as the Search tab — drawn as
   * the induced subgraph. Never "resolve the query to one node": that answers a
   * different question and hides everything else the query matched. */
  async function subgraphQuery(query: string): Promise<void> {
    const bundle = await api.search(query, repo());
    const known = new Set(state.map?.nodes.map((node) => node.file));
    const hits = [...bundle.tier1.map((file) => ({ file: file.file, score: file.score })),
                  ...bundle.tier2.slice(0, 10)
                    .map((file) => ({ file: file.file, score: file.score }))];
    state.subgraph = { query, files: hits.filter((hit) => known.has(hit.file)) };
    state.mode = "subgraph";
    state.node = undefined;
    state.route = undefined;
    paint();
  }

  input.addEventListener("keydown", (event) => {
    if ((event as KeyboardEvent).key === "Enter") void run();
  });

  return {
    root: el("div", { class: "view-wrap graph-view" },
      el("div", { class: "query-bar" }, input, stats),
      el("div", { class: "graph-layout" }, stage.root, panel)),
    focus: () => input.focus(),
    async load(): Promise<void> {
      fill(panel, el("div", { class: "empty" }, el("div", { class: "spinner" }),
                     "building the graph…"));
      try {
        state.map = await api.graph(repo());
        paint();
      } catch (failure) {
        onError(failure);
      }
    },
  };
}

function back(onBack: () => void): HTMLElement {
  return el("button", { class: "chip accent-chip", onclick: onBack },
            "← back to overview");
}
