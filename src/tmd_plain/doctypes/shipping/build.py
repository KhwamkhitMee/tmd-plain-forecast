"""ประกอบ ShippingIssue จากฉบับที่แยกแล้ว + ตรวจความซื่อตรง (F1-F4 แบบเดียวกับรายวัน).

ภาพรวม: ตัดเป็นหน่วยและท่อน ตัวจัดประเภทประโยค (NB/k-NN ที่เขียนเอง) แยกคำแนะนำออก
คำแนะนำคัดคำต่อคำ (QuotedAdvice) ท่อนอื่นแสดงคำต่อคำพร้อมค่าที่ดึงได้ (ภาษาของกรมอ่านเข้าใจได้อยู่แล้ว
และการเขียนใหม่ทำให้เสียบริบท เช่น "คลื่นสูงมากกว่า 2 เมตร" เฉพาะบริเวณที่มีฝนฟ้าคะนอง)
พื้นที่ทะเล: ดึงค่าด้วย regex แล้วเขียนตามแม่แบบเดียวกับรายวัน (ไม่มีอภิธานฝน เพราะหน้าเดินเรือไม่มีหมายเหตุเกณฑ์)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from tmd_plain.config import load_config
from tmd_plain.contract import (
    REGION_KEYS,
    LineKind,
    QuotedAdvice,
    SeaArea,
    SeaPart,
    ShippingIssue,
    SummaryLine,
)
from tmd_plain.doctypes.shipping.parse import ParsedShipping, SeaBlock
from tmd_plain.extract.facts import Fact, Pattern, Value, extract_block, extract_line
from tmd_plain.extract.scope import clauses, locations
from tmd_plain.generate.fidelity import CHANCE, line_errors
from tmd_plain.generate.templates import build_lines, facts_dict, kind_of
from tmd_plain.prep.units import split_units, unit_id

_NUM = r"\d+(?:\.\d+)?"
_DIRS = "ตะวันออกเฉียงเหนือ|ตะวันออกเฉียงใต้|ตะวันตกเฉียงเหนือ|ตะวันตกเฉียงใต้|ตะวันออก|ตะวันตก|เหนือ|ใต้|แปรปรวน"
_SPACE = re.compile(r"\s+")


def _num_of(s: str) -> int | float:
    return float(s) if "." in s else int(s)


def _wind_knots(m: re.Match[str]) -> list[tuple[str, Value]]:
    return [
        ("wind_dir", m.group("dir")),
        ("wind_speed_kt_low", _num_of(m.group("klo"))),
        ("wind_speed_kt_high", _num_of(m.group("khi") or m.group("klo"))),
        ("wind_speed_kmh_low", _num_of(m.group("lo"))),
        ("wind_speed_kmh_high", _num_of(m.group("hi") or m.group("lo"))),
    ]


def _wave_storm(m: re.Match[str]) -> list[tuple[str, Value]]:
    lo = m.group("lo")
    return [
        ("wave_storm_qualifier", m.group("qual")),
        ("wave_storm_m_low", _num_of(lo)),
        ("wave_storm_m_high", _num_of(m.group("hi") or lo)),
    ]


def _phrase(name: str) -> Callable[[re.Match[str]], list[tuple[str, Value]]]:
    return lambda m: [(name, m.group(0))]


# รูปแบบเฉพาะเดินเรือ ลองก่อนรูปแบบกลาง: ลมเป็นนอต "หรือ" กม./ชม., คลื่นในภาพรวมที่มี "จะมี" คั่น
# (รูปแบบกลางจะอ่านเป็นคลื่นทั่วไป เสียบริบทว่าเฉพาะบริเวณที่มีฝนฟ้าคะนอง) และ "ตอนล่าง" ที่ไม่มี "ทาง" นำหน้า
SHIPPING_PATTERNS: tuple[Pattern, ...] = (
    (
        re.compile(
            rf"บริเวณที่มีฝนฟ้าคะนองจะมีคลื่น\s*(?P<qual>สูงประมาณ|สูงมากกว่า|สูง)\s*"
            rf"(?P<lo>{_NUM})(?:\s*[-–]\s*(?P<hi>{_NUM}))?\s*เมตร"
        ),
        _wave_storm,
    ),
    (
        re.compile(
            rf"ลม(?P<dir>{_DIRS})\s*ความเร็ว\s*(?P<klo>{_NUM})(?:\s*[-–]\s*(?P<khi>{_NUM}))?\s*นอต\s*"
            rf"(?:หรือ\s*)?(?:ความเร็ว\s*)?(?P<lo>{_NUM})(?:\s*[-–]\s*(?P<hi>{_NUM}))?\s*กม\./ชม\."
        ),
        _wind_knots,
    ),
    (re.compile(r"(?:ทาง)?ตอน(?:บน|ล่าง)"), _phrase("area_part")),
)


@dataclass(frozen=True)
class OverviewUnit:
    text: str  # ท่อนคำต่อคำ
    unit_id: str
    label: str  # ป้ายจากตัวจัดประเภท (weather / cause / advice / other)


def shipping_unit_id(text: str) -> str:
    # unit_id ใช้อักษรแรกของชนิด ("s" ชนกับ sevenday) จึงใช้ "sh" แทน
    return "sh" + unit_id("s", text)[1:]


def overview_units(parsed: ParsedShipping, label_of: Callable[[str], str]) -> list[OverviewUnit]:
    """หน่วย (กติกาเดียวกับรายวัน) แล้วตัดเป็นท่อนที่ "สำหรับ/ชาวเรือ/เรือเล็ก/ขอให้" ให้คำแนะนำแยกจากสาเหตุ."""
    out: list[OverviewUnit] = []
    for unit in split_units(parsed.overview):
        for piece in clauses(unit):
            text = piece.strip()
            if text:
                out.append(OverviewUnit(text, shipping_unit_id(text), label_of(text)))
    return out


def _overview_line(unit: OverviewUnit) -> SummaryLine:
    facts = extract_line(unit.text, 0, SHIPPING_PATTERNS)
    kinds = [k for f in facts if (k := kind_of(f.name)) is not None]
    kind: LineKind = kinds[0] if kinds else "other"
    return SummaryLine(
        kind=kind, text=unit.text, facts={**facts_dict(facts), "unit_role": unit.label}
    )


def _lines(lines: tuple[str, ...]) -> list[SummaryLine]:
    # gl={} : ไม่มีอภิธานฝนของเดินเรือ ("daily" ใช้เป็นชนิดของแม่แบบเท่านั้น ไม่ได้ใช้เกณฑ์ของรายวัน)
    return build_lines(extract_block(lines, SHIPPING_PATTERNS), lines, "daily", gl={})


def area_facts(block: SeaBlock) -> list[Fact]:
    return [
        f
        for ln in (block.lines, *(p.lines for p in block.parts))
        for f in extract_block(ln, SHIPPING_PATTERNS)
    ]


def _area(block: SeaBlock) -> SeaArea:
    return SeaArea(
        name_th=block.name_th,
        lines=_lines(block.lines) if block.lines else [],
        parts=[SeaPart(name_th=p.name_th, lines=_lines(p.lines)) for p in block.parts],
    )


def assemble_shipping(
    parsed: ParsedShipping, units: list[OverviewUnit], source_label: str | None = None
) -> ShippingIssue:
    """ผลสรุปทั้งฉบับ; ไม่มีเวลาประมวลผลในผล (ผลซ้ำได้). บล็อกที่ไม่มีค่าเลยโยน GenerateError."""
    advice: list[QuotedAdvice] = []
    overview: list[SummaryLine] = []
    seen: set[str] = set()
    for unit in units:
        if unit.label != "advice":
            overview.append(_overview_line(unit))
        elif unit.unit_id not in seen:
            seen.add(unit.unit_id)
            here = locations(unit.text)
            advice.append(
                QuotedAdvice(
                    text=unit.text,
                    regions=[k for k in REGION_KEYS if k in here],
                    source_unit_id=unit.unit_id,
                )
            )
    return ShippingIssue(
        issue_id=parsed.issue_id,
        doc_type="shipping",
        issued_at=parsed.issued_at,
        source_label=source_label or parsed.issued_line,
        overview=overview,
        areas={key: _area(block) for key, block in parsed.areas.items()},
        advice=advice,
        pipeline_version=load_config()["pipeline_version"],
    )


def _norm(text: str) -> str:
    return _SPACE.sub("", text)


def check_shipping(issue: ShippingIssue, parsed: ParsedShipping) -> list[str]:
    """F1 ตัวเลขของพื้นที่/ส่วนย่อยอยู่ในบล็อกของตัวเอง · F2 จังหวัด · F3 ภาพรวมและคำแนะนำคำต่อคำ · F4 ไม่มีคำว่าโอกาส."""
    errors: list[str] = []
    source = _norm(parsed.overview)
    for key, area in issue.areas.items():
        block = parsed.areas[key]
        for n, line in enumerate(area.lines):
            errors += line_errors(line, " ".join(block.lines), {}, f"{key}#{n}")
        for part, part_block in zip(area.parts, block.parts, strict=True):
            for n, line in enumerate(part.lines):
                errors += line_errors(
                    line, " ".join(part_block.lines), {}, f"{key}/{part.name_th}#{n}"
                )
    for n, line in enumerate(issue.overview):
        if _norm(line.text) not in source:
            errors.append(f"F3 ภาพรวมไม่อยู่ในต้นฉบับ #{n}")
        if CHANCE.search(line.text):
            errors.append(f"F4 ภาพรวมใช้คำว่าโอกาส #{n}")
    for item in issue.advice:
        if _norm(item.text) not in source:
            errors.append(f"F3 คำแนะนำไม่อยู่ในต้นฉบับ {item.source_unit_id}")
        if CHANCE.search(item.text):
            errors.append(f"F4 คำแนะนำใช้คำว่าโอกาส {item.source_unit_id}")
    if issue.issue_id != parsed.issue_id:
        errors.append(f"รหัสฉบับ {issue.issue_id} ไม่ตรงบรรทัดออกประกาศ {parsed.issue_id}")
    return errors
