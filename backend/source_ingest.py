"""Bounded, local inspection of untrusted demo TXT/CSV references.

No file contents or CSV row values are returned or retained in task state.
These heuristics are evidence for a demo, not a prompt-injection classifier.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime
from pathlib import PurePath
from typing import Any, Dict, Optional

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


def safe_reference_signals(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Allowlisted, value-free facts that an advisory cloud agent may receive."""
    return {
        "present": True,
        "format": summary["format"],
        "row_count": summary.get("row_count"),
        "has_sensitive_columns": bool(summary.get("sensitive_columns")),
        "possible_instruction": (
            "POSSIBLE_INSTRUCTION_IN_REFERENCE" in summary["flags"]
        ),
    }


def preview_reference_review(
    name: str, content: str, recipient_count: int
) -> Dict[str, Any]:
    """Suggest human checks without treating reference data as authorization."""
    if not 1 <= recipient_count <= 1000:
        raise ValueError("recipient_count must be 1–1000")
    summary = inspect_reference(name, content)
    checks = []
    if summary["format"] == "csv":
        rows = summary["row_count"]
        if rows == 0:
            checks.append({
                "code": "EMPTY_ROSTER",
                "severity": "REVIEW",
                "message": "报名表没有数据行，请核对资料是否完整。",
            })
        elif rows != recipient_count:
            checks.append({
                "code": "COUNT_MISMATCH",
                "severity": "REVIEW",
                "message": (
                    f"报名表有 {rows} 行，拟通知 {recipient_count} 人；"
                    "请核对是否包含重复、未报名或其他对象。系统不会自动修改人数。"
                ),
            })
        else:
            checks.append({
                "code": "COUNT_MATCH",
                "severity": "INFO",
                "message": (
                    f"报名表行数与拟通知人数均为 {rows}；"
                    "行数一致不代表每位对象都已授权接收通知。"
                ),
            })
        if summary["sensitive_columns"]:
            checks.append({
                "code": "SENSITIVE_FIELDS_EXCLUDED",
                "severity": "REVIEW",
                "message": "资料含敏感列；只使用行数与允许的列名，勿上传真实个人名单。",
            })
    else:
        checks.append({
            "code": "TEXT_NOT_USED_FOR_COUNT",
            "severity": "INFO",
            "message": "TXT 不用于推断通知人数；请以用户填写的人数为准。",
        })
    if "POSSIBLE_INSTRUCTION_IN_REFERENCE" in summary["flags"]:
        checks.append({
            "code": "INSTRUCTION_REVIEW",
            "severity": "REVIEW",
            "message": (
                "资料可能包含操作指令；仅作为待核对内容，"
                "不会改变收件人或工具权限。"
            ),
        })
    proposal = _schedule_proposal(content) if summary["format"] == "csv" else None
    activity_draft = _activity_draft(content) if summary["format"] == "txt" else None
    return {
        "mode": "PREVIEW_ONLY",
        "source_summary": summary,
        "checks": checks,
        "schedule_proposal": proposal,
        "activity_draft": activity_draft,
        "warning": "这是提交前建议，不创建任务、不授权、不执行工具；仍需人工核对。",
    }


def _activity_draft(content: str) -> Optional[Dict[str, str]]:
    """Extract only explicit bounded fields; never interpret prose as authority."""
    fields: Dict[str, str] = {}
    for line in content.splitlines():
        match = re.fullmatch(r"\s*(活动时间|活动地点)\s*[：:]\s*(.*?)\s*", line)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2)
    starts_at = fields.get("活动时间", "")
    location = fields.get("活动地点", "")
    time_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?:\+08:00|\+09:00|\+00:00)"
    if not re.fullmatch(time_pattern, starts_at):
        return None
    try:
        datetime.fromisoformat(starts_at)
    except ValueError:
        return None
    location_pattern = r"[\w\u4e00-\u9fff\s·（）()—-]+"
    if not 1 <= len(location) <= 120 or not re.fullmatch(
        location_pattern, location
    ):
        return None
    return {
        "starts_at": starts_at,
        "location": location,
        "warning": (
            "从外部 TXT 提取的待核对草案；只有用户点击采纳才会填入表单，"
            "不构成执行授权。"
        ),
    }


def _schedule_proposal(content: str) -> Optional[Dict[str, Any]]:
    """Use only a controlled availability vocabulary; never return CSV values."""
    reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
    assert reader.fieldnames is not None  # validated by inspect_reference
    columns = {
        name.strip().lower().lstrip("\ufeff"): name for name in reader.fieldnames
    }
    column = next(
        (
            columns[key]
            for key in ("availability", "可参与时段", "shift", "班次")
            if key in columns
        ),
        None,
    )
    if column is None:
        return None
    counts = {"上午": 0, "下午": 0}
    assignments = []
    unassigned = []
    options = {
        "上午": {"上午"}, "morning": {"上午"},
        "下午": {"下午"}, "afternoon": {"下午"},
        "全天": {"上午", "下午"}, "均可": {"上午", "下午"},
        "all-day": {"上午", "下午"}, "both": {"上午", "下午"},
    }
    for index, row in enumerate(reader, start=1):
        raw = (row[column] or "").strip().lower()
        available = options.get(raw, set())
        if not available:
            unassigned.append(index)
            continue
        slot = min(available, key=lambda value: (counts[value], value != "上午"))
        counts[slot] += 1
        assignments.append({"candidate_index": index, "slot": slot})
    return {
        "basis": "仅识别报名表中的标准可参与时段，不使用姓名、电话或其他字段",
        "assignments": assignments,
        "unassigned_indices": unassigned,
        "slot_counts": counts,
        "warning": (
            "匿名排班草案；请核对人员意愿与实际名单后另行确认，"
            "草案不会自动执行。"
        ),
    }


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
