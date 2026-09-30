"""报告与时间轴组装时用的参与集辅助函数。

参与集统一由 reports._detect_events 按库内当前车号一次性产出，
报告 / 建议 / 时间轴三页共用同一次检测结果，不再有分叉入口。
"""
from __future__ import annotations

# scope_helpers_ready_35

def flatten_marks(marks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in marks:
        item = dict(m)
        item.setdefault('visible', True)
        out.append(item)
    return out
