/* Building DOM without a framework.
 *
 * Four helpers, and one rule that is the reason they exist: nothing here ever
 * assigns innerHTML from data. Every string the engine returns is source code
 * from someone's repository, and a repository is allowed to contain a `<script>`
 * tag — a studio that pastes it into the page executes it.
 */

type Attrs = Record<string, string | ((event: Event) => void)>;

export function el(tag: string, attrs: Attrs = {}, ...children: (Node | string)[]): HTMLElement {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (typeof value === "function") node.addEventListener(key.replace(/^on/, ""), value);
    else if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

/** Replace a node's children. `textContent` for strings, never innerHTML. */
export function fill(target: HTMLElement, ...children: (Node | string)[]): void {
  target.replaceChildren(...children.map(
    (child) => (typeof child === "string" ? document.createTextNode(child) : child)));
}

export function need<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing element #${id}`);
  return found as T;
}

/** A code block with true line numbers, so what is on screen can be quoted. */
export function code(text: string, firstLine: number): HTMLElement {
  const lines = text.split("\n");
  const gutterWidth = String(firstLine + lines.length - 1).length;
  return el("pre", { class: "code" }, ...lines.flatMap((line, offset) => [
    el("span", { class: "ln" }, String(firstLine + offset).padStart(gutterWidth, " ")),
    document.createTextNode(` ${line}\n`),
  ]));
}
