"""BrowserSession-driven NotebookLM UI operations for current SP-C2 runtime."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ._errors import (
    NotebookLMExtractionError,
    NotebookLMInputError,
    NotebookLMLoginRequiredError,
    NotebookLMSelectorError,
    NotebookLMSessionContractError,
    NotebookLMTimeoutError,
    NotebookLMUnexpectedStateError,
)
from ._protocols import BrowserSession
from ._runlog import emit_event, redact_str
from ._selectors import SelectorStore
from ._types import NormalizedSource, OperationEvent

NOTEBOOK_URL_TEMPLATE = "https://notebooklm.google.com/notebook/{notebook_id}"
_REQUIRED_SESSION_METHODS = ("navigate", "eval", "click", "type_text")
_NOTEBOOK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,256}$")


def push_sources(
    session: BrowserSession,
    notebook_id: str,
    sources: list[dict],
    *,
    timeout_s: int = 60,
) -> list[str]:
    """Push URL/text sources into NotebookLM and return local ``source_...`` refs."""

    _ensure_session_contract(session)
    notebook_id = _validate_notebook_id(notebook_id)
    timeout_s = _validate_timeout(timeout_s)
    normalized_sources = _validate_sources(sources)
    selectors = _load_selectors()
    emit_event(session, OperationEvent("push_sources", "started", notebook_id))
    source_refs: list[str] = []
    try:
        _open_notebook(session, notebook_id, timeout_s, selectors)
        for index, source in enumerate(normalized_sources, start=1):
            _add_one_source(session, source, selectors, timeout_s)
            source_refs.append(_source_ref(notebook_id, source, index))
        emit_event(session, OperationEvent("push_sources", "succeeded", notebook_id, source_refs=tuple(source_refs)))
        return source_refs
    except Exception as exc:
        emit_event(session, OperationEvent("push_sources", "failed", notebook_id, message=str(exc), source_refs=tuple(source_refs)))
        if isinstance(exc, (NotebookLMInputError, NotebookLMLoginRequiredError, NotebookLMSelectorError, NotebookLMSessionContractError, NotebookLMTimeoutError, NotebookLMUnexpectedStateError, NotebookLMExtractionError)):
            raise
        raise NotebookLMUnexpectedStateError(f"Failed to push NotebookLM sources: {redact_str(str(exc))}") from exc


def pull_briefing(
    session: BrowserSession,
    notebook_id: str,
    *,
    timeout_s: int = 120,
) -> str:
    """Pull the visible NotebookLM Briefing Doc text or raise a typed failure."""

    _ensure_session_contract(session)
    notebook_id = _validate_notebook_id(notebook_id)
    timeout_s = _validate_timeout(timeout_s)
    selectors = _load_selectors()
    emit_event(session, OperationEvent("pull_briefing", "started", notebook_id))
    try:
        _open_notebook(session, notebook_id, timeout_s, selectors)
        _optional_click(session, selectors, "briefing_generate_button", timeout_s=min(timeout_s, 10))
        text = _read_visible_text(session, selectors, "briefing_content", timeout_s)
        if not text:
            _optional_click(session, selectors, "briefing_refresh_button", timeout_s=min(timeout_s, 10))
            text = _read_visible_text(session, selectors, "briefing_content", timeout_s)
        if not text:
            raise NotebookLMTimeoutError(
                "NotebookLM Briefing Doc did not produce visible text before timeout. "
                "Confirm user authorization, source readiness, and selector freshness."
            )
        artifact_ref = _artifact_ref(notebook_id, "briefing")
        emit_event(session, OperationEvent("pull_briefing", "succeeded", notebook_id, artifact_refs=(artifact_ref,)))
        return text
    except Exception as exc:
        emit_event(session, OperationEvent("pull_briefing", "failed", notebook_id, message=str(exc)))
        if isinstance(exc, (NotebookLMLoginRequiredError, NotebookLMTimeoutError, NotebookLMExtractionError, NotebookLMSelectorError, NotebookLMSessionContractError, NotebookLMInputError)):
            raise
        raise NotebookLMUnexpectedStateError(f"Failed to pull NotebookLM Briefing Doc: {redact_str(str(exc))}") from exc


def pull_faq(
    session: BrowserSession,
    notebook_id: str,
    *,
    timeout_s: int = 120,
) -> list[dict]:
    """Pull NotebookLM FAQ as ``[{"q": str, "a": str}]`` dictionaries."""

    _ensure_session_contract(session)
    notebook_id = _validate_notebook_id(notebook_id)
    timeout_s = _validate_timeout(timeout_s)
    selectors = _load_selectors()
    emit_event(session, OperationEvent("pull_faq", "started", notebook_id))
    try:
        _open_notebook(session, notebook_id, timeout_s, selectors)
        _optional_click(session, selectors, "faq_generate_button", timeout_s=min(timeout_s, 10))
        _wait_for_present(session, selectors.candidates("faq_item"), label="FAQ items", timeout_s=timeout_s)
        raw = _eval(session, _script_extract_faq(selectors), timeout_s=timeout_s)
        faq = parse_faq(raw)
        if not faq:
            raise NotebookLMExtractionError("NotebookLM FAQ was visible but could not be parsed. Update FAQ selectors.")
        artifact_ref = _artifact_ref(notebook_id, "faq")
        emit_event(session, OperationEvent("pull_faq", "succeeded", notebook_id, artifact_refs=(artifact_ref,)))
        return faq
    except Exception as exc:
        emit_event(session, OperationEvent("pull_faq", "failed", notebook_id, message=str(exc)))
        if isinstance(exc, (NotebookLMLoginRequiredError, NotebookLMTimeoutError, NotebookLMExtractionError, NotebookLMSelectorError, NotebookLMSessionContractError, NotebookLMInputError)):
            raise
        raise NotebookLMUnexpectedStateError(f"Failed to pull NotebookLM FAQ: {redact_str(str(exc))}") from exc


def parse_faq(raw: object) -> list[dict]:
    """Normalize FAQ data returned from DOM extraction or a fallback text block."""

    if raw is None:
        return []
    if isinstance(raw, list):
        parsed: list[dict] = []
        for item in raw:
            if isinstance(item, dict):
                q = str(item.get("q") or item.get("question") or "").strip()
                a = str(item.get("a") or item.get("answer") or "").strip()
                if q and a:
                    parsed.append({"q": q, "a": a})
            elif isinstance(item, str):
                parsed.extend(parse_faq(item))
        return parsed
    if not isinstance(raw, str):
        raise NotebookLMExtractionError(f"FAQ extraction returned unsupported type: {type(raw).__name__}.")
    text = raw.strip()
    if not text:
        return []
    qa_pattern = re.compile(
        r"(?:^|\n)\s*(?:[-*]\s*)?(?:\*\*)?(?:Q(?:uestion)?\s*\d*|Q\d+)[:.)-]\s*(?:\*\*)?\s*(?P<q>.+?)\n"
        r"\s*(?:[-*]\s*)?(?:\*\*)?(?:A(?:nswer)?\s*\d*|A\d+)[:.)-]\s*(?:\*\*)?\s*(?P<a>.+?)(?=\n\s*(?:[-*]\s*)?(?:\*\*)?(?:Q(?:uestion)?\s*\d*|Q\d+)[:.)-]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return [
        {"q": _cleanup_text(match.group("q")), "a": _cleanup_text(match.group("a"))}
        for match in qa_pattern.finditer(text)
        if _cleanup_text(match.group("q")) and _cleanup_text(match.group("a"))
    ]


def _ensure_session_contract(session: object) -> None:
    missing = [name for name in _REQUIRED_SESSION_METHODS if not callable(getattr(session, name, None))]
    if missing:
        raise NotebookLMSessionContractError(
            "BrowserSession is missing required SP-C2 methods: "
            + ", ".join(missing)
            + ". SP-H expects navigate, eval, click(x,y), and type_text(text)."
        )


def _validate_timeout(timeout_s: int) -> int:
    if not isinstance(timeout_s, int) or timeout_s <= 0:
        raise NotebookLMInputError("timeout_s must be a positive integer number of seconds.")
    return timeout_s


def _validate_notebook_id(notebook_id: str) -> str:
    if not isinstance(notebook_id, str) or not notebook_id.strip():
        raise NotebookLMInputError("notebook_id must be a non-empty NotebookLM notebook ID.")
    value = notebook_id.strip()
    if value.startswith(("http://", "https://")) or "/" in value:
        raise NotebookLMInputError("notebook_id must be the NotebookLM notebook ID only, not a full URL.")
    if not _NOTEBOOK_ID_RE.fullmatch(value):
        raise NotebookLMInputError("notebook_id may contain only letters, numbers, underscores, and hyphens.")
    return value


def _validate_sources(sources: list[dict]) -> list[NormalizedSource]:
    if not isinstance(sources, list) or not sources:
        raise NotebookLMInputError("sources must be a non-empty list of dictionaries.")
    normalized: list[NormalizedSource] = []
    for index, item in enumerate(sources, start=1):
        if not isinstance(item, dict):
            raise NotebookLMInputError(f"sources[{index}] must be a dictionary.")
        has_url = "url" in item
        has_text = "text" in item
        if has_url == has_text:
            raise NotebookLMInputError(f"sources[{index}] must contain exactly one of 'url' or 'text'.")
        if has_url:
            url = item.get("url")
            if not isinstance(url, str) or not url.strip():
                raise NotebookLMInputError(f"sources[{index}]['url'] must be a non-empty string.")
            parsed = urlparse(url.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise NotebookLMInputError(f"sources[{index}]['url'] must be an http(s) URL.")
            normalized.append(NormalizedSource("url", url.strip(), _optional_title(item)))
        else:
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise NotebookLMInputError(f"sources[{index}]['text'] must be a non-empty string.")
            normalized.append(NormalizedSource("text", text.strip(), _optional_title(item)))
    return normalized


def _optional_title(item: dict) -> str | None:
    title = item.get("title")
    if title is None:
        return None
    if not isinstance(title, str) or not title.strip():
        raise NotebookLMInputError("source title must be a non-empty string when provided.")
    return title.strip()


def _open_notebook(session: BrowserSession, notebook_id: str, timeout_s: int, selectors: SelectorStore) -> None:
    session.navigate(NOTEBOOK_URL_TEMPLATE.format(notebook_id=notebook_id), timeout_s=timeout_s)
    if _login_required(session, selectors, timeout_s=min(timeout_s, 15)):
        raise NotebookLMLoginRequiredError(
            "NotebookLM requires manual user action (login, MFA, CAPTCHA, terms prompt, or account gate). "
            "SP-H will not bypass access controls; complete the step in the SP-C2 browser session and retry."
        )


def _login_required(session: BrowserSession, selectors: SelectorStore, timeout_s: int) -> bool:
    script = "/* notebooklm_bridge:login_required */\n" + _script_any_present(
        selectors.candidates("login_required_signal"), marker="login_required"
    )
    try:
        return bool(_eval(session, script, timeout_s=timeout_s))
    except Exception as exc:
        raise NotebookLMUnexpectedStateError(
            f"Could not inspect NotebookLM login state through BrowserSession.eval: {redact_str(str(exc))}"
        ) from exc


def _add_one_source(session: BrowserSession, source: NormalizedSource, selectors: SelectorStore, timeout_s: int) -> None:
    _click_key(session, selectors, "add_source_button", timeout_s=timeout_s)
    if source.kind == "url":
        _click_key(session, selectors, "source_url_tab", timeout_s=timeout_s)
        _click_key(session, selectors, "source_url_input", timeout_s=timeout_s)
        session.type_text(source.content, timeout_s=timeout_s)
    else:
        _click_key(session, selectors, "source_text_tab", timeout_s=timeout_s)
        if source.title:
            _click_key(session, selectors, "source_title_input", timeout_s=timeout_s)
            session.type_text(source.title, timeout_s=timeout_s)
        _click_key(session, selectors, "source_text_input", timeout_s=timeout_s)
        session.type_text(source.content, timeout_s=timeout_s)
    _click_key(session, selectors, "source_submit_button", timeout_s=timeout_s)
    _wait_for_present(session, selectors.candidates("source_ready_indicator"), label="source readiness", timeout_s=timeout_s)


def _optional_click(session: BrowserSession, selectors: SelectorStore, key: str, *, timeout_s: int) -> None:
    with suppress(Exception):
        _click_key(session, selectors, key, timeout_s=timeout_s)


def _click_key(session: BrowserSession, selectors: SelectorStore, key: str, *, timeout_s: int) -> None:
    point = _resolve_target(session, selectors.candidates(key), key, timeout_s=timeout_s)
    session.click(float(point["x"]), float(point["y"]), timeout_s=timeout_s)


def _resolve_target(session: BrowserSession, candidates: list[str], label: str, *, timeout_s: int) -> dict[str, float]:
    deadline = time.monotonic() + timeout_s
    last: Any = None
    while True:
        raw = _eval(session, _script_resolve_target(candidates, marker=label), timeout_s=min(timeout_s, 5))
        last = raw
        if isinstance(raw, dict) and raw.get("found") and isinstance(raw.get("x"), (int, float)) and isinstance(raw.get("y"), (int, float)):
            return {"x": float(raw["x"]), "y": float(raw["y"])}
        if time.monotonic() >= deadline:
            raise NotebookLMTimeoutError(f"Timed out resolving NotebookLM target '{label}'. Update selectors.json.")
        time.sleep(0.05)


def _wait_for_present(session: BrowserSession, candidates: list[str], *, label: str, timeout_s: int) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        if _eval(session, _script_any_present(candidates, marker=label), timeout_s=min(timeout_s, 5)):
            return
        if time.monotonic() >= deadline:
            raise NotebookLMTimeoutError(f"Timed out waiting for NotebookLM {label}. Check authorization and selectors.")
        time.sleep(0.05)


def _read_visible_text(session: BrowserSession, selectors: SelectorStore, key: str, timeout_s: int) -> str:
    _wait_for_present(session, selectors.candidates(key), label=key, timeout_s=timeout_s)
    raw = _eval(session, _script_extract_text(selectors.candidates(key), marker=key), timeout_s=timeout_s)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise NotebookLMExtractionError(f"Expected {key} extraction to return str, got {type(raw).__name__}.")
    return _cleanup_text(raw)


def _eval(session: BrowserSession, script: str, *, timeout_s: int) -> Any:
    try:
        return session.eval(script, timeout_s=timeout_s)
    except TypeError:
        return session.eval(script, timeout_s=timeout_s)


def _load_selectors() -> SelectorStore:
    override = os.environ.get("NOETICBRAID_NOTEBOOKLM_SELECTORS")
    if override:
        return SelectorStore.load(Path(override))
    return SelectorStore.load_default()


def _script_any_present(candidates: list[str], *, marker: str) -> str:
    return f"""
/* notebooklm_bridge:any_present:{marker} */
(() => {{
  const candidates = {json.dumps(candidates)};
  const bodyText = () => (document.body && document.body.innerText || '');
  const textVisible = (needle) => bodyText().toLowerCase().includes(String(needle).toLowerCase());
  const cssVisible = (selector) => {{ try {{ return Boolean(document.querySelector(selector)); }} catch (_err) {{ return false; }} }};
  return candidates.some((candidate) => {{
    if (candidate.startsWith('text=')) return textVisible(candidate.slice(5));
    const hasText = candidate.match(/:has-text\\(['\"](.+?)['\"]\\)/);
    if (hasText) return textVisible(hasText[1]);
    return cssVisible(candidate);
  }});
}})();
""".strip()


def _script_resolve_target(candidates: list[str], *, marker: str) -> str:
    return f"""
/* notebooklm_bridge:resolve_target:{marker} */
(() => {{
  const candidates = {json.dumps(candidates)};
  const visible = (node) => {{
    if (!node) return false;
    const rect = node.getBoundingClientRect();
    const style = window.getComputedStyle(node);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  }};
  const byText = (needle) => {{
    const lower = String(needle).toLowerCase();
    const nodes = Array.from(document.querySelectorAll('button,[role="button"],[role="tab"],input,textarea,a,div,span'));
    return nodes.find((node) => visible(node) && (node.innerText || node.value || node.getAttribute('aria-label') || '').toLowerCase().includes(lower));
  }};
  for (const candidate of candidates) {{
    let node = null;
    if (candidate.startsWith('text=')) node = byText(candidate.slice(5));
    else {{
      const hasText = candidate.match(/:has-text\\(['\"](.+?)['\"]\\)/);
      if (hasText) node = byText(hasText[1]);
      else {{ try {{ node = document.querySelector(candidate); }} catch (_err) {{ node = null; }} }}
    }}
    if (visible(node)) {{
      const rect = node.getBoundingClientRect();
      return {{found: true, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2}};
    }}
  }}
  return {{found: false}};
}})();
""".strip()


def _script_extract_text(candidates: list[str], *, marker: str) -> str:
    return f"""
/* notebooklm_bridge:extract_text:{marker} */
(() => {{
  const candidates = {json.dumps(candidates)};
  const bodyText = () => (document.body && document.body.innerText || '').trim();
  for (const candidate of candidates) {{
    if (candidate.startsWith('text=')) {{
      /* Text-only candidates prove visibility but are not safe extraction roots. */
      continue;
    }}
    const hasText = candidate.match(/:has-text\\(['\"](.+?)['\"]\\)/);
    if (hasText && !bodyText().toLowerCase().includes(hasText[1].toLowerCase())) continue;
    try {{
      const node = document.querySelector(hasText ? candidate.replace(/:has-text\\(['\"].+?['\"]\\)/, '') : candidate);
      if (node && node.innerText && node.innerText.trim()) return node.innerText.trim();
    }} catch (_err) {{}}
  }}
  return '';
}})();
""".strip()


def _script_extract_faq(selectors: SelectorStore) -> str:
    return f"""
/* notebooklm_bridge:extract_faq */
(() => {{
  const itemSelectors = {json.dumps(selectors.candidates('faq_item'))};
  const questionSelectors = {json.dumps(selectors.candidates('faq_question'))};
  const answerSelectors = {json.dumps(selectors.candidates('faq_answer'))};
  const queryOne = (root, selectors) => {{
    for (const selector of selectors) {{
      try {{
        const node = root.querySelector(selector);
        if (node && node.innerText && node.innerText.trim()) return node.innerText.trim();
      }} catch (_err) {{}}
    }}
    return '';
  }};
  const items = [];
  for (const selector of itemSelectors) {{
    try {{
      for (const node of document.querySelectorAll(selector)) {{
        const q = queryOne(node, questionSelectors);
        const a = queryOne(node, answerSelectors);
        if (q || a) items.push({{q, a}});
      }}
    }} catch (_err) {{}}
    if (items.length) return items;
  }}
  return (document.body && document.body.innerText || '').trim();
}})();
""".strip()


def _cleanup_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _source_ref(notebook_id: str, source: NormalizedSource, index: int) -> str:
    digest = hashlib.sha256(f"{notebook_id}\0{index}\0{source.kind}\0{source.content}".encode("utf-8")).hexdigest()[:24]
    return f"source_notebooklm_{source.kind}_{digest}"


def _artifact_ref(notebook_id: str, kind: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", notebook_id).strip("_") or "notebook"
    return f"artifact_notebooklm_{kind}_{slug}"[:128]
