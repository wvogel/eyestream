from __future__ import annotations

import json
import os
import contextvars
from typing import Optional

_translations: dict[str, dict[str, str]] = {}
_i18n_dir = os.path.dirname(__file__)

SUPPORTED_LANGUAGES = ["en", "de"]
DEFAULT_LANGUAGE = "en"

_current_lang: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_lang", default=DEFAULT_LANGUAGE
)


def _load_lang(lang: str) -> dict[str, str]:
    if lang not in _translations:
        path = os.path.join(_i18n_dir, f"{lang}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        else:
            _translations[lang] = {}
    return _translations[lang]


def t(key: str, **kwargs) -> str:
    """Get translated string using the current request language (contextvar).
    Falls back to English, then to the key itself.
    """
    lang = _current_lang.get()
    strings = _load_lang(lang)
    text = strings.get(key)
    if text is None and lang != "en":
        text = _load_lang("en").get(key)
    if text is None:
        text = key
    if kwargs:
        for k, v in kwargs.items():
            text = text.replace("{" + k + "}", str(v))
    return text


def get_translations(lang: Optional[str] = None) -> dict[str, str]:
    """Return the full translation dict for a language (for embedding in JS)."""
    if lang is None:
        lang = _current_lang.get()
    return dict(_load_lang(lang))


def set_language(lang: str) -> None:
    """Set the language for the current request context."""
    if lang in SUPPORTED_LANGUAGES:
        _current_lang.set(lang)
    else:
        _current_lang.set(DEFAULT_LANGUAGE)


def get_language() -> str:
    """Get the current language."""
    return _current_lang.get()
