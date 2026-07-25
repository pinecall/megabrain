/* Boot: the shell, three views, one error path.
 *
 * State is the selected repo and the active tab. A UI whose state is a
 * question already asked does not need a store, and one that grows a store
 * grows a second source of truth for what is on screen.
 */
import { ApiFailure, api } from "./api.js";
import type { RepoEntry } from "./contracts.js";
import { el, fill, need } from "./dom.js";
import { mountShell, type Shell, type TabName } from "./shell.js";
import { askView } from "./views/ask.js";
import { briefView } from "./views/brief.js";
import { graphView } from "./views/graph.js";
import { openFile } from "./views/files.js";
import { addRepoOverlay } from "./views/adding.js";
import { searchView } from "./views/search.js";
import { applyTheme, currentTheme } from "./theme.js";

let selected: string | undefined;
const repo = (): string | undefined => selected;

const LAST_REPO = "mb-last-repo";

function toast(failure: unknown): void {
  const message = failure instanceof ApiFailure
    ? `${failure.message} (${failure.code})` : String(failure);
  const node = el("div", { class: "toast" }, message);
  need("toasts").append(node);
  setTimeout(() => node.remove(), 8000);
}

const show = (file: string, line?: number): void => {
  void openFile(file, repo(), toast, line);
};

const views = {
  search: searchView(repo, show, toast),
  brief: briefView(repo, show, toast),
  ask: askView(repo, toast),
  graph: graphView(repo, show, toast),
};

function select(shell: Shell, tab: TabName): void {
  shell.select(tab);
  fill(shell.viewport, views[tab].root);
  views[tab].focus?.();
  if (tab === "graph") void views.graph.load();
}

async function refreshRail(shell: Shell, pick: (entry: RepoEntry) => void): Promise<void> {
  const { repos } = await api.repos();
  shell.setRepos(repos, pick);
}


async function boot(): Promise<void> {
  applyTheme(currentTheme());   // before first paint: no dark flash for a light user
  const host = need("app");
  const config = await api.config();
  let pick: (entry: RepoEntry) => void = () => {};
  const shell = mountShell(host, config,
    /* "Index a repo" opens the ADD flow — a path, a census, then indexing.
     * It used to re-index whatever was selected, which is neither what the
     * label says nor what anyone with one repository already indexed wants. */
    () => addRepoOverlay(repo(), () => void refreshRail(shell, pick), toast),
    () => toast("settings: coming with phase 16"));
  shell.onTab((tab) => select(shell, tab));

  const { repos } = await api.repos();
  if (!repos.length) {
    fill(shell.viewport, el("div", { class: "empty" },
      el("div", {}, "No indexed repository on this machine."),
      el("div", { class: "mono", style: "font-size:11.5px" },
         "megabrain index <path>")));
    return;
  }
  pick = (entry: RepoEntry): void => {
    selected = entry.path;
    localStorage.setItem(LAST_REPO, entry.path);
    shell.markRepo(entry.path);
    // Every view holding a per-repo strip re-reads it: the suggestions used to
    // load once at construction and then showed the first repo's questions for
    // the rest of the session.
    for (const view of Object.values(views)) view.refresh();
    shell.setCrumb(entry.name, `${entry.files} files · ${entry.chunks} chunks`);
    // Asked once per selection, never per query: it hashes every file. The
    // answer is shown, and the decision to re-index stays with the reader —
    // a search that silently spent a minute and some money because a file
    // changed is a search nobody can predict the cost of.
    void api.health(entry.path, true).then((health) => {
      if (health.stale) shell.setStale(health.freshness ?? "index is behind disk");
    }).catch(() => {});
  };
  shell.setRepos(repos, pick);
  /* LAST CHOICE first, then the biggest index. Ranking by size alone kept
   * selecting whichever repo happened to be largest — a corpus root nobody was
   * working on — so every reload threw away the reader's actual choice. An
   * empty index is never the default: it answers every query with nothing. */
  const usable = repos.filter((entry) => entry.chunks > 0);
  const pool = usable.length ? usable : repos;
  const remembered = pool.find((entry) => entry.path === localStorage.getItem(LAST_REPO));
  pick(remembered ?? [...pool].sort((one, two) => two.chunks - one.chunks)[0]!);
  select(shell, "ask");
}

boot().catch(toast);
