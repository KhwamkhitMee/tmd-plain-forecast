"""แม่แบบประโยคภาษาง่ายจากค่าที่ดึงได้ (ขั้น 3): หนึ่ง SummaryLine ต่อชนิด (ลม/คลื่นแยกตามเขตลม).

กติกา (สเปกหัวข้อ 4 + ADR 0013 ที่แก้โดย ADR 0020):
- ตัวเลขและชื่อจังหวัดมาจากค่าใน facts ของบรรทัดต้นฉบับเท่านั้น ไม่มีค่าที่คำนวณในข้อความ
- ข้อความกระชับ ไม่มีวงเล็บขยายความ: รายชื่อจังหวัดอยู่ใน detail, ความหมายระดับฝน/ความหนาวอยู่ใน notes
- ความหมายระดับใช้อภิธานจากหมายเหตุของ TMD เท่านั้น
- "ร้อยละ N ของพื้นที่" คือสัดส่วนพื้นที่ ห้ามเขียนเป็นโอกาส/ความน่าจะเป็น
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tmd_plain.contract import DocType, FactValue, LineKind, SummaryLine
from tmd_plain.extract.facts import Fact, Value
from tmd_plain.generate.glossary import cold_terms, glossary, rain_terms

_KIND_OF_PREFIX: list[tuple[str, LineKind]] = [
    ("rain_", "rain"),
    ("heavy_rain", "rain"),
    ("very_heavy_rain", "rain"),
    ("light_rain", "rain"),
    ("some_rain", "rain"),
    ("gusts", "rain"),
    ("hail", "rain"),
    ("province", "rain"),
    ("temp_", "temperature"),
    ("peak_", "temperature"),
    ("cold", "temperature"),
    ("wind_", "wind"),
    ("strong_wind", "wind"),
    ("wave", "wave"),
    ("fog", "fog"),
    ("cloud", "other"),
]
_ORDER: tuple[LineKind, ...] = ("rain", "temperature", "wind", "wave", "fog", "other")
_RAIN_PLAIN = {"ฝน/ฝนฟ้าคะนอง": "ฝนหรือฝนฟ้าคะนอง"}
_WAVE_QUAL = {"สูง": "สูง", "สูงประมาณ": "สูงราว", "สูงมากกว่า": "สูงกว่า", "ต่ำกว่า": "ต่ำกว่า"}


class GenerateError(ValueError):
    """บล็อกภาคที่สร้างสรุปไม่ได้ (ไม่มีค่าใดเลย) ห้ามเดา."""


def kind_of(name: str) -> LineKind | None:
    for prefix, kind in _KIND_OF_PREFIX:
        if name.startswith(prefix):
            return kind
    return None  # period_*, area_part: ตามส่วนที่อยู่ก่อนหน้า


def _num(v: Value) -> str:
    return str(v)


def _range(lo: Value, hi: Value) -> str:
    return _num(lo) if lo == hi else f"{_num(lo)}-{_num(hi)}"


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return " ".join(names[:-1]) + " และ" + names[-1]


@dataclass
class _Group:
    kind: LineKind
    area: str = ""
    facts: list[Fact] = field(default_factory=list)


def _group(facts: Sequence[Fact]) -> list[_Group]:
    """แบ่งค่าเป็นกลุ่มตามชนิด ลม/คลื่นแยกตามเขตลม ค่าที่ไม่มีชนิดตามกลุ่มก่อนหน้าในบรรทัดเดียวกัน."""
    groups: dict[tuple[LineKind, str], _Group] = {}
    area = ""
    prev: tuple[int, LineKind] | None = None
    first_in_line: dict[int, str] = {}
    for f in facts:
        first_in_line.setdefault(f.line, f.name)
        if f.name == "wind_area":
            area = str(f.value).rstrip(":").strip()
        kind = kind_of(f.name)
        if kind is None:
            # วลีช่วงวันที่ขึ้นต้นบรรทัดเป็นหัวช่วง (แยกไว้แล้ว) ไม่ใส่ซ้ำ
            if (
                f.name.startswith("period_")
                and first_in_line[f.line] == "period_text"
                and (prev is None or prev[0] != f.line)
            ):
                continue
            kind = prev[1] if prev and prev[0] == f.line else "rain"
        key = (kind, area if kind in ("wind", "wave") else "")
        groups.setdefault(key, _Group(kind, key[1])).facts.append(f)
        prev = (f.line, kind)
    return sorted(groups.values(), key=lambda g: _ORDER.index(g.kind))


def facts_dict(facts: list[Fact]) -> dict[str, FactValue]:
    out: dict[str, FactValue] = {}
    for f in facts:
        if f.name in out:
            old = out[f.name]
            out[f.name] = [*(old if isinstance(old, list) else [str(old)]), str(f.value)]
        elif f.name == "province":
            out[f.name] = [str(f.value)]
        else:
            out[f.name] = f.value
    return out


SEP = " · "
UNIT_C = "°C"


def _notes(terms: list[str], gl: dict[str, str], used: list[str]) -> list[str]:
    """ความหมายของคำที่ยังไม่เคยอ้างในบรรทัดนี้ ("ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร")."""
    fresh = [t for t in terms if t in gl and t not in used]
    used += fresh
    return [f"{t} คือ {gl[t]}" for t in fresh]


def _qualify(parts: list[str], f: Fact) -> None:
    """ส่วนขยายพื้นที่/ช่วงวัน ต่อท้ายท่อนก่อนหน้า (ไม่มีท่อนก่อนหน้า = เป็นท่อนเอง)."""
    if parts:
        parts[-1] = f"{parts[-1]} {f.value}"
    else:
        parts.append(str(f.value))


def _rain_text(
    g: _Group, lines: Sequence[str], gl: dict[str, str], used: list[str]
) -> tuple[str, list[str], list[str]]:
    """(ข้อความ, detail รายชื่อจังหวัด, notes ความหมายระดับฝน)."""
    parts: list[str] = []
    detail: list[str] = []
    notes: list[str] = []
    by: dict[str, Value] = {}
    event = ""  # ท่อนเหตุการณ์ล่าสุด ใช้นำหน้ารายชื่อจังหวัดที่ตามมา (ฝนตกหนักบางแห่ง บริเวณจังหวัด...)
    i = 0
    facts = g.facts
    # นำหน้าด้วยเหตุการณ์เฉพาะเมื่อมีหลายชุดจังหวัด (ไม่งั้นคลุมเครือว่าชุดไหนของท่อนไหน)
    runs = sum(
        1
        for k, f in enumerate(facts)
        if f.name == "province" and (k == 0 or facts[k - 1].name != "province")
    )
    while i < len(facts):
        f = facts[i]
        by[f.name] = f.value
        if f.name == "rain_area_pct_high":
            kind = str(by.get("rain_kind", "ฝน"))
            lo, hi = by["rain_area_pct_low"], f.value
            parts.append(f"{_RAIN_PLAIN.get(kind, kind)} ร้อยละ {_range(lo, hi)} ของพื้นที่")
            event = ""
        elif f.name == "province":
            names = [str(f.value)]
            while i + 1 < len(facts) and facts[i + 1].name == "province":
                i += 1
                names.append(str(facts[i].value))
            lead = "ส่วนมากที่จังหวัด" if "ส่วนมาก" in lines[f.line] else "บริเวณจังหวัด"
            detail.append(f"{event if runs > 1 else ''} {lead}{_join_names(names)}".strip())
        elif f.name in ("heavy_rain", "very_heavy_rain", "light_rain"):
            notes += _notes(rain_terms(str(f.value)), gl, used)
            parts.append(str(f.value))
            event = str(f.value)
        elif f.name in ("some_rain", "gusts", "hail"):
            parts.append(str(f.value))
            event = str(f.value)
        elif f.name in ("area_part", "period_text"):
            _qualify(parts, f)
        i += 1
    return SEP.join(parts), detail, notes


def _temperature_text(g: _Group, gl: dict[str, str], used: list[str]) -> tuple[str, list[str]]:
    v = {f.name: f.value for f in g.facts}
    parts: list[str] = []
    notes: list[str] = []
    for f in g.facts:
        if f.name == "cold":
            notes += _notes(cold_terms(str(f.value)), gl, used)
            parts.append(str(f.value))
        elif f.name == "temp_trend":
            change = (
                f" {_range(v['temp_change_low'], v['temp_change_high'])} {UNIT_C}"
                if "temp_change_low" in v
                else ""
            )
            parts.append(f"อุณหภูมิ{f.value}{change}")
        elif f.name == "temp_min_high":
            parts.append(f"ต่ำสุด {_range(v['temp_min_low'], f.value)} {UNIT_C}")
        elif f.name == "temp_max_high":
            parts.append(f"สูงสุด {_range(v['temp_max_low'], f.value)} {UNIT_C}")
        elif f.name == "peak_temp_min_high":
            feel = str(v.get("peak_feel", ""))
            notes += _notes(cold_terms(feel), gl, used)
            head = f"บน{v['peak_place']}" + (f" {feel}" if feel else "")
            parts.append(f"{head} ต่ำสุด {_range(v['peak_temp_min_low'], f.value)} {UNIT_C}")
        elif f.name in ("area_part", "period_text"):
            _qualify(parts, f)
    return SEP.join(parts), notes


def _wind_text(g: _Group) -> str:
    v = {f.name: f.value for f in g.facts}
    parts: list[str] = []
    if "wind_dir" in v:
        direction = "ลมแปรปรวน" if v["wind_dir"] == "แปรปรวน" else f"ลม{v['wind_dir']}"
        if "wind_speed_kt_low" in v:
            # พยากรณ์เดินเรือแสดงนอตตามที่ผู้ใช้ทะเลอ่าน ค่า กม./ชม. ของต้นฉบับยังอยู่ใน facts
            speed = f"{_range(v['wind_speed_kt_low'], v['wind_speed_kt_high'])} นอต"
        else:
            speed = f"{_range(v['wind_speed_kmh_low'], v['wind_speed_kmh_high'])} กม./ชม."
        parts.append(f"{direction} {speed}")
    if "strong_wind" in v:
        parts.append("ลมแรง")
    text = SEP.join(parts)
    return f"{g.area}: {text}" if g.area and text else text


# ชื่อต้นของคำบอกคลื่นแต่ละแบบ: ทั่วไป / ห่างฝั่ง / บริเวณที่มีฝนฟ้าคะนอง
_WAVE_WHERE = {"wave": "คลื่น", "wave_offshore": "ห่างฝั่ง", "wave_storm": "ที่ฝนฟ้าคะนอง"}


def _wave_text(g: _Group) -> str:
    v = {f.name: f.value for f in g.facts}
    parts: list[str] = []
    for prefix, where in _WAVE_WHERE.items():
        if f"{prefix}_m_low" in v:
            qual = _WAVE_QUAL.get(str(v[f"{prefix}_qualifier"]), str(v[f"{prefix}_qualifier"]))
            height = _range(v[f"{prefix}_m_low"], v[f"{prefix}_m_high"])
            lead = f"{where}{qual}" if prefix == "wave" else f"{where} {qual}"
            parts.append(f"{lead} {height} ม.")
    text = SEP.join(parts)
    return f"{g.area}: {text}" if g.area and text else text


def build_lines(
    facts: Sequence[Fact],
    lines: Sequence[str],
    doc_type: DocType,
    *,
    gl: dict[str, str] | None = None,
) -> list[SummaryLine]:
    """ค่าของบล็อก (หรือของช่วงวัน) -> ประโยคสรุปเรียงตามชนิด ฝน อุณหภูมิ ลม คลื่น หมอก อื่นๆ.

    gl = อภิธานที่ใช้ (ไม่ระบุ = ของชนิดนั้นตามหมายเหตุ TMD)
    """
    gl = glossary(doc_type) if gl is None else gl
    out: list[SummaryLine] = []
    for g in _group(facts):
        used: list[str] = []
        detail: list[str] = []
        notes: list[str] = []
        if g.kind == "rain":
            text, detail, notes = _rain_text(g, lines, gl, used)
        elif g.kind == "temperature":
            text, notes = _temperature_text(g, gl, used)
        elif g.kind == "wind":
            text = _wind_text(g)
        elif g.kind == "wave":
            text = _wave_text(g)
        else:
            text = SEP.join(str(f.value) for f in g.facts if f.name in ("fog", "cloud"))
        if not text.strip() and detail:
            text = detail.pop(0)  # ไม่มีท่อนหลัก (มีแต่จังหวัด) ให้ท่อนแรกเป็นข้อความ
        if not text.strip():
            continue
        facts_out = facts_dict(g.facts)
        if used:
            facts_out["glossary_terms"] = used
        out.append(SummaryLine(kind=g.kind, text=text, facts=facts_out, detail=detail, notes=notes))
    if not out:
        raise GenerateError("ไม่มีค่าที่ดึงได้ในบล็อกนี้")
    return out
