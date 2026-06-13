# Inspired by and adapted from the "caveman" productivity skill by Matt Pocock (MIT License)
# Copyright (c) 2026 Matt Pocock

import re
from typing import Any

from pydantic import BaseModel

# Regex for case-insensitive filler words, matching whole words
FILLER_RE = re.compile(
    r"\b(a|an|the|just|really|basically|actually|simply|sure|certainly|of\s+course|happy\s+to|please|would|could|should|likely|probably|maybe)\b",
    re.IGNORECASE,
)

SYNONYMS = {
    "authentication": "auth",
    "authenticated": "auth",
    "authenticate": "auth",
    "configuration": "config",
    "configured": "config",
    "configure": "config",
    "implementation": "impl",
    "implemented": "impl",
    "implement": "impl",
    "function": "fn",
    "functions": "fns",
    "argument": "arg",
    "arguments": "args",
    "parameter": "param",
    "parameters": "params",
    "repository": "repo",
    "repositories": "repos",
    "database": "DB",
    "databases": "DBs",
    "connection": "conn",
    "connections": "conns",
    "information": "info",
    "initialize": "init",
    "initialized": "init",
    "initialization": "init",
    "documentation": "docs",
    "documented": "docs",
    "document": "doc",
    "documents": "docs",
    "directory": "dir",
    "directories": "dirs",
    "environment": "env",
    "environments": "envs",
    "exception": "err",
    "exceptions": "errs",
    "error": "err",
    "errors": "errs",
    "request": "req",
    "requests": "reqs",
    "response": "res",
    "responses": "res",
}

SYNONYMS_RE = re.compile(
    r"\b(" + "|".join(map(re.escape, SYNONYMS.keys())) + r")\b", re.IGNORECASE
)


def _replace_synonym(match: re.Match) -> str:
    word = match.group(1).lower()
    replacement = SYNONYMS.get(word, match.group(1))
    if match.group(1).isupper():
        return replacement.upper()
    if match.group(1)[0].isupper():
        return replacement.capitalize()
    return replacement


def compress_text(text: str) -> str:
    """Compress a single text block using caveman rules."""
    if not text or not isinstance(text, str):
        return text
    # 1. Remove filler words
    text = FILLER_RE.sub("", text)
    # 2. Replace synonyms
    text = SYNONYMS_RE.sub(_replace_synonym, text)
    # 3. Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    # 4. Clean up spaces before punctuation
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return text.strip()


def compress_payload(payload: Any) -> Any:
    """
    Recursively traverse python collections and Pydantic models.
    Compress string values while keeping dictionary keys and non-string types intact.
    """
    if isinstance(payload, BaseModel):
        model_dict = payload.model_dump()
        compressed_dict = compress_payload(model_dict)
        return payload.__class__(**compressed_dict)
    if isinstance(payload, dict):
        return {key: compress_payload(val) for key, val in payload.items()}
    if isinstance(payload, list):
        return [compress_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(compress_payload(item) for item in payload)
    if isinstance(payload, str):
        return compress_text(payload)
    return payload
