"""Import/call edges: one module per language, plus what they share.

The shape `CLAUDE.md` §5 promised for phase 6 (`indexing/edges/<lang>.py`) and
never got — eight files that belong together were sitting among the phases and
the registry, so "how does an edge get extracted" meant reading the whole
package.

Edges are ANNOTATION data, never ranking data (hard rule #3), and every extractor
is deterministic. A language without one still gets symbols, chunks and the
file-skeleton signal, so adding an extractor is additive by construction.
"""

from __future__ import annotations

from .pins import PIN_SCHEMA, write_pin_edges
from .python import ModuleIndex, module_index, python_edges
from .typescript import TsFiles, ts_edges, ts_files

__all__ = ["ModuleIndex", "module_index", "python_edges",
           "TsFiles", "ts_edges", "ts_files",
           "write_pin_edges", "PIN_SCHEMA"]
