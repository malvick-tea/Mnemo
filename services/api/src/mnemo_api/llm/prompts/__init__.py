"""Versioned Jinja2 prompt templates.

Every template ends with `_vN.jinja2`. The caller asks for `"rag_answer_v1"`;
this module renders the template and returns both the rendered text and the
fingerprint we stamp on `queries.model_used` / logs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_PROMPTS_DIR = Path(__file__).resolve().parent
_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(default=False),
    undefined=StrictUndefined,
    keep_trailing_newline=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(name: str, /, **vars: Any) -> tuple[str, str]:
    """Render `name.jinja2`. Returns `(rendered_text, fingerprint)`."""
    template = _env.get_template(f"{name}.jinja2")
    text = template.render(**vars)
    return text, name
