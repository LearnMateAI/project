"""
Reading JSON back out of a model reply.

The safety net under the unconstrained path. When grammar-constrained decoding is
available the output is already clean and this is a plain `json.loads`; when it is not --
an older llama-cpp build, a server without schema support -- the model tends to wrap the
JSON in a code fence or a sentence of preamble, and this is what recovers it.
"""

import json
import re
from typing import Any


def parse_json_reply(raw: str) -> Any:
    """
    Parse a model reply that is supposed to be JSON.

    Raises ValueError when there is nothing parseable. That is deliberate: callers treat
    it as a failed attempt and retry, which is far better than shipping a placeholder
    object downstream and having it surface as an empty quiz three steps later.
    """
    # Already-parsed input passes straight through, so a caller need not care whether the
    # backend handed back text or a structure.
    if isinstance(raw, (dict, list)):
        return raw

    text = (raw or "").strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass

    # Strip a ```json fence if one is present, then take the outermost braces/brackets --
    # which is what survives a model that introduced its answer before giving it.
    fenced = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"[\[{].*[\]}]", fenced, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            pass

    # Truncated: the full reply can be thousands of tokens, and the opening is enough to
    # see what went wrong.
    raise ValueError(f"Could not parse model output as JSON: {text[:200]}")
