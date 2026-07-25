/* The wire contracts, mirrored from src/megabrain/contracts/.
 *
 * Hand-mirrored rather than generated: a generator is a second build step to
 * keep working, and these shapes change once a phase. What keeps them honest
 * is that the studio is typed against THESE — a field the engine renamed shows
 * up as a compile error here, not as `undefined` in a panel.
 *
 * One rule: never add a field the Python contract does not declare. This file
 * is a mirror; a field invented here is a field the backend never sends.
 */

export interface Span {
  file: string;
  start_line: number;
  end_line: number;
}

export interface ChunkRef extends Span {
  id: number;
  kind: string;
  name: string | null;
  part: string | null;
  text: string;
  breadcrumb: string;
}

export interface ChunkHit extends ChunkRef {
  score: number;
}

export interface SymbolRef {
  name: string;
  kind: string;
  line: number;
  end_line: number;
  signature: string | null;
  doc: string | null;
}

export interface Tier1File {
  file: string;
  score: number;
  chunks: ChunkHit[];
  symbols: SymbolRef[];
  neighbors: string[];
}

export interface Tier2File {
  file: string;
  score: number;
  via_graph: boolean;
  matched: string[];
  doc: string | null;
  best_chunk: ChunkRef | null;
  symbols: SymbolRef[];
}

export interface Bundle {
  query: string;
  repo: string;
  tier1: Tier1File[];
  tier2: Tier2File[];
  flows: unknown[];
  anchors: unknown[];
  ms: number;
}

export interface FileView extends Span {
  text: string;
  symbols: SymbolRef[];
  symbol: string | null;
  stale: boolean;
}

export interface RepoEntry {
  path: string;
  name: string;
  files: number;
  chunks: number;
}

export interface GraphNode {
  file: string;
  community: number;
  degree: number;
  in_degree: number;
}

export interface GraphLink {
  source: string;
  target: string;
  kind: string;
}

export interface Community {
  id: number;
  size: number;
  files: string[];
}

export interface GraphMap {
  repo: string;
  files: number;
  nodes: GraphNode[];
  links: GraphLink[];
  communities: Community[];
  hubs: GraphNode[];
  ms: number;
}

export interface Neighbourhood {
  file: string;
  community: number;
  imports: string[];
  imported_by: string[];
  ms: number;
}

export interface Health {
  ok: boolean;
  version: string;
  repo?: string;
  root?: string;
  files?: number;
  chunks?: number;
  symbols?: number;
  edges?: number;
}

export interface Project {
  repo: string;
  config_file: string;
  queries: string[];
  models: { narrator: string; rerank: string };
  malformed: boolean;
}

export interface Config {
  version: string;
  readonly: boolean;
  rate_limit: number;
  auth: boolean;
}

export interface ApiError {
  error: string;
  code: string;
}
