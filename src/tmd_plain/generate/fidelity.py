"""ตรวจความซื่อตรงของผลสรุปเทียบต้นฉบับ (F1-F5) คืนรายการข้อผิดพลาด ว่าง = ผ่าน.

F1 ตัวเลขในประโยคของภาคต้องอยู่ในบล็อกต้นฉบับของภาคนั้น (ADR 0020: ไม่มีค่าที่คำนวณในข้อความแล้ว)
   และทุกรายการใน notes ต้องตรงอภิธาน TMD ตามคำใน facts.glossary_terms (ตัวเลขของนิยามมาจากหมายเหตุของ TMD)
F2 ชื่อจังหวัดในประโยค (text และ detail) ต้องอยู่ในบล็อกต้นฉบับ · F3 คำแนะนำเป็นสตริงย่อยของต้นฉบับ (ปรับช่องว่าง)
F4 ห้ามมีคำว่าโอกาส + ตัวเลข % หรือ "ความน่าจะเป็น" · F5 ตามมาจาก F1 (ตรวจกับบล็อกของภาคตัวเองเท่านั้น)
"""

from __future__ import annotations

import re

from tmd_plain.contract import Issue, SummaryLine
from tmd_plain.extract.provinces import PROVINCE_RE
from tmd_plain.generate.glossary import glossary
from tmd_plain.prep.regions import ParsedIssue

_NUM = re.compile(r"\d+(?:\.\d+)?")
CHANCE = re.compile(r"โอกาส[^\n]{0,30}?\d+\s*%|ความน่าจะเป็น")
_SPACE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACE.sub("", text)


def line_errors(line: SummaryLine, block: str, gl: dict[str, str], where: str) -> list[str]:
    """F1 F2 F4 ของประโยคหนึ่งเทียบบล็อกต้นฉบับ (ใช้ร่วมกับชนิดอื่น เช่น พยากรณ์เดินเรือ)."""
    errors: list[str] = []
    allowed = set(_NUM.findall(block))
    for n in _NUM.findall(line.text):
        if n not in allowed:
            errors.append(f"F1 ตัวเลข {n} ไม่มีที่มา {where}: {line.text}")
    terms = line.facts.get("glossary_terms", [])
    known = {f"{t} คือ {gl[t]}" for t in (terms if isinstance(terms, list) else []) if t in gl}
    for note in line.notes:
        if note not in known:
            errors.append(f"F1 ความหมายระดับไม่ตรงอภิธาน TMD {where}: {note}")
    for m in PROVINCE_RE.finditer(" ".join([line.text, *line.detail])):
        if m.group(0) not in block:
            errors.append(f"F2 จังหวัด {m.group(0)} ไม่อยู่ในต้นฉบับ {where}")
    if CHANCE.search(" ".join([line.text, *line.detail, *line.notes])):
        errors.append(f"F4 ใช้คำว่าโอกาส/ความน่าจะเป็น {where}: {line.text}")
    return errors


def check_issue(issue: Issue, parsed: ParsedIssue) -> list[str]:
    gl = glossary(issue.doc_type)
    errors: list[str] = []
    source = _norm(" ".join((*parsed.overview, *parsed.caution)))
    for key, region in issue.regions.items():
        block = " ".join(parsed.regions[key].lines)
        lines = [*region.lines, *(ln for p in region.periods for ln in p.lines)]
        for n, line in enumerate(lines):
            errors += line_errors(line, block, gl, f"{key}#{n}")
        for item in region.advice:
            if _norm(item.text) not in source:
                errors.append(f"F3 คำแนะนำไม่อยู่ในต้นฉบับ {key}: {item.source_unit_id}")
    for item in issue.general_advice:
        if _norm(item.text) not in source:
            errors.append(f"F3 คำแนะนำไม่อยู่ในต้นฉบับ (ทั่วไป): {item.source_unit_id}")
    for item in [*issue.general_advice, *(a for r in issue.regions.values() for a in r.advice)]:
        if CHANCE.search(item.text):
            errors.append(f"F4 คำแนะนำใช้คำว่าโอกาส {item.source_unit_id}")
    return errors


def cross_region_numbers(issue: Issue, parsed: ParsedIssue) -> list[str]:
    """F5 แยกรายงาน: ตัวเลขในสรุปของภาคที่ไม่อยู่ในบล็อกตัวเอง แต่อยู่ในบล็อกภาคอื่น (ค่าข้ามภาค)."""
    gl = glossary(issue.doc_type)
    blocks = {k: set(_NUM.findall(" ".join(b.lines))) for k, b in parsed.regions.items()}
    out: list[str] = []
    for key, region in issue.regions.items():
        for line in [*region.lines, *(ln for p in region.periods for ln in p.lines)]:
            if not line_errors(line, " ".join(parsed.regions[key].lines), gl, key):
                continue
            for n in _NUM.findall(line.text):
                others = [k for k, nums in blocks.items() if k != key and n in nums]
                if n not in blocks[key] and others:
                    out.append(f"F5 ตัวเลข {n} ใน {key} พบเฉพาะในบล็อก {others}")
    return out
