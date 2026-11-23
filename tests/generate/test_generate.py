import json
import sys
from pathlib import Path

import pytest

from tmd_plain.contract import Issue
from tmd_plain.extract.facts import extract_block
from tmd_plain.generate.assemble import default_source_label, issued_at_from_id
from tmd_plain.generate.fidelity import check_issue
from tmd_plain.generate.glossary import cold_terms, glossary, rain_terms
from tmd_plain.generate.templates import GenerateError, build_lines

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import make_golden_issues as golden  # noqa: E402

FORBIDDEN = ("โอกาส", "ความน่าจะเป็น")


def lines_for(block: list[str], doc_type: str = "daily"):
    return build_lines(extract_block(block), block, doc_type)  # type: ignore[arg-type]


def test_glossary_uses_tmd_thresholds_per_doc_type() -> None:
    assert glossary("daily")["ฝนหนัก"] == "ฝน 35.1-90.0 มิลลิเมตร"
    assert glossary("sevenday")["ฝนหนัก"] == "ฝน 35.1-110.0 มิลลิเมตร"
    assert glossary("daily")["อากาศหนาว"] == "อุณหภูมิ 8.0-15.9 องศาเซลเซียส"
    assert rain_terms("ฝนตกหนักถึงหนักมากบางแห่ง") == ["ฝนหนัก", "ฝนหนักมาก"]
    assert cold_terms("อากาศเย็นถึงหนาว") == ["อากาศเย็น", "อากาศหนาว"]
    assert cold_terms("อากาศหนาวเย็น") == []


def test_rain_line_is_concise_and_keeps_provinces_in_detail() -> None:
    [rain] = lines_for(["มีฝนฟ้าคะนองร้อยละ 30 ของพื้นที่", "ส่วนมากบริเวณจังหวัดสระบุรี และนครปฐม"])
    assert rain.kind == "rain"
    assert rain.text == "ฝนฟ้าคะนอง ร้อยละ 30 ของพื้นที่"
    assert rain.detail == ["ส่วนมากที่จังหวัดสระบุรี และนครปฐม"]
    assert rain.facts["province"] == ["สระบุรี", "นครปฐม"]
    # ADR 0020: ไม่มีค่าที่คำนวณ ("ราว N ใน 10 ส่วน") ในข้อความหรือ facts
    assert "ใน 10" not in rain.text
    assert "rain_area_tenths_low" not in rain.facts and "derived_formula" not in rain.facts
    assert not any(w in rain.text for w in FORBIDDEN)


def test_lines_are_ordered_by_kind_and_glossary_goes_to_notes() -> None:
    out = lines_for(
        [
            "ลมตะวันออก ความเร็ว 10-20 กม./ชม.",
            "อากาศเย็นกับมีหมอกบางในตอนเช้า",
            "อุณหภูมิต่ำสุด 18-23 องศาเซลเซียส",
            "มีฝนฟ้าคะนอง ร้อยละ 70 ของพื้นที่ และมีฝนตกหนักบางแห่ง",
        ]
    )
    assert [line.kind for line in out] == ["rain", "temperature", "wind", "fog"]
    assert out[0].text == "ฝนฟ้าคะนอง ร้อยละ 70 ของพื้นที่ · ฝนตกหนักบางแห่ง"
    assert out[0].notes == ["ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร"]
    assert out[0].facts["glossary_terms"] == ["ฝนหนัก"]
    assert out[1].text == "อากาศเย็น · ต่ำสุด 18-23 °C"
    assert out[1].notes == ["อากาศเย็น คือ อุณหภูมิ 16.0-22.9 องศาเซลเซียส"]
    assert out[2].text == "ลมตะวันออก 10-20 กม./ชม."
    assert "(" not in "".join(line.text for line in out)


def test_several_province_groups_keep_which_event_they_belong_to() -> None:
    [rain] = lines_for(
        [
            "มีฝนฟ้าคะนองร้อยละ 70 ของพื้นที่ และมีฝนตกหนักบางแห่ง บริเวณจังหวัดชุมพร และสุราษฎร์ธานี",
            "มีฝนตกหนักมากบางพื้นที่ บริเวณจังหวัดสงขลา และปัตตานี",
        ]
    )
    assert rain.text == "ฝนฟ้าคะนอง ร้อยละ 70 ของพื้นที่ · ฝนตกหนักบางแห่ง · ฝนตกหนักมากบางพื้นที่"
    assert rain.detail == [
        "ฝนตกหนักบางแห่ง บริเวณจังหวัดชุมพร และสุราษฎร์ธานี",
        "ฝนตกหนักมากบางพื้นที่ บริเวณจังหวัดสงขลา และปัตตานี",
    ]
    assert [n.split(" คือ")[0] for n in rain.notes] == ["ฝนหนัก", "ฝนหนักมาก"]


def test_wind_and_waves_split_by_wind_area() -> None:
    out = lines_for(
        [
            "ตั้งแต่จังหวัดชุมพรขึ้นมา: ลมตะวันออก ความเร็ว 15-35 กม./ชม.",
            "ทะเลมีคลื่นสูง 1-2 เมตร",
            "ตั้งแต่จังหวัดสุราษฎร์ธานีลงไป: ลมตะวันออกเฉียงใต้ ความเร็ว 20-35 กม./ชม.",
            "ทะเลมีคลื่นสูงประมาณ 2 เมตร",
        ]
    )
    assert [(line.kind, line.text.split(":")[0]) for line in out] == [
        ("wind", "ตั้งแต่จังหวัดชุมพรขึ้นมา"),
        ("wind", "ตั้งแต่จังหวัดสุราษฎร์ธานีลงไป"),
        ("wave", "ตั้งแต่จังหวัดชุมพรขึ้นมา"),
        ("wave", "ตั้งแต่จังหวัดสุราษฎร์ธานีลงไป"),
    ]
    assert out[1].text.endswith("ลมตะวันออกเฉียงใต้ 20-35 กม./ชม.")
    assert out[3].text.endswith("คลื่นสูงราว 2 ม.")


def test_block_without_facts_is_an_error_not_a_guess() -> None:
    with pytest.raises(GenerateError):
        lines_for(["ข้อความทดสอบที่ไม่มีค่า"])


def test_issue_meta_helpers() -> None:
    assert issued_at_from_id("daily", "161120261800").isoformat() == "2026-11-16T18:00:00+07:00"
    assert default_source_label("daily", "011120261800") == "ประจำวันที่ 1 พฤศจิกายน 2569 รอบ 18.00 น."
    assert default_source_label("sevenday", "261116") == "ฉบับวันที่ 16 พฤศจิกายน 2569"


@pytest.mark.parametrize("name", sorted(golden.CASES))
def test_golden_issue_is_valid_contract_without_chance_wording(name: str) -> None:
    text = (ROOT / "tests" / "golden" / "issues" / f"{name}.json").read_text(encoding="utf-8")
    issue = Issue.model_validate(json.loads(text))
    for region in issue.regions.values():
        for line in [*region.lines, *(ln for p in region.periods for ln in p.lines)]:
            assert not any(w in line.text for w in FORBIDDEN), line.text


@pytest.mark.parametrize("name", sorted(golden.CASES))
def test_golden_issue_matches_and_passes_fidelity(name: str) -> None:
    if not golden.source_path(name).exists():
        pytest.skip("ไม่มีข้อมูลดิบ (data/raw ไม่อยู่ใน repo)")
    issue, parsed = golden.build(name)
    expected = (ROOT / "tests" / "golden" / "issues" / f"{name}.json").read_text(encoding="utf-8")
    assert golden.render(issue) == expected
    assert check_issue(issue, parsed) == []
