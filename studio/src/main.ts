/* Boot: pick a repo, wire the panels, keep one error path.
 *
 * The whole studio is three panels over one API. State is the selected repo and
 * nothing else — a UI whose state is a question already asked does not need a
 * store, and one that grows a store grows two sources of truth for what is on
 * screen.
 */
import { ApiFailure, api } from "./api.js";
import type { RepoEntry } from "./contracts.js";
import { el, fill, need } from "./dom.js";
import { filePanel } from "./files.js";
import { graphPanel } from "./graph.js";
import { searchPanel } from "./search.js";

let selected: string | undefined;

const repo = (): string | undefined => selected;
const view = need("view");
const status = need("status");
const repoList = need("repos");
const input = need<HTMLInputElement>("q");

const files = filePanel(view, repo, (file) => guard(() => graph.node(file)));
const graph = graphPanel(view, repo, (file) => guard(() => files.open(file)));
const search = searchPanel(view, repo,
  (file, symbol) => guard(() => files.open(file, symbol)));

/** One error path for every action: a panel that renders its own failure
 *  renders it differently from its neighbours. */
async function guard(action: () => Promise<void>): Promise<void> {
  try {
    await action();
  } catch (failure) {
    const message = failure instanceof ApiFailure
      ? `${failure.message} (${failure.code})`
      : String(failure);
    fill(view, el("p", { class: "warn" }, message));
  }
}

function selectRepo(entry: RepoEntry, button: HTMLElement): void {
  selected = entry.path;
  repoList.querySelectorAll(".on").forEach((other) => other.classList.remove("on"));
  button.classList.add("on");
  status.textContent = `${entry.name} · ${entry.files} files · ${entry.chunks} chunks`;
}

async function boot(): Promise<void> {
  const [config, listed] = await Promise.all([api.config(), api.repos()]);
  status.textContent = `megabrain ${config.version}`;
  if (!listed.repos.length) {
    fill(view, el("p", { class: "dim" },
      "No indexed repository on this machine yet. Run `megabrain index <path>` "
      + "and reload."));
    return;
  }
  fill(repoList, ...listed.repos.map((entry) => {
    const button = el("button", { class: "repo" }, entry.name);
    button.addEventListener("click", () => selectRepo(entry, button));
    return button;
  }));
  const first = listed.repos[0];
  const firstButton = repoList.firstElementChild;
  if (first && firstButton instanceof HTMLElement) selectRepo(first, firstButton);
  fill(view, el("p", { class: "dim" }, "Ask something about this repository."));
}

need("go").addEventListener("click", () => {
  if (input.value.trim()) void guard(() => search.run(input.value.trim()));
});
input.addEventListener("keydown", (event) => {
  if ((event as KeyboardEvent).key === "Enter" && input.value.trim()) {
    void guard(() => search.run(input.value.trim()));
  }
});
need("graph").addEventListener("click", () => void guard(() => graph.overview()));

void guard(boot);
