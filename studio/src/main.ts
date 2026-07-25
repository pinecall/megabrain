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
import { graphView } from "./views/graph.js";
import { openFile } from "./views/files.js";
import { addRepoOverlay } from "./views/adding.js";
import { searchView } from "./views/search.js";
import { applyTheme, currentTheme } from "./theme.js";

let selected: string | undefined;
const repo = (): string | undefined => selected;

function toast(failure: unknown): void {
  const message = failure instanceof ApiFailure
    ? `${failure.message} (${failure.code})` : String(failure);
  const node = el("div", { class: "toast" }, message);
  need("toasts").append(node);
  setTimeout(() => node.remove(), 8000);
}

const show = (file: string): void => { void openFile(file, repo(), toast); };

const views = {
  search: searchView(repo, show, toast),
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
    shell.markRepo(entry.path);
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
  pick(repos[0]!);
  select(shell, "ask");
}

boot().catch(toast);
