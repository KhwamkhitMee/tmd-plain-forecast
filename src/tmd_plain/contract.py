"""สัญญาข้อมูล v2 (docs/spec/data-contract.md, ADR 0017): ต้นฉบับของรูปข้อมูลที่ทุกขั้นและฝั่งเว็บใช้ร่วม.

เปลี่ยนไฟล์นี้ต้องเขียน ADR ก่อน แล้วรัน scripts/export_schema.py ให้ JSON Schema ฝั่งเว็บตรงกัน
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "2"

RegionKey = Literal[
    "north",
    "northeast",
    "central",
    "east",
    "south_east_coast",
    "south_west_coast",
    "bangkok_vicinity",
]
REGION_KEYS: tuple[RegionKey, ...] = (
    "north",
    "northeast",
    "central",
    "east",
    "south_east_coast",
    "south_west_coast",
    "bangkok_vicinity",
)
REGION_LABELS_TH: dict[RegionKey, str] = {
    "north": "ภาคเหนือ",
    "northeast": "ภาคตะวันออกเฉียงเหนือ",
    "central": "ภาคกลาง",
    "east": "ภาคตะวันออก",
    "south_east_coast": "ภาคใต้ฝั่งตะวันออก (อ่าวไทย)",
    "south_west_coast": "ภาคใต้ฝั่งตะวันตก (อันดามัน)",
    "bangkok_vicinity": "กรุงเทพมหานครและปริมณฑล",
}

UnitLabel = Literal["weather", "advice", "cause", "other"]
LABELS: tuple[UnitLabel, ...] = ("weather", "advice", "cause", "other")

DocType = Literal["daily", "sevenday"]
DOC_TYPES: tuple[DocType, ...] = ("daily", "sevenday")

LineKind = Literal["rain", "temperature", "wind", "wave", "fog", "other"]

ErrorCode = Literal["unsupported_document", "too_large", "extract_failed", "empty_file"]
ERROR_MESSAGES_TH: dict[ErrorCode, str] = {
    # ความหมายตั้งแต่ 10.3 (ADR 0017): PDF ชนิดอื่นได้โหมดทั่วไป จึงปฏิเสธเฉพาะไฟล์ที่ไม่ใช่ PDF
    "unsupported_document": "ไฟล์นี้ไม่ใช่ PDF กรุณาเลือกไฟล์ PDF จากเว็บไซต์กรมอุตุนิยมวิทยา",
    "too_large": "ไฟล์ใหญ่เกิน 4 MB กรุณาเลือกไฟล์พยากรณ์ฉบับเดียว",
    "extract_failed": "อ่านหรือสรุปข้อความในไฟล์ไม่สำเร็จ ไฟล์อาจเป็นภาพสแกนที่ไม่มีข้อความหรือไฟล์เสีย กรุณาลองไฟล์อื่น",
    "empty_file": "ไฟล์ว่างเปล่า กรุณาเลือกไฟล์ใหม่",
}

# ค่าที่ดึงได้ (ใช้ตรวจ F1-F5) เก็บเป็นชนิดพื้นฐานเท่านั้นเพื่อให้ JSON ฝั่งเว็บตรวจง่าย
FactValue = str | int | float | bool | list[str]

_DAILY_ID = re.compile(r"\d{12}")  # รหัสรอบ DDMMYYYYHHMM (ปี ค.ศ.)
_SEVENDAY_ID = re.compile(r"\d{6}")  # YYMMDD ตามชื่อไฟล์ t_YYMMDD.pdf


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SummaryLine(_Model):
    kind: LineKind
    text: str = Field(min_length=1)
    facts: dict[str, FactValue] = Field(default_factory=dict)
    # ข้อความรอง (ADR 0020): รายชื่อจังหวัดของประโยคฝน ใช้พับ/กางในหน้าเว็บ · ว่าง = ไม่เขียนลงไฟล์ (exclude_if)
    # จึงข้อความที่คัดจากต้นฉบับ (เตือนภัย รายสัปดาห์ ฯลฯ) เหมือนเดิมทุกไบต์
    detail: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    # ความหมายของระดับฝน/ความหนาวตามหมายเหตุของ TMD ("ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร") หน้าเว็บรวมแสดงครั้งเดียวต่อหน้า
    notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class Period(_Model):
    start: date
    end: date
    lines: list[SummaryLine] = Field(min_length=1)

    @model_validator(mode="after")
    def _start_not_after_end(self) -> Period:
        if self.start > self.end:
            raise ValueError("start ต้องไม่หลัง end")
        return self


class AdviceItem(_Model):
    text: str = Field(min_length=1)  # คัดจากต้นฉบับตรงๆ ห้ามเขียนเอง
    scope: list[RegionKey] = Field(min_length=1)
    general: bool
    source_unit_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _general_means_all_regions(self) -> AdviceItem:
        if self.general and set(self.scope) != set(REGION_KEYS):
            raise ValueError("ข้อแนะนำทั่วไปต้องมี scope ครบ 7 ภาค")
        if len(set(self.scope)) != len(self.scope):
            raise ValueError("scope มีภาคซ้ำ")
        return self


class RegionSummary(_Model):
    lines: list[SummaryLine] = Field(default_factory=list)
    periods: list[Period] = Field(default_factory=list)
    advice: list[AdviceItem] = Field(default_factory=list)


class Issue(_Model):
    issue_id: str
    doc_type: DocType
    issued_at: datetime
    source_label: str = Field(min_length=1)
    regions: dict[RegionKey, RegionSummary]
    general_advice: list[AdviceItem] = Field(default_factory=list)
    pipeline_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_shape(self) -> Issue:
        if set(self.regions) != set(REGION_KEYS):
            raise ValueError("regions ต้องมีครบ 7 ภาคพอดี")
        if self.issued_at.tzinfo is None:
            raise ValueError("issued_at ต้องมีเขตเวลา (+07:00)")
        pattern = _DAILY_ID if self.doc_type == "daily" else _SEVENDAY_ID
        if not pattern.fullmatch(self.issue_id):
            raise ValueError(f"issue_id ไม่ตรงรูปแบบของ {self.doc_type}")
        for key, region in self.regions.items():
            if self.doc_type == "daily" and region.periods:
                raise ValueError(f"พยากรณ์รายวันต้องไม่มี periods ({key})")
            if self.doc_type == "sevenday" and not region.periods:
                raise ValueError(f"พยากรณ์ 7 วันต้องมี periods ({key})")
            if self.doc_type == "daily" and not region.lines:
                raise ValueError(f"พยากรณ์รายวันต้องมี lines ({key})")
            for item in region.advice:
                if key not in item.scope:
                    raise ValueError(f"คำแนะนำในภาค {key} ต้องมี {key} ใน scope")
        if any(not item.general for item in self.general_advice):
            raise ValueError("general_advice รับเฉพาะรายการที่ general=true")
        return self


class ErrorDetail(_Model):
    code: ErrorCode
    message_th: str = Field(min_length=1)


class SummarizeError(_Model):
    ok: Literal[False]
    error: ErrorDetail


def error_response(code: ErrorCode) -> SummarizeError:
    """สร้างคำตอบข้อผิดพลาดพร้อมข้อความภาษาไทยมาตรฐาน."""
    return SummarizeError(
        ok=False, error=ErrorDetail(code=code, message_th=ERROR_MESSAGES_TH[code])
    )


# ---------------------------------------------------------------------------
# v2 (ADR 0017): ชนิดเอกสารรอบ 1, โหมดทั่วไปของ /demo และ trace
# ---------------------------------------------------------------------------

StoredDocType = Literal["daily", "sevenday", "shipping", "warning", "weekly"]
STORED_DOC_TYPES: tuple[StoredDocType, ...] = ("daily", "sevenday", "shipping", "warning", "weekly")

ResultKind = Literal["issue", "shipping", "warning", "weekly", "generic"]
RESULT_KINDS: tuple[ResultKind, ...] = ("issue", "shipping", "warning", "weekly", "generic")

SeaAreaKey = Literal["gulf_of_thailand", "andaman_malacca", "kota_bharu_singapore", "ca_mau_cape"]
SEA_AREA_KEYS: tuple[SeaAreaKey, ...] = (
    "gulf_of_thailand",
    "andaman_malacca",
    "kota_bharu_singapore",
    "ca_mau_cape",
)
# ชื่อพื้นที่ตามหัวข้อในพยากรณ์เดินเรือ (พบครบ 4 พื้นที่ใน 100/100 ฉบับที่เก็บ)
SEA_AREA_LABELS_TH: dict[SeaAreaKey, str] = {
    "gulf_of_thailand": "อ่าวไทยทั้งสองฝั่ง",
    "andaman_malacca": "ทะเลอันดามันและช่องแคบมะละกา",
    "kota_bharu_singapore": "เส้นทางเดินเรือโกตาบารูถึงสิงคโปร์",
    "ca_mau_cape": "ปลายแหลมญวน",
}

GenericWarning = Literal["not_tmd_like"]

TraceStepId = Literal[
    "read_pdf",
    "clean",
    "detect_type",
    "segment",
    "units",
    "tokenize",
    "filter_tokens",
    "classify",
    "scope",
    "extract",
    "template",
    "verify",
    "result",
]
TraceStatus = Literal["done", "skipped", "failed"]
# ค่าที่ trace เก็บได้: ชนิดพื้นฐาน รายการ และแผนที่ชื่อ -> ตัวเลข (เช่น คะแนน NB ต่อป้าย)
TraceValue = str | int | float | bool | list[str] | list[int | float] | dict[str, int | float]

# เพดานของ trace (ข้อตัดสินใจ V4 ข) ใช้ทั้งตอนสร้าง (10.2) และตอนตรวจ
TRACE_MAX_BYTES = 256 * 1024
TRACE_MAX_ITEMS = 50

# <ปี พ.ศ.>_<เลขประกาศ>
_WARNING_ID = re.compile(r"\d{4}_\d+")
# 315/2569
_NOTICE_NO = re.compile(r"\d+/\d{4}")


def _require_tz(value: datetime | None, name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{name} ต้องมีเขตเวลา (+07:00)")


def _require_unique(items: list[str], name: str) -> None:
    if len(set(items)) != len(items):
        raise ValueError(f"{name} มีค่าซ้ำ")


class QuotedAdvice(_Model):
    # คัดจากต้นฉบับตรงๆ ห้ามเขียนเอง
    text: str = Field(min_length=1)
    regions: list[RegionKey] = Field(default_factory=list)
    source_unit_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_regions(self) -> QuotedAdvice:
        _require_unique(list(self.regions), "regions")
        return self


class SeaPart(_Model):
    # "ตอนบน" / "ตอนล่าง" ตามต้นฉบับ
    name_th: str = Field(min_length=1)
    lines: list[SummaryLine] = Field(min_length=1)


class SeaArea(_Model):
    name_th: str = Field(min_length=1)
    lines: list[SummaryLine] = Field(default_factory=list)
    parts: list[SeaPart] = Field(default_factory=list)

    @model_validator(mode="after")
    def _has_content(self) -> SeaArea:
        if not self.lines and not self.parts:
            raise ValueError("พื้นที่ทะเลต้องมี lines หรือ parts")
        return self


class ShippingIssue(_Model):
    issue_id: str
    doc_type: Literal["shipping"]
    issued_at: datetime
    source_label: str = Field(min_length=1)
    overview: list[SummaryLine] = Field(default_factory=list)
    areas: dict[SeaAreaKey, SeaArea]
    advice: list[QuotedAdvice] = Field(default_factory=list)
    pipeline_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_shape(self) -> ShippingIssue:
        if not _DAILY_ID.fullmatch(self.issue_id):
            raise ValueError("issue_id ของพยากรณ์เดินเรือต้องเป็น DDMMYYYYHHMM")
        _require_tz(self.issued_at, "issued_at")
        if set(self.areas) != set(SEA_AREA_KEYS):
            raise ValueError("areas ต้องมีครบ 4 พื้นที่ทะเลพอดี")
        for key, area in self.areas.items():
            if area.name_th != SEA_AREA_LABELS_TH[key]:
                raise ValueError(f"ชื่อพื้นที่ {key} ไม่ตรงต้นฉบับ")
        return self


class EffectPeriod(_Model):
    # คำต่อคำ เช่น "มีผลกระทบจนถึงวันที่ ..."
    text: str = Field(min_length=1)
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _start_not_after_end(self) -> EffectPeriod:
        if self.start and self.end and self.start > self.end:
            raise ValueError("start ต้องไม่หลัง end")
        return self


class WarningNotice(_Model):
    issue_id: str
    doc_type: Literal["warning"]
    issued_at: datetime
    source_label: str = Field(min_length=1)
    # "เรื่อง ..." คำต่อคำ = คำบอกความรุนแรงของ TMD เอง
    title: str = Field(min_length=1)
    series_no: int = Field(ge=1)
    notice_no: str
    # ไม่มีบรรทัดช่วงที่มีผลในต้นฉบับ = None (พบ 1 ใน 155 ฉบับ, ADR 0018)
    effect: EffectPeriod | None = None
    next_issue_at: datetime | None = None
    regions: list[RegionKey] = Field(default_factory=list)
    provinces: list[str] = Field(default_factory=list)
    lines: list[SummaryLine] = Field(default_factory=list)
    precautions: list[QuotedAdvice] = Field(default_factory=list)
    pipeline_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_shape(self) -> WarningNotice:
        if not _WARNING_ID.fullmatch(self.issue_id):
            raise ValueError("issue_id ของประกาศเตือนภัยต้องเป็น <ปี พ.ศ.>_<เลขประกาศ>")
        if not _NOTICE_NO.fullmatch(self.notice_no):
            raise ValueError("notice_no ต้องเป็น <เลข>/<ปี พ.ศ.>")
        number, year = self.notice_no.split("/")
        if self.issue_id != f"{year}_{number}":
            raise ValueError("issue_id ต้องตรงกับ notice_no")
        _require_tz(self.issued_at, "issued_at")
        _require_tz(self.next_issue_at, "next_issue_at")
        if self.next_issue_at is not None and self.next_issue_at <= self.issued_at:
            raise ValueError("next_issue_at ต้องหลัง issued_at")
        _require_unique(list(self.regions), "regions")
        _require_unique(self.provinces, "provinces")
        return self


class TableCell(_Model):
    # ช่องตารางคำต่อคำ
    text: str = Field(min_length=1)
    facts: dict[str, FactValue] = Field(default_factory=dict)


class WeeklyRegion(_Model):
    lines: list[SummaryLine] = Field(default_factory=list)
    rain_max: TableCell | None = None
    temp_max: TableCell | None = None
    temp_min: TableCell | None = None


class WeeklySummary(_Model):
    issue_id: str
    doc_type: Literal["weekly"]
    issued_at: datetime
    source_label: str = Field(min_length=1)
    week_start: date
    week_end: date
    overview: list[SummaryLine] = Field(default_factory=list)
    regions: dict[RegionKey, WeeklyRegion]
    pipeline_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_shape(self) -> WeeklySummary:
        if not _DAILY_ID.fullmatch(self.issue_id):
            raise ValueError("issue_id ของสรุปรายสัปดาห์ต้องเป็น DDMMYYYYHHMM")
        _require_tz(self.issued_at, "issued_at")
        if self.week_start > self.week_end:
            raise ValueError("week_start ต้องไม่หลัง week_end")
        if set(self.regions) != set(REGION_KEYS):
            raise ValueError("regions ต้องมีครบ 7 ภาคพอดี")
        return self


class GenericUnit(_Model):
    unit_id: str = Field(min_length=1)
    # คำต่อคำ
    text: str = Field(min_length=1)
    label: UnitLabel
    confidence: float = Field(ge=0.0, le=1.0)
    uncertain: bool
    regions: list[RegionKey] = Field(default_factory=list)
    provinces: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)


class GenericSection(_Model):
    heading: str | None = None
    units: list[GenericUnit] = Field(default_factory=list)


class GlossaryEntry(_Model):
    term: str = Field(min_length=1)
    # จาก resources/glossary.toml เท่านั้น
    explanation: str = Field(min_length=1)


class GenericDocument(_Model):
    title: str | None = None
    tmd_like: bool
    warnings: list[GenericWarning] = Field(default_factory=list)
    page_count: int = Field(ge=1)
    char_count: int = Field(ge=0)
    has_region_headings: bool
    sections: list[GenericSection] = Field(default_factory=list)
    glossary: list[GlossaryEntry] = Field(default_factory=list)
    truncated: bool = False

    @model_validator(mode="after")
    def _check_shape(self) -> GenericDocument:
        if ("not_tmd_like" in self.warnings) == self.tmd_like:
            raise ValueError("warnings ต้องมี not_tmd_like เมื่อ tmd_like=false เท่านั้น")
        _require_unique(list(self.warnings), "warnings")
        ids = [u.unit_id for s in self.sections for u in s.units]
        _require_unique(ids, "unit_id")
        return self


class TraceStep(_Model):
    id: TraceStepId
    title_th: str = Field(min_length=1)
    status: TraceStatus
    note_th: str = ""
    data: dict[str, TraceValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _items_within_limit(self) -> TraceStep:
        for key, value in self.data.items():
            if isinstance(value, (list, dict)) and len(value) > TRACE_MAX_ITEMS:
                raise ValueError(f"trace {self.id}.{key} เกิน {TRACE_MAX_ITEMS} ชิ้น")
        return self


class Trace(_Model):
    steps: list[TraceStep] = Field(default_factory=list)
    truncated: bool = False

    @model_validator(mode="after")
    def _check_shape(self) -> Trace:
        _require_unique([s.id for s in self.steps], "step id")
        # วัดแบบไม่มีช่องว่าง ให้ตรงกับ JSON.stringify ฝั่งเว็บ
        compact = json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
        )
        size = len(compact.encode("utf-8"))
        if size > TRACE_MAX_BYTES:
            raise ValueError(f"trace ใหญ่เกิน {TRACE_MAX_BYTES} ไบต์")
        return self


class SummarizeIssueOk(_Model):
    ok: Literal[True]
    kind: Literal["issue"]
    document: Issue
    trace: Trace | None = None


class SummarizeShippingOk(_Model):
    ok: Literal[True]
    kind: Literal["shipping"]
    document: ShippingIssue
    trace: Trace | None = None


class SummarizeWarningOk(_Model):
    ok: Literal[True]
    kind: Literal["warning"]
    document: WarningNotice
    trace: Trace | None = None


class SummarizeWeeklyOk(_Model):
    ok: Literal[True]
    kind: Literal["weekly"]
    document: WeeklySummary
    trace: Trace | None = None


class SummarizeGenericOk(_Model):
    ok: Literal[True]
    kind: Literal["generic"]
    document: GenericDocument
    trace: Trace | None = None


# คำตอบสำเร็จของ /api/summarize (v2 ตั้งแต่ 10.2) แยกชนิดด้วย kind
SummarizeOk = Annotated[
    SummarizeIssueOk
    | SummarizeShippingOk
    | SummarizeWarningOk
    | SummarizeWeeklyOk
    | SummarizeGenericOk,
    Field(discriminator="kind"),
]

DocumentModel = Issue | ShippingIssue | WarningNotice | WeeklySummary | GenericDocument
OkResponse = (
    SummarizeIssueOk
    | SummarizeShippingOk
    | SummarizeWarningOk
    | SummarizeWeeklyOk
    | SummarizeGenericOk
)
_OK_MODELS: dict[ResultKind, type[_Model]] = {
    "issue": SummarizeIssueOk,
    "shipping": SummarizeShippingOk,
    "warning": SummarizeWarningOk,
    "weekly": SummarizeWeeklyOk,
    "generic": SummarizeGenericOk,
}


def ok_response(
    kind: ResultKind, document: DocumentModel, trace: Trace | None = None
) -> OkResponse:
    """สร้างคำตอบสำเร็จตามชนิด (document ผิดชนิดกับ kind -> ValidationError)."""
    return _OK_MODELS[kind](ok=True, kind=kind, document=document, trace=trace)  # type: ignore[return-value]
