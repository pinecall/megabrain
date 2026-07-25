"""GET /project — what a repository decided about itself.

Separate from `/config`, which describes the DEPLOYMENT. This is per repo: the
questions it wants asked of it, and the models it narrates and judges with.
"""

from __future__ import annotations

from ...._errors import MegabrainError
from ....project import CONFIG_FILE, load_project
from ....usecases import resolve_root, starters_for
from ..messages import Reply, Request
from ..replies import from_engine, json_reply

__all__ = ["project_route"]


def project_route(request: Request) -> Reply:
    try:
        root = resolve_root(request.repo())
    except MegabrainError as err:
        return from_engine(err)
    project = load_project(root)
    # Derived from the index when the repo declares none — and the SOURCE is
    # reported, so the studio can label a guess as a guess instead of passing
    # it off as something the repository asked for.
    starters = starters_for(root)
    return json_reply({
        "repo": root.name,
        "config_file": CONFIG_FILE,
        "queries": starters["queries"],
        "queries_source": starters["source"],
        "models": {"narrator": project.narrator_model,
                   "rerank": project.rerank_model},
        # Said out loud: a fallback that looks like "no config" is how somebody
        # edits a file for an hour and never learns it was never parsed.
        "malformed": project.malformed,
    })
