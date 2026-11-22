#!/usr/bin/env python3
"""校验 evaluation/datasets/ 下的 JSONL 评测集。

用法:python3 scripts/validate_datasets.py
退出码:0 = 全部通过;1 = 存在问题。
仅使用标准库,不依赖仓库其余代码。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATASETS_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "datasets"

REQUIRED_FIELDS = [
    "id",
    "category",
    "user_goal",
    "source",
    "source_type",
    "expected_tools",
    "expected_params",
    "expected_decision",
    "expected_final_state",
    "reason",
]

VALID_CATEGORIES = {
    "normal",
    "boundary",
    "injection",
    "privilege",
    "parameter",
    "recovery",
}

VALID_DECISIONS = {"ALLOW", "CONFIRM", "BLOCK"}

VALID_SOURCE_TYPES = {"user_directive", "reference_material", "external_document"}

VALID_TOOLS = {"calendar", "send_notice", "shared_file", "export_roster"}

CATEGORY_PREFIX = {
    "normal": "NRM",
    "boundary": "BND",
    "injection": "INJ",
    "privilege": "PRV",
    "parameter": "PAR",
    "recovery": "REC",
}

EXPECTED_COUNTS = {
    "normal.jsonl": 6,
    "boundary.jsonl": 3,
    "injection.jsonl": 4,
    "privilege.jsonl": 3,
    "parameter.jsonl": 3,
    "recovery.jsonl": 1,
}


def check_file(path: Path, seen_ids: dict[str, str]) -> list[str]:
    problems: list[str] = []
    category_from_filename = path.stem
    count = 0
    with path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            count += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name}:{lineno} 不是合法 JSON: {exc}")
                continue
            where = f"{path.name}:{lineno}"
            for field in REQUIRED_FIELDS:
                if field not in item or item[field] in (None, ""):
                    problems.append(f"{where} 缺少必填字段 {field}")
            sid = item.get("id", "")
            if not sid:
                continue
            if sid in seen_ids:
                problems.append(f"{where} id 重复: {sid}(首次出现于 {seen_ids[sid]})")
            seen_ids[sid] = where
            prefix = sid.split("-")[0] if "-" in sid else ""
            if prefix != CATEGORY_PREFIX.get(category_from_filename):
                problems.append(
                    f"{where} id 前缀 {prefix} 与文件类别 {category_from_filename} 不符"
                )
            if item.get("category") != category_from_filename:
                problems.append(
                    f"{where} category={item.get('category')} 与文件名不符"
                )
            if item.get("category") not in VALID_CATEGORIES:
                problems.append(f"{where} category 非法: {item.get('category')}")
            if item.get("expected_decision") not in VALID_DECISIONS:
                problems.append(
                    f"{where} expected_decision 非法: {item.get('expected_decision')}"
                )
            if item.get("source_type") not in VALID_SOURCE_TYPES:
                problems.append(f"{where} source_type 非法: {item.get('source_type')}")
            for tool_action in item.get("expected_tools", []):
                tool = str(tool_action).split(":")[0]
                if tool not in VALID_TOOLS:
                    problems.append(f"{where} 未知工具: {tool}")
    expected = EXPECTED_COUNTS.get(path.name)
    if expected is not None and count != expected:
        problems.append(f"{path.name} 条数 {count} != 预期 {expected}")
    return problems


def main() -> int:
    if not DATASETS_DIR.is_dir():
        print(f"数据目录不存在: {DATASETS_DIR}")
        return 1
    seen_ids: dict[str, str] = {}
    all_problems: list[str] = []
    total = 0
    for name in sorted(EXPECTED_COUNTS):
        path = DATASETS_DIR / name
        if not path.exists():
            all_problems.append(f"缺少文件: {name}")
            continue
        problems = check_file(path, seen_ids)
        all_problems.extend(problems)
        total += sum(1 for _ in path.open(encoding="utf-8") if _.strip())
    for path in sorted(DATASETS_DIR.glob("*.jsonl")):
        if path.name not in EXPECTED_COUNTS:
            all_problems.append(f"出现未登记的文件: {path.name}")
    print(f"共读取 {total} 条样本,涉及 {len(seen_ids)} 个唯一 id")
    if all_problems:
        print(f"发现 {len(all_problems)} 个问题:")
        for problem in all_problems:
            print(f"  - {problem}")
        return 1
    print("校验通过:JSON 合法、id 唯一、字段完整、类别与决策均在白名单内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
