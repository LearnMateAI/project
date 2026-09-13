"""
The state that flows between nodes across one turn.

In LangGraph a node does not mutate state; it returns a dict of the keys it wants to
change, and the framework merges that into the running state. So every field below is
written by exactly one node and read by the ones downstream of it.

By default a returned key *overwrites* whatever was there. A field can opt out of that
with `Annotated[type, reducer]`, which tells LangGraph to combine the old and new values
instead. `attempts` is the only field here that does -- see the note on it below.
"""

from typing import Any, Dict, List, Optional

from typing_extensions import Annotated, TypedDict


def _append(left: List, right: List) -> List:
    """
    Reducer for `attempts`: concatenate instead of overwrite.

    Both sides are defaulted to `[]` because on the first node to write the key the
    left side is still absent (None), not an empty list.
    """
    return (left or []) + (right or [])


class ChatState(TypedDict, total=False):
    """
    One turn's working memory.

    `total=False` means every key is optional, which is what lets nodes return partial
    dicts and lets `ChatAgent.ask` seed only the fields it actually knows up front.
    """

    # --- Inputs: set by ChatAgent.ask before the graph runs, never changed after ------
    query: str                      # what the user actually typed, verbatim
    session_id: str                 # conversation key; history is stored under it
    user_id: str                    # whose conversation it is; stored on every turn
    doc_id: Any                     # restricts retrieval to one ingested PDF (None = all)
    history: List[Dict[str, str]]   # prior turns, as [{"role": ..., "content": ...}]
    threshold: int                  # score out of 100 the judge must see to pass
    max_attempts: int               # total generations allowed, including the first
    evaluate: bool                  # False skips the judge entirely (fast/offline mode)
    verbose: bool                   # False silences the progress logging
    persist: bool                   # False runs the turn without saving it to Mongo
    on_progress: Any                # optional callable(message); set when run on a job
    on_token: Any                   # optional callable(text_so_far); receives the reply
                                    #   as it is generated, for streaming it to a client
    on_reply: Any                   # optional callable(text, attempt); fires once a whole
                                    #   candidate reply exists, before the judge sees it --
                                    #   the point at which there is something worth reading
    model_id: Optional[str]         # optional registry id; omitted uses .env default
    retrieval_mix: Optional[Dict]   # ANN / BM25 / both counts from hybrid retrieve
    timings: Optional[Dict]         # rewrite_ms / retrieve_ms / generate_ms / judge_ms / model_load_ms

    # --- Written by rewrite ----------------------------------------------------------
    standalone_query: str           # the query with pronouns resolved; what we embed

    # --- Written by retrieve ---------------------------------------------------------
    contexts: List[Any]             # retrieved chunks as LangChain Documents; [] in general mode
    scores: List[float]             # cosine similarity per chunk, aligned with `contexts`
    mode: str                       # "pdf" or "general" -- decided by score, not by the model
    top_score: float                # best similarity seen; the number the mode was decided on

    # --- Written by generate / evaluate (the retry loop) ------------------------------
    attempt: int                    # 1-based counter of generations so far
    reply: str                      # the current candidate answer; overwritten on retry
    critique: Optional[str]         # judge's fix instruction, fed into the next generation
    passed: bool                    # did the latest reply clear the threshold
    verdict: Optional[Dict]         # the judge's full structured result for the latest reply

    # The one accumulating field. `reply` keeps only the newest text, but `attempts`
    # keeps every version and its verdict, so a caller can show the whole retry history.
    attempts: Annotated[List[Dict], _append]
