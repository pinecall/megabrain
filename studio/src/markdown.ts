/* Markdown, rendered as DOM — never as an HTML string.
 *
 * The walkthrough's fenced blocks hold code spliced from a repository, and a
 * repository is allowed to contain `<script>`. Every markdown library that
 * returns a string puts that string through innerHTML, which executes it. This
 * builds nodes instead, so the code is always text and never markup.
 *
 * Only what the narrator actually emits is supported: headings, paragraphs,
 * fenced code with its file/line caption, inline code, and bold. A fuller
 * renderer is more surface for the same guarantee to leak through.
 */
import { el } from "./dom.js";

export function renderMarkdown(source: string): HTMLElement[] {
  const out: HTMLElement[] = [];
  let paragraph: string[] = [];

  const flush = (): void => {
    if (paragraph.length) out.push(el("p", {}, ...inline(paragraph.join(" "))));
    paragraph = [];
  };

  const lines = source.split("\n");
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index] ?? "";
    if (line.startsWith("```")) {
      flush();
      const [block, next] = fence(lines, index);
      out.push(block);
      index = next;
    } else if (line.startsWith("#")) {
      flush();
      out.push(el("h2", {}, line.replace(/^#+\s*/, "")));
    } else if (!line.trim()) {
      flush();
    } else {
      paragraph.push(line);
    }
  }
  flush();
  return out;
}

function fence(lines: string[], start: number): [HTMLElement, number] {
  const body: string[] = [];
  let index = start + 1;
  for (; index < lines.length && !(lines[index] ?? "").startsWith("```"); index++) {
    body.push(lines[index] ?? "");
  }
  // The caption is the `**\`file\` L10-20**` line the splice writes above every
  // block. Kept with its code rather than as a stray paragraph: a block a
  // reader cannot locate is a quote, not evidence.
  const caption = (lines[start - 2] ?? "").match(/\*\*`([^`]+)`\s*(L\d+-\d+)\*\*/);
  const pre = el("pre", {});
  if (caption) pre.append(el("span", { class: "fh" }, `${caption[1]}  ${caption[2]}`));
  pre.append(document.createTextNode(body.join("\n")));
  return [pre, index];
}

function inline(text: string): (Node | string)[] {
  // The caption line is consumed by `fence`; emitting it again as prose would
  // print the file path twice, once as a heading and once as a stray sentence.
  if (/^\*\*`[^`]+`\s*L\d+-\d+\*\*$/.test(text.trim())) return [];
  const out: (Node | string)[] = [];
  for (const part of text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)) {
    if (part.startsWith("`") && part.endsWith("`")) {
      out.push(el("code", {}, part.slice(1, -1)));
    } else if (part.startsWith("**") && part.endsWith("**")) {
      out.push(el("em", {}, part.slice(2, -2)));
    } else if (part) {
      out.push(part);
    }
  }
  return out;
}
