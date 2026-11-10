"""Bounded, local inspection of untrusted demo TXT/CSV references.

No file contents or CSV row values are returned or retained in task state.
These heuristics are evidence for a demo, not a prompt-injection classifier.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import PurePath
from typing import Any, Dict

MAX_REFERENCE_BYTES = 32 * 1024
MAX_CSV_ROWS = 500
MAX_CSV_COLUMNS = 20

_SAFE_COLUMNS = {
    "activity", "availability", "group", "location", "role", "shift", "skill",
    "team", "time", "分组", "可参与时段", "地点", "技能", "时间", "活动",
    "班次", "角色",
}
_SENSITIVE_COLUMNS = {
    "address", "email", "home_address", "id_number", "name", "phone",
    "住址", "姓名", "身份证", "身份证号", "邮箱", "手机号", "电话",
}
_INSTRUCTION_PATTERNS = (
    re.compile(r"忽略.{0,12}(之前|以上|上述).{0,12}(指令|要求|规则)", re.I),
    re.compile(r"(系统|开发者)指令", re.I),
    re.compile(r"(导出|发送).{0,20}(完整名单|手机号|身份证|外部邮箱)", re.I),
    re.compile(r"ignore.{0,20}(previous|prior).{0,20}instructions", re.I),
    re.compile(r"system\s+prompt", re.I),
)


def inspect_reference(name: str, content: str) -> Dict[str, Any]:
    """Return a non-executable source summary; never trust content as authority."""
    if not name or name != PurePath(name).name or "\\" in name:
        raise ValueError("reference name must be a plain file name")
    suffix = PurePath(name).suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise ValueError("only UTF-8 TXT and CSV references are supported")
    if "\x00" in content:
        raise ValueError("binary reference content is not supported")
    raw = content.encode("utf-8")
    if not raw or len(raw) > MAX_REFERENCE_BYTES:
        raise ValueError("reference must be 1–32768 UTF-8 bytes")

    flags = []
    result: Dict[str, Any] = {
        "name": name,
        "format": suffix[1:],
        "source_trust": "EXTERNAL_UNTRUSTED",
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "flags": flags,
    }
    if suffix == ".csv":
        result.update(_inspect_csv(content, flags))
    if any(pattern.search(content) for pattern in _INSTRUCTION_PATTERNS):
        flags.append("POSSIBLE_INSTRUCTION_IN_REFERENCE")
    return result


def _inspect_csv(content: str, flags: list[str]) -> Dict[str, Any]:
    try:
        reader = csv.reader(io.StringIO(content, newline=""), strict=True)
        headers = next(reader)
        if not headers or len(headers) > MAX_CSV_COLUMNS:
            raise ValueError("CSV must have 1–20 columns")
        normalized = [header.strip().lower().lstrip("\ufeff") for header in headers]
        if any(not header for header in normalized) or len(set(normalized)) != len(
            normalized
        ):
            raise ValueError("CSV headers must be nonempty and unique")
        rows = 0
        for row in reader:
            if len(row) != len(headers):
                raise ValueError("CSV rows must match the header width")
            rows += 1
            if rows > MAX_CSV_ROWS:
                raise ValueError("CSV must have at most 500 data rows")
    except (csv.Error, StopIteration) as exc:
        raise ValueError("invalid CSV reference") from exc

    sensitive = sorted(set(normalized) & _SENSITIVE_COLUMNS)
    if sensitive:
        flags.append("SENSITIVE_COLUMNS_EXCLUDED")
    return {
        "row_count": rows,
        "safe_columns": sorted(set(normalized) & _SAFE_COLUMNS),
        "excluded_column_count": len(normalized) - len(set(normalized) & _SAFE_COLUMNS),
        "sensitive_columns": sensitive,
    }
