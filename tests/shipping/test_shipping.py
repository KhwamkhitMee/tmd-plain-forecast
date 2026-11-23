"""พยากรณ์เดินเรือ (Phase 11.1): แยกโครง ดึงค่า แม่แบบ ตรวจ F และ golden."""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from tmd_plain.contract import SEA_AREA_KEYS, ShippingIssue
from tmd_plain.doctypes.registry import spec_for
from tmd_plain.doctypes.shipping.build import (
    SHIPPING_PATTERNS,
    OverviewUnit,
    assemble_shipping,
    check_shipping,
)
from tmd_plain.doctypes.shipping.parse import ShippingParseError, issued_from, parse_shipping
from tmd_plain.doctypes.shipping.runner import summarize_shipping
from tmd_plain.extract.facts import extract_line
from tmd_plain.prep.doctype import detect_doc_type

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden" / "shipping"
PROCESSED = ROOT / "data" / "processed" / "shipping"
sys.path.insert(0, str(ROOT / "scripts"))
import make_golden_shipping  # noqa: E402

SAMPLE = """ลักษณะอากาศทั่วไป
03 พฤศจิกายน 2569
ลมฝ่ายตะวันออกพัดปกคลุมอ่าวไทย ทำให้บริเวณดังกล่าวมีฝนตกหนักบางแห่ง
สำหรับทะเลอันดามันและอ่าวไทย บริเวณที่มีฝนฟ้าคะนองจะมีคลื่นสูงมากกว่า 2 เมตร ชาวเรือควรเดินเรือด้วยความระมัดระวัง
ออกประกาศ 03 พฤศจิกายน 2569 13:00 น.
พยากรณ์อากาศสำหรับเรือเดินทะเล เรือในราชนาวีและเรือทำการประมง
อ่าวไทยทั้งสองฝั่ง
มีฝนฟ้าคะนอง ร้อยละ 70 ของพื้นที่ และมีฝนตกหนักถึงหนักมากบางแห่งตอนล่าง
ตอนบน: ลมตะวันออก ความเร็ว 8-16 นอต หรือ ความเร็ว 15-30 กม./ชม.
ทะเลมีคลื่นสูงประมาณ 1 เมตร บริเวณที่มีฝนฟ้าคะนองคลื่นสูงมากกว่า 2 เมตร
อ่าวไทยตอนล่าง : ลมแปรปรวน ความเร็ว 8-16 นอต หรือ 15-30 กม./ชม.
ทะเลมีคลื่นสูง 1 - 2 เมตร บริเวณที่มีฝนฟ้าคะนองคลื่นสูงมากกว่า 2 เมตร
ทะเลอันดามันและช่องแคบมะละกา
มีฝนฟ้าคะนอง ร้อยละ 60 ของพื้นที่
ลมตะวันออก ความเร็ว 8-18 นอต หรือ 15-35 กม./ชม.
ทะเลมีคลื่นสูง 1 เมตร ห่างฝั่งคลื่นสูง 1-2 เมตร บริเวณที่มีฝนฟ้าคะนองคลื่นสูงมากกว่า 2 เมตร
เส้นทางเดินเรือโกตาบารูถึงสิงคโปร์
มีฝนฟ้าคะนอง ร้อยละ 20 ของพื้นที่
ลมตะวันออกเฉียงใต้ ความเร็ว 8-16 นอต หรือ 15-30 กม./ชม.
ทะเลมีคลื่นสูงประมาณ 1 เมตร
ปลายแหลมญวน
มีฝนฟ้าคะนอง ร้อยละ 40 ของพื้นที่
ลมตะวันออก ความเร็ว 8-18 นอต หรือ 15-35 กม./ชม.
ทะเลมีคลื่นสูง 1-2 เมตร
ออกประกาศ 03 พฤศจิกายน 2569 13:00 น."""


def _label(text: str) -> str:
    # ตัวจัดประเภทจำลอง: เทสต์โครงไม่ขึ้นกับโมเดลที่เทรน
    return "advice" if "ควร" in text else "cause"


def test_detect_and_registry() -> None:
    assert detect_doc_type(SAMPLE) == "shipping"
    assert spec_for(SAMPLE).kind == "shipping"
    # หัวข้อพื้นที่ไม่ครบ = ไม่ใช่โครงเดินเรือ ไม่เดา (ไปโหมดทั่วไป)
    partial = SAMPLE.replace("ปลายแหลมญวน", "ทะเลจีนใต้")
    assert detect_doc_type(partial) == "unsupported"


def test_parse_structure() -> None:
    parsed = parse_shipping(SAMPLE)
    assert parsed.issue_id == "031120261300"
    assert parsed.issued_line == "ออกประกาศ 03 พฤศจิกายน 2569 13:00 น."
    assert set(parsed.areas) == set(SEA_AREA_KEYS)
    gulf = parsed.areas["gulf_of_thailand"]
    assert len(gulf.lines) == 1
    # "ตอนล่าง :" และ "อ่าวไทยตอนล่าง" เป็นส่วนย่อยเดียวกัน
    assert [p.name_th for p in gulf.parts] == ["ตอนบน", "ตอนล่าง"]
    assert gulf.parts[1].lines[0].startswith("ลมแปรปรวน")
    # บรรทัดออกประกาศท้ายหน้าไม่เข้าเนื้อหาพื้นที่สุดท้าย
    assert not any("ออกประกาศ" in ln for ln in parsed.areas["ca_mau_cape"].all_lines())
    assert "ชาวเรือควร" in parsed.overview


@pytest.mark.parametrize(
    "broken",
    [
        SAMPLE.replace("ลักษณะอากาศทั่วไป\n", ""),
        SAMPLE.replace("ออกประกาศ 03 พฤศจิกายน 2569 13:00 น.\nพยากรณ์", "พยากรณ์"),
        SAMPLE.replace("ปลายแหลมญวน\n", "อ่าวไทยทั้งสองฝั่ง\n"),
    ],
)
def test_parse_rejects_broken_structure(broken: str) -> None:
    with pytest.raises(ShippingParseError):
        parse_shipping(broken)


def test_issued_from() -> None:
    assert issued_from("ออกประกาศ 01 พฤศจิกายน 2569 00:00 น.") == datetime.fromisoformat(
        "2026-11-01T00:00:00+07:00"
    )
    assert issued_from("ออกประกาศ 31 กุมภาพันธ์ 2569 00:00 น.") is None
    assert issued_from("ไม่มีเวลา") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "ลมตะวันออก ความเร็ว 8-16 นอต หรือ ความเร็ว 15-30 กม./ชม.",
            {
                "wind_dir": "ตะวันออก",
                "wind_speed_kt_low": 8,
                "wind_speed_kt_high": 16,
                "wind_speed_kmh_low": 15,
                "wind_speed_kmh_high": 30,
            },
        ),
        (
            "ลมแปรปรวน ความเร็ว 8-18 นอต หรือ 15-35 กม./ชม.",
            {"wind_dir": "แปรปรวน", "wind_speed_kt_high": 18, "wind_speed_kmh_high": 35},
        ),
        # ภาพรวม: "จะมีคลื่น" = เฉพาะบริเวณที่มีฝนฟ้าคะนอง ไม่ใช่คลื่นทั่วไป
        (
            "บริเวณที่มีฝนฟ้าคะนองจะมีคลื่นสูงมากกว่า 2 เมตร",
            {"wave_storm_qualifier": "สูงมากกว่า", "wave_storm_m_low": 2},
        ),
        ("มีฝนตกหนักบางแห่งตอนล่าง", {"heavy_rain": "ฝนตกหนักบางแห่ง", "area_part": "ตอนล่าง"}),
    ],
)
def test_shipping_patterns(text: str, expected: dict[str, object]) -> None:
    facts = {f.name: f.value for f in extract_line(text, 0, SHIPPING_PATTERNS)}
    assert expected.items() <= facts.items()
    assert "wave_m_low" not in facts or "จะมีคลื่น" not in text


def test_assemble_lines_and_advice() -> None:
    run = summarize_shipping(SAMPLE, _label)
    assert not hasattr(run, "error"), run
    issue: ShippingIssue = run.document  # type: ignore[union-attr,assignment]
    gulf = issue.areas["gulf_of_thailand"]
    assert gulf.lines[0].text.startswith("ฝนฟ้าคะนอง ร้อยละ 70 ของพื้นที่")
    assert "ใน 10" not in gulf.lines[0].text
    assert "ตอนล่าง" in gulf.lines[0].text
    # ADR 0020: เดินเรือแสดงนอตอย่างเดียว ค่า กม./ชม. ของต้นฉบับยังอยู่ใน facts
    assert gulf.parts[0].lines[0].text == "ลมตะวันออก 8-16 นอต"
    assert gulf.parts[0].lines[0].facts["wind_speed_kmh_low"] == 15
    assert gulf.parts[1].lines[0].text == "ลมแปรปรวน 8-16 นอต"
    assert [a.text for a in issue.advice] == ["ชาวเรือควรเดินเรือด้วยความระมัดระวัง"]
    assert all(line.facts["unit_role"] == "cause" for line in issue.overview)
    assert issue.source_label == "ออกประกาศ 03 พฤศจิกายน 2569 13:00 น."


def test_fidelity_catches_invented_number() -> None:
    parsed = parse_shipping(SAMPLE)
    units = [OverviewUnit("ชาวเรือควรเดินเรือด้วยความระมัดระวัง", "sh-x", "advice")]
    issue = assemble_shipping(parsed, units)
    assert check_shipping(issue, parsed) == []
    area = issue.areas["ca_mau_cape"]
    bad_line = area.lines[0].model_copy(update={"text": "มีฝนฟ้าคะนองร้อยละ 90 ของพื้นที่"})
    tampered = issue.model_copy(
        update={
            "areas": {**issue.areas, "ca_mau_cape": area.model_copy(update={"lines": [bad_line]})}
        }
    )
    assert any(e.startswith("F1") for e in check_shipping(tampered, parsed))
    rewritten = issue.model_copy(
        update={"advice": [issue.advice[0].model_copy(update={"text": "ชาวเรือควรงดออกเรือ"})]}
    )
    assert any(e.startswith("F3") for e in check_shipping(rewritten, parsed))


def test_golden_shipping() -> None:
    if not make_golden_shipping.sources_exist():
        pytest.skip("ไม่มีข้อมูลดิบ (data/raw ไม่อยู่ใน repo)")
    built = make_golden_shipping.build()
    assert sorted(built) == sorted(p.name for p in GOLDEN.glob("*.json"))
    for name, body in built.items():
        assert body == (GOLDEN / name).read_text(encoding="utf-8"), (
            f"{name}: รัน scripts/make_golden_shipping.py แล้วอ่าน diff"
        )


def test_processed_files_follow_contract() -> None:
    files = sorted(PROCESSED.glob("*.json"))
    if not files:
        pytest.skip("ยังไม่ได้รัน scripts/run_pipeline.py")
    for path in files:
        issue = ShippingIssue.model_validate(json.loads(path.read_text(encoding="utf-8")))
        assert issue.issue_id == path.stem
