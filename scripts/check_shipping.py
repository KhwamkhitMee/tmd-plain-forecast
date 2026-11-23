"""Phase 11.1: ตรวจพยากรณ์เดินเรือทุกฉบับที่เก็บ -> docs/results/shipping-check.md (ต้องพิมพ์ errors: 0).

รัน: .venv/Scripts/python.exe -X utf8 scripts/check_shipping.py
ข้อผิดพลาด (ทำให้ล้ม): ตรวจชนิดไม่ได้, แยกโครงไม่ได้, รหัสจากบรรทัดออกประกาศไม่ตรงรหัสรอบ, ไม่ผ่าน F1-F4,
บรรทัดต้นฉบับของพื้นที่ทะเลที่ไม่ได้ค่าเลย, ตัวเลขในบล็อกพื้นที่ที่ไม่อยู่ในสรุปของพื้นที่นั้น (ข้อมูลหาย)
ข้อสังเกต (ไม่ล้ม): ท่อนที่มีคำแนะนำ (ควร/ขอให้) แต่ตัวจัดประเภทไม่ได้ให้ป้าย advice และกลับกัน
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from tmd_plain.classify.model_io import load_labeler
from tmd_plain.contract import SEA_AREA_KEYS, SEA_AREA_LABELS_TH, ShippingIssue, SummarizeError
from tmd_plain.doctypes.shipping.build import SHIPPING_PATTERNS
from tmd_plain.doctypes.shipping.parse import parse_shipping
from tmd_plain.doctypes.shipping.runner import ShippingDetails, summarize_shipping
from tmd_plain.extract.facts import extract_line
from tmd_plain.prep.doctype import detect_doc_type
from tmd_plain.prep.extract import document_from_txt
from tmd_plain.raw_io import load_shipping

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "docs" / "results" / "shipping-check.md"
_NUM = re.compile(r"\d+(?:\.\d+)?")
_ADVICE_WORDS = re.compile(r"ควร|ขอให้|หลีกเลี่ยง|งดออกจากฝั่ง")


def _area_numbers_missing(issue: ShippingIssue, details: ShippingDetails) -> list[str]:
    out: list[str] = []
    for key in SEA_AREA_KEYS:
        block = details.parsed.areas[key]
        area = issue.areas[key]
        all_lines = (*area.lines, *(ln for p in area.parts for ln in p.lines))
        said = " ".join(ln.text for ln in all_lines)
        have = set(_NUM.findall(said))
        # ADR 0020: ข้อความแสดงนอตอย่างเดียว ค่า กม./ชม. ของต้นฉบับอยู่ใน facts ถือว่าไม่ตกหล่น
        for ln in all_lines:
            for value in ln.facts.values():
                if isinstance(value, int | float) and not isinstance(value, bool):
                    have.add(str(value))
        for n in _NUM.findall(" ".join(block.all_lines())):
            if n not in have:
                out.append(f"{key}: ตัวเลข {n} ในต้นฉบับไม่อยู่ในสรุป")
    return out


def main() -> int:
    label_of = load_labeler(ROOT / "models")
    raws = load_shipping(RAW)
    errors: list[str] = []
    notes: list[str] = []
    labels: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    empty_lines = 0
    for raw in raws:
        text = document_from_txt(raw.txt.read_text(encoding="utf-8")).text
        where = f"shipping/{raw.issue_id}"
        if detect_doc_type(text) != "shipping":
            errors.append(f"{where}: ตรวจชนิดไม่ได้ shipping")
            continue
        run = summarize_shipping(text, label_of)
        if isinstance(run, SummarizeError):
            errors.append(f"{where}: {run.error.code}")
            continue
        issue: ShippingIssue = run.document  # type: ignore[assignment]
        details: ShippingDetails = run.details
        if issue.issue_id != raw.issue_id:
            errors.append(f"{where}: รหัสจากเนื้อหา {issue.issue_id} ไม่ตรงรหัสรอบ")
        for key, block in parse_shipping(text).areas.items():
            for line in block.all_lines():
                if not extract_line(line, 0, SHIPPING_PATTERNS):
                    empty_lines += 1
                    errors.append(f"{where}: บรรทัดไม่ได้ค่าเลย ({key}): {line}")
        errors += [f"{where}: {m}" for m in _area_numbers_missing(issue, details)]
        for unit in details.units:
            labels[unit.label] += 1
            looks_advice = bool(_ADVICE_WORDS.search(unit.text))
            if looks_advice != (unit.label == "advice"):
                notes.append(f"{where}: ป้าย {unit.label}: {unit.text}")
        for area in issue.areas.values():
            for ln in (*area.lines, *(ln for p in area.parts for ln in p.lines)):
                kinds[ln.kind] += 1
    lines = [
        "# ตรวจพยากรณ์เดินเรือ (Phase 11.1)",
        "",
        "สร้างโดย `scripts/check_shipping.py` (อย่าแก้ด้วยมือ) · แหล่ง: ข้อความหน้าเว็บที่เก็บใน `data/raw/shipping/`",
        "",
        f"- ฉบับ: {len(raws)} · ข้อผิดพลาด: {len(errors)} · บรรทัดต้นฉบับที่ไม่ได้ค่า: {empty_lines}",
        f"- พื้นที่ทะเล: {', '.join(SEA_AREA_LABELS_TH[k] for k in SEA_AREA_KEYS)} (ครบทุกฉบับถ้าไม่มีข้อผิดพลาด)",
        "- ป้ายของท่อนภาพรวม (ตัวจัดประเภทที่ใช้ในเว็บ): "
        + ", ".join(f"{k} {v}" for k, v in sorted(labels.items())),
        "- ชนิดประโยคของพื้นที่ทะเล: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())),
        f"- ข้อสังเกตป้าย (มีคำแนะนำแต่ไม่ได้ป้าย advice หรือกลับกัน): {len(notes)}",
        "",
        "## ข้อผิดพลาด",
        "",
        *([f"- {e}" for e in errors] or ["- ไม่มี"]),
        "",
        "## ข้อสังเกตป้าย",
        "",
        *([f"- {n}" for n in sorted(set(notes))] or ["- ไม่มี"]),
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"issues {len(raws)} · label notes {len(notes)} · errors: {len(errors)}")
    for e in errors[:20]:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
