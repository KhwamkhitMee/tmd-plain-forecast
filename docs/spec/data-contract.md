# สัญญาข้อมูล v1

สถานะ: **v1 เป็นโค้ดแล้ว (Phase 1.1, 2026-11-16) ผู้ใช้รีวิวผ่าน 2026-11-16** รูปร่างเหมือนร่าง v0 ทุกอย่าง (จึงไม่ต้องมี ADR) เพิ่มกฎตรวจและข้อความข้อผิดพลาดภาษาไทย ตั้งแต่นี้การเปลี่ยนใดๆ ต้องบันทึก ADR

**ต้นฉบับอยู่ในโค้ด:** `src/tmd_plain/contract.py` (Pydantic) → `scripts/export_schema.py` → `lib/contract/issue.schema.json`, `lib/contract/summarize-response.schema.json` (ห้ามแก้ไฟล์ JSON เอง เทสต์จะตรวจว่าตรงกับโค้ด) · ไฟล์ตัวอย่าง: `tests/fixtures/contract/` (เขียนมือจากฉบับจริง ใช้กับฝั่งเว็บก่อนท่อประมวลผลเสร็จ)

**กฎตรวจที่เพิ่มใน v1:** `regions` ต้องมีครบ 7 คีย์พอดี · `issued_at` ต้องมีเขตเวลา · `issue_id` รายวัน 12 หลัก (DDMMYYYYHHMM) / 7 วัน 6 หลัก (YYMMDD) · รายวันต้องมี `lines` และห้ามมี `periods`; 7 วันต้องมี `periods` · คำแนะนำในภาคใดต้องมีภาคนั้นใน `scope` · `general=true` ต้องมี scope ครบ 7 ภาค และอยู่ใน `general_advice` เท่านั้น · `Period.start` ไม่หลัง `end` และมีอย่างน้อย 1 บรรทัด · `facts` เก็บได้แค่ string / ตัวเลข / bool / list ของ string · ห้ามมีฟิลด์นอกสัญญา (`extra="forbid"`)

**หลักการ:** Pydantic (Python) เป็นต้นฉบับของรูปข้อมูล -> ส่งออก JSON Schema (Draft 2020-12) -> ฝั่งเว็บตรวจด้วย Zod ที่เขียนมือใน `lib/contract/issue.ts` (Phase 4.1 ไม่ใช้ `json-schema-to-typescript` เพราะยังไม่ได้รับอนุญาต dependency) และมีเทสต์ Vitest เทียบชื่อฟิลด์ของ Zod กับ `issue.schema.json`

## 1. ค่าคงที่ที่ตกลงแล้ว

**ภาค 7 แบบ** (คีย์ตรงกับฟิลด์ของ API พยากรณ์รายวันของ TMD)

| คีย์ | ชื่อไทย | รหัสในตารางแมปภาค |
|---|---|---|
| `north` | ภาคเหนือ | N |
| `northeast` | ภาคตะวันออกเฉียงเหนือ | NE |
| `central` | ภาคกลาง | C |
| `east` | ภาคตะวันออก | E |
| `south_east_coast` | ภาคใต้ฝั่งตะวันออก (อ่าวไทย) | SE |
| `south_west_coast` | ภาคใต้ฝั่งตะวันตก (อันดามัน) | SW |
| `bangkok_vicinity` | กรุงเทพมหานครและปริมณฑล | BKK |

**ป้ายหน่วย:** `weather`, `advice`, `cause`, `other`
**ชนิดเอกสาร:** `daily`, `sevenday`

## 2. ผลสรุปต่อฉบับ

```
Issue {
  issue_id: string            // รายวัน: รหัสรอบ DDMMYYYYHHMM; 7 วัน: YYMMDD
  doc_type: "daily" | "sevenday"
  issued_at: string           // ISO 8601 พร้อมเขตเวลา +07:00
  source_label: string        // ข้อความป้ายต้นฉบับ เช่น "ประจำวันที่ 16 พฤศจิกายน 2569 17.00 น."
  regions: { <region_key>: RegionSummary }   // ครบ 7 คีย์
  general_advice: AdviceItem[]               // คำแนะนำที่ใช้กับทุกภาค
  pipeline_version: string
}
RegionSummary {
  lines: SummaryLine[]        // รายวัน: ข้อความสรุปสภาพอากาศ
  periods: Period[]           // 7 วัน: แยกตามช่วงวัน (รายวันเป็น [])
  advice: AdviceItem[]        // เฉพาะภาคนี้
}
Period { start: string, end: string, lines: SummaryLine[] }   // วันที่ ISO
SummaryLine { kind: "rain"|"temperature"|"wind"|"wave"|"fog"|"other", text: string, facts: object, detail?: string[], notes?: string[] }   // detail/notes: ADR 0020 (ว่าง = ไม่มีในไฟล์)
AdviceItem { text: string, scope: <region_key>[], general: boolean, source_unit_id: string }
```
- `text` ของ `SummaryLine` เป็นประโยคภาษาไทยกระชับที่เขียนตามแม่แบบ (ไม่มีวงเล็บขยายความ ไม่มีค่าที่คำนวณ) · `detail` = รายชื่อจังหวัดของประโยคฝน (พับ/กางในเว็บ) · `notes` = ความหมายระดับฝน/ความหนาวตามหมายเหตุ TMD ("ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร") เว็บรวมแสดงครั้งเดียวต่อหน้า ส่วน `AdviceItem.text` คัดมาจากต้นฉบับตรงๆ
- `facts` เก็บค่าที่ดึงได้ (เช่น `rain_area_pct`, `temp_min`, `temp_max`) เพื่อใช้ตรวจ F1-F5
- ไม่ใส่เวลาประมวลผลไว้ในไฟล์ผลลัพธ์ (เพื่อให้ผลซ้ำได้) ใส่ใน metadata ตอนโหลด

## 3. ฐานข้อมูล (ตารางเดียว ใน `db/schema.sql` สร้างใน Neon แล้ว Phase 0.4; role อ่านอย่างเดียว `web_reader` จาก `db/roles.sql` สร้างแล้ว 2026-11-17; โหลดด้วย `npm run load:neon` ตาม ADR 0014)

```
forecast_issue (
  issue_id     text,
  doc_type     text,          -- 'daily' | 'sevenday'
  issued_at    timestamptz,
  source_label text,
  payload      jsonb,         -- Issue ทั้งก้อน
  loaded_at    timestamptz default now(),
  primary key (doc_type, issue_id)
)
index on (doc_type, issued_at desc)
```
ข้อมูลน้อย (หลักสิบฉบับ) การเก็บ JSON ทั้งก้อนง่ายที่สุด; บทบาท DB: ผู้โหลดเขียน (`DATABASE_URL_DIRECT`), เว็บอ่านอย่างเดียว (`DATABASE_URL`)

## 4. API ของ /demo (รูปคำตอบ `lib/contract/summarize-response.schema.json`, ฟังก์ชัน `api/summarize.py` Phase 5.1, รูปคำตอบ v2 ตั้งแต่ 10.2 ดูหัวข้อ v2.7)

`POST /api/summarize` (PDF ไม่เกิน 4 MB) · body = ไฟล์ PDF ดิบ (`Content-Type: application/pdf` ไม่ใช่ multipart) · สถานะ HTTP: 200 สำเร็จ, 413 `too_large`, 422 รหัสอื่น (เนื้อคำตอบเป็น JSON ตามข้างล่างทุกกรณี) · `GET` ได้ 405 · ไฟล์ที่ไม่ขึ้นต้นด้วย `%PDF-` ได้ `unsupported_document` · `issue_id` และ `source_label` อ่านจากหัว PDF (รอบรายวัน = เวลาออกประกาศ + 1 ชม.)
- สำเร็จ: `{ "ok": true, "kind": "issue", "document": Issue, "trace": Trace | null }` (v2 ตั้งแต่ 10.2; รูป v1 `{ ok, issue }` เลิกใช้แล้ว) · `POST /api/summarize?trace=1` ได้ภาพขั้นตอน
- ผิดพลาด: `{ "ok": false, "error": { "code": "unsupported_document" | "too_large" | "extract_failed" | "empty_file", "message_th": string } }` ข้อความภาษาไทยมาตรฐานอยู่ที่ `ERROR_MESSAGES_TH` ใน `contract.py`
- ไม่เก็บไฟล์ ไม่เก็บผลลัพธ์

## 5. ชุดป้าย (ไฟล์ตารางติดป้าย)
`unit_id | doc_type | appears_in (list) | text | context_prev | context_next | suggested_label | final_label | scope (เฉพาะ advice) | reviewer | note` ดูรายละเอียดใน `labeling-guideline.md`

## 6. พารามิเตอร์โมเดล
`models/*.json`: Naive Bayes (log prior, log likelihood ต่อคำ, ค่า m, คำศัพท์) และ k-NN (เวกเตอร์ตัวอย่าง, k) ขนาดเล็ก commit ได้

---

# สัญญาข้อมูล v2 (Phase 10.1 · ผู้ใช้อนุมัติ 2026-11-18 ตามข้อเสนอ, ADR 0017)

ร่างนี้ออกแบบจากตัวอย่างจริงใน `data/raw` (เก็บใน 9.1-9.2): เดินเรือ 100 ฉบับ, ประกาศเตือนภัย 155 ฉบับ, สรุปรายสัปดาห์ 100 ฉบับ, ชุด generic 7 ไฟล์ · ต้นฉบับอยู่ใน `src/tmd_plain/contract.py` (โมเดล v2) → `scripts/export_schema.py` → `lib/contract/*.schema.json` · Zod ใน `lib/contract/documents.ts` และ `summarize.ts` · ไฟล์ตัวอย่างต่อชนิดใน `tests/fixtures/contract/`

## v2.0 หลักการ
- **ชนิดเดิมไม่เปลี่ยน:** `Issue` (รายวัน/7 วัน) คงรูปเดิมทุกฟิลด์ → `data/processed/` 35 ไฟล์เท่าเดิมทุกไบต์ ตารางและตัวโหลดเดิมใช้ได้ · `CONTRACT_VERSION` = `"2"` (อยู่แค่ใน `$comment` ของ schema ไม่อยู่ในไฟล์ผล)
- **ความถูกต้องของผลเหมือน v1 ทุกชนิด:** ข้อความที่เขียนตามแม่แบบอยู่ใน `SummaryLine` เท่านั้น และตัวเลข/จังหวัดในนั้นต้องมาจากบล็อกต้นฉบับ (F1 + ADR 0013) · คำแนะนำ หัวเรื่อง ชื่อพื้นที่ ช่องตาราง = **คัดคำต่อคำ** · ไม่สร้างระดับความรุนแรงหรือสเกลสีเอง
- ทุกโมเดล `frozen`, `extra="forbid"` เหมือน v1 · วันที่/เวลาเป็น ISO พร้อม `+07:00`
- `generic` ใช้เฉพาะ `/demo` ไม่เก็บลง DB

## v2.1 ค่าคงที่ใหม่
| ชื่อ | ค่า |
|---|---|
| `DocType` (เก็บใน DB) | `daily`, `sevenday` (เดิม) + `shipping`, `warning`, `weekly` (แผน 11) · `agro7`, `outlook3m` สงวนไว้ใน check constraint ของ DB เท่านั้น โมเดลกำหนดในแผน 12 หลังประตู 12.1 (ADR ภาคต่อ) |
| `ResultKind` (คำตอบ `/demo`) | `issue` (รายวัน/7 วัน), `shipping`, `warning`, `weekly`, `generic` |
| `SeaAreaKey` | `gulf_of_thailand` "อ่าวไทยทั้งสองฝั่ง", `andaman_malacca` "ทะเลอันดามันและช่องแคบมะละกา", `kota_bharu_singapore` "เส้นทางเดินเรือโกตาบารูถึงสิงคโปร์", `ca_mau_cape` "ปลายแหลมญวน" (พบครบ 4 พื้นที่ใน 100/100 ฉบับ; ชื่อพื้นที่ที่ไม่รู้จัก = ข้อผิดพลาดมีรหัส ไม่เดา) |
| `LineKind` | ใช้ชุดเดิม (`wave`, `wind`, `rain` ใช้กับทะเลด้วย) |
| `issue_id` | `shipping`, `weekly`: `DDMMYYYYHHMM` แบบรายวัน · `warning`: `<ปี พ.ศ.>_<เลขประกาศ>` เช่น `2569_315` (ตรงกับ `data/raw`) |

## v2.2 พยากรณ์เดินเรือ `ShippingIssue`
```
ShippingIssue {
  issue_id, doc_type: "shipping", issued_at, source_label, pipeline_version
  overview: SummaryLine[]          // จาก "ลักษณะอากาศทั่วไป" (ภาษาง่าย ตามแม่แบบ)
  areas: { <SeaAreaKey>: SeaArea } // ครบ 4 คีย์
  advice: QuotedAdvice[]           // เช่น "ชาวเรือควร..." คัดคำต่อคำ
}
SeaArea { name_th: string (คำต่อคำ), lines: SummaryLine[], parts: SeaPart[] }
  // lines = ทั้งพื้นที่ (ฝนร้อยละ N ของพื้นที่) · parts = ตอนบน/ตอนล่างของอ่าวไทย (พื้นที่อื่นเป็น [])
SeaPart { name_th: string ("ตอนบน" | "ตอนล่าง" ตามต้นฉบับ), lines: SummaryLine[] }
QuotedAdvice { text: string (คำต่อคำ), regions: RegionKey[] (ว่างได้), source_unit_id: string }
```
`facts` ของบรรทัดลม/คลื่น: `wind_dir` (คำต่อคำ เช่น "ตะวันออกเฉียงใต้", "แปรปรวน"), `wind_speed_kt_low/high`, `wind_speed_kmh_low/high` (ทั้งนอตและ กม./ชม. ตามต้นฉบับ ไม่แปลงหน่วยเอง), `wave_m_low/high`, `wave_storm_m_low/high` (ชื่อเดียวกับผลรายวัน) · ฝน: `rain_area_pct` (ร้อยละของพื้นที่ ไม่ใช่โอกาส)

## v2.3 ประกาศเตือนภัย `WarningNotice`
```
WarningNotice {
  issue_id: "2569_315", doc_type: "warning", issued_at ("ประกาศ ณ วันที่ ... เวลา ..."), source_label, pipeline_version
  title: string            // ข้อความหลังคำว่า "เรื่อง" คำต่อคำ (หลายบรรทัดรวมเป็นบรรทัดเดียว) = คำบอกความรุนแรงของ TMD เอง เช่น "ฝนตกหนักถึงหนักมากบริเวณภาคใต้"
  series_no: int           // ฉบับที่ 7
  notice_no: string        // "315/2569"
  effect: { text: string (คำต่อคำ เช่น "มีผลกระทบจนถึงวันที่ ..."), start: date | null, end: date | null } | null   // ไม่มีบรรทัดในต้นฉบับ = null (ADR 0018)
  next_issue_at: datetime | null
  regions: RegionKey[]     // ภาคที่กล่าวถึง (กฎแบบ scope.py ใน 11.2)
  provinces: string[]      // ชื่อจังหวัดที่พบ คำต่อคำ
  lines: SummaryLine[]     // ภาษาง่าย: ฝน/คลื่น/อุณหภูมิที่ลดลง พร้อม facts
  precautions: QuotedAdvice[]
}
```
- ตัวอย่างจริง 155 ฉบับมี 2 เรื่องหลัก ("ฝนตกหนักถึงหนักมาก" 128, "อากาศแปรปรวน" 27) และ**ไม่มีฟิลด์ระดับแยก** จึงไม่มี `level` ในสัญญา ใช้ `title` แทน
- ช่วงที่มีผลมี 3 แบบ ("จนถึง" 71, "ตั้งแต่" 34, "ในช่วง" 17) จึงให้ `start`/`end` เป็น null ได้ และเก็บ `text` คำต่อคำเสมอ
- ไม่เก็บชื่อผู้ลงนาม · ฟิลด์ประเภทประโยค/ชนิดภัยจากตัวจัดประเภท (11.3) จะเพิ่มด้วย ADR ภาคต่อหลังผู้ใช้อนุมัติ label set (V7)

## v2.4 สรุปรายสัปดาห์ `WeeklySummary`
```
WeeklySummary {
  issue_id, doc_type: "weekly", issued_at, source_label, pipeline_version
  week_start: date, week_end: date
  overview: SummaryLine[]                       // จากย่อหน้า "ประเทศไทย"
  regions: { <RegionKey>: WeeklyRegion }        // ครบ 7 ภาค (ต้นฉบับมีครบ 100/100)
}
WeeklyRegion { lines: SummaryLine[], rain_max: TableCell | null, temp_max: TableCell | null, temp_min: TableCell | null }
TableCell { text: string (ช่องตารางคำต่อคำ รวมวงเล็บสถานีที่สอง), facts: { value, unit, ... } }
```
ช่องตารางว่างได้จริง (หน้าฝนไม่มีอุณหภูมิ หน้าหนาวไม่มีฝน) จึงเป็น `null`

## v2.5 โหมดทั่วไป `GenericDocument` (`/demo` เท่านั้น)
```
GenericDocument {
  title: string | null            // บรรทัดหัวแรก คำต่อคำ
  tmd_like: boolean
  warnings: ("not_tmd_like")[]
  page_count: int, char_count: int
  has_region_headings: boolean    // ใช้ตัดสินว่าแสดงแท็บภาค
  sections: { heading: string | null, units: GenericUnit[] }[]
  glossary: { term: string, explanation: string }[]   // จาก resources/glossary.toml เท่านั้น
  truncated: boolean
}
GenericUnit {
  unit_id, text (คำต่อคำ), label: UnitLabel, confidence: 0..1, uncertain: boolean (ต่ำกว่าเกณฑ์ใน config.toml)
  regions: RegionKey[], provinces: string[], numbers: string[], dates: string[]   // ช่วงข้อความที่พบ คำต่อคำ
}
```
ไม่มีข้อความที่เขียนใหม่เลย · ผล JSON < 1 MB (แผน 10.3) ถ้าเกินตัดหน่วยท้ายและใส่ `truncated: true`

กติกาที่ใช้จริง (10.3, `src/tmd_plain/generic/`, ค่าตั้งใน `[generic]` ของ `config.toml`):
- โครง: ต่อบรรทัด PDF กลับเป็นย่อหน้า (บรรทัดสั้นกว่า 75% ของบรรทัดเต็มของเอกสารนั้น = จบย่อหน้า), บรรทัดสั้นไม่เกิน 40 ตัวที่ตามด้วยเนื้อความ = หัวข้อ, ข้อที่มีเลข/ขีด/ชื่อภาคขึ้นต้นบรรทัด = ย่อหน้าใหม่ · บรรทัดที่มีแค่ตัวเลขสั้นๆ (เลขหน้าที่ PDF แทรกกลางประโยค) ข้ามตอนต่อย่อหน้า การตรวจความถูกต้องจึงเทียบกับต้นฉบับที่ตัดบรรทัดเลขหน้าออก
- หน่วย: ตัดตามกติกาหน่วยเดิม (`prep/units.py`) รหัส `g-<sha1 8 ตัว>` (ข้อความซ้ำในเอกสารเดียวต่อท้าย `-2`, `-3`)
- ป้าย + ความมั่นใจ: ตัวจัดประเภทที่อนุมัติ (`models/selected.json`) ความมั่นใจ = posterior ของป้ายที่เลือก (ปัด 4 ตำแหน่ง) · `uncertain` เมื่อความมั่นใจ < `uncertain_below` (0.8) หรือสัดส่วนคำที่อยู่ในคลังคำของโมเดล < `min_known_ratio` (0.5)
- `tmd_like`: พบ "กรมอุตุนิยมวิทยา"/"tmd.go.th"/"Thai Meteorological Department" หรือสัดส่วนคำในคลังคำเฉลี่ยต่อหน่วย ≥ `tmd_vocab_ratio` (0.35, มีหน่วย ≥ 5) · วัดแล้ว: แผนที่สรุปรายสัปดาห์ที่ไม่มีชื่อกรม 0.489-0.758, สไลด์วิชา 0.102-0.171
- ไฮไลต์ (คำต่อคำ): วันที่ (เลข + เดือนเต็ม/ย่อ + ปี, ช่วงเดือน), ตัวเลข/ช่วงตัวเลขพร้อมหน่วยที่ตามมา (ไม่นับตัวเลขในวันที่), จังหวัด (ชื่อที่เป็นคำทั่วไปด้วย เลย/ตาก/แพร่/น่าน/ตราด/ตรัง นับเมื่อมี "จ." หรือ "จังหวัด" นำ), ภาคตามตารางแมปภาค v1 (`extract/scope.locations`)
- คำอธิบายศัพท์: เฉพาะเกณฑ์ความหนาว (`[cold]` ใน `glossary.toml`) เกณฑ์ฝนไม่ให้ เพราะรายวันกับ 7 วันใช้เกณฑ์ต่างกัน เอกสารชนิดอื่นเลือกชุดที่ถูกไม่ได้
- ตรวจ (`generic/fidelity.check_generic`): ข้อความทุกหน่วย หัวเรื่อง หัวข้อ อยู่ในต้นฉบับ, ตัวเลข/วันที่/จังหวัดอยู่ในหน่วยนั้น, ภาคตรงกับคำบอกที่ตั้งในหน่วย, คำอธิบายศัพท์ตรงกับ `glossary.toml` · ไม่ผ่าน = `extract_failed`
- ผลตรวจกับ PDF ที่เก็บ: [results/generic-check.md](../results/generic-check.md)

## v2.6 ภาพขั้นตอน `Trace`
```
Trace { steps: TraceStep[], truncated: boolean }
TraceStep {
  id: "read_pdf" | "clean" | "detect_type" | "segment" | "units" | "tokenize" | "filter_tokens"
      | "classify" | "scope" | "extract" | "template" | "verify" | "result"
  title_th: string, status: "done" | "skipped" | "failed", note_th: string
  data: { <key>: string | number | boolean | string[] | number[] | { <key>: number } }
}
```
- มีเฉพาะขั้นที่ไปป์ไลน์ของชนิดนั้นทำจริง (UI เรียงตาม `steps` ไม่ hard-code) · ผลลัพธ์เมื่อเปิด/ปิด trace ต้องเหมือนกันทุกไบต์
- ขนาดสูงสุดตามข้อตัดสินใจ (ข) ถ้าตัดให้ `truncated: true`

## v2.7 API `/api/summarize` v2
```
สำเร็จ:   { ok: true, kind: ResultKind, document: Issue | ShippingIssue | WarningNotice | WeeklySummary | GenericDocument, trace: Trace | null }
ผิดพลาด: { ok: false, error: { code, message_th } }   // รหัสเดิม 4 ตัว
```
- `kind` เป็นตัวแยกชนิดของ `document` (discriminated union) · ส่ง `?trace=1` จึงมี `trace` ไม่ส่งได้ `null` (10.2) · เพดาน trace เป็นค่าคงที่ในสัญญา `TRACE_MAX_BYTES` = 262144, `TRACE_MAX_ITEMS` = 50 (ทั้ง Python และ Zod)
- ความหมายรหัสเปลี่ยนเพราะมีโหมดทั่วไป (ใช้จริงตั้งแต่ 10.3): `unsupported_document` = ไม่ใช่ PDF เท่านั้น ("ไฟล์นี้ไม่ใช่ PDF ...") · PDF ที่ไม่มีชั้นข้อความ (ภาพล้วน) หรือสรุป/ตรวจไม่ผ่าน = `extract_failed` · PDF อื่นทุกชนิดที่มีข้อความได้ `kind: "generic"` (ไม่ใช่ของ TMD = `not_tmd_like`)
- หน้า `/demo` (10.4) แสดงผล `kind: "issue"` และ `"generic"` พร้อมภาพขั้นตอน และ `"warning"` ตั้งแต่ 11.4 (การ์ดเดียวกับ `/warnings`) ชนิดที่ยังไม่มีการแสดงผลใน `/demo` (`shipping`, `weekly` จนถึง 11.5) แสดงคำแจ้ง "ระบบอ่านเอกสารนี้ได้แล้ว แต่..." (`lib/upload.ts` outcome `notice`, ไม่ใช่ข้อผิดพลาด)
- รูปคำตอบเปลี่ยน (`issue` → `kind` + `document`) ใน 10.2: Python (`SummarizeOk` = union แยกด้วย `kind`, `ok_response`) และ Zod (`summarizeOkSchema`) เปลี่ยนในชุดเดียวกัน (deploy พร้อมกันบน Vercel) และลบรูป v1 แล้ว
- trace สร้างหลังท่อประมวลผลเสร็จจากผลระหว่างทาง (`tmd_plain.tracing.build_trace`, ขั้นของแต่ละชนิดใน `tmd_plain.doctypes`) ตัดให้เหลือไม่เกิน 90% ของเพดาน (เผื่อ JSON ฝั่งเว็บเขียนตัวเลขต่างกันเล็กน้อย) · คะแนนของตัวจัดประเภทใน trace ปัดทศนิยม 4 ตำแหน่ง

## v2.8 ฐานข้อมูล
- ใช้ตารางเดิม `forecast_issue` ต่อ (`payload` = เอกสารตาม `doc_type`) · migration ใน 11.1 (ผู้ใช้รัน): เปลี่ยน check constraint เป็น `doc_type in ('daily','sevenday','shipping','warning','weekly','agro7','outlook3m')` ไม่ลบข้อมูล
- SQL: `db/migrations/001-doc-type-v2.sql` (11.1; drop if exists + add constraint ในธุรกรรมเดียว รันซ้ำได้) · `db/schema.sql` สำหรับฐานใหม่มีรายการเดียวกันแล้ว · **ผู้ใช้อนุมัติ (V6) และรันเองใน Neon SQL Editor** ก่อน `npm run load:neon` ไฟล์เดินเรือ (ไม่รัน constraint เดิมจะปฏิเสธแถว shipping และธุรกรรมของตัวโหลดย้อนทั้งหมด)
- ตัวโหลดตรวจทุกไฟล์ด้วย Zod ตาม `doc_type` ก่อนเขียน (`lib/contract/stored.ts` `storedDocumentSchema` = รายวัน/7 วัน/เดินเรือ; ไฟล์ผิดสัญญาไม่ขึ้น DB) · ไฟล์ใน `lib/contract/` import กันแบบสัมพัทธ์ `./x.ts` เพราะตัวโหลดรันด้วย node ตรงๆ

## v2.9 ข้อตัดสินใจ V4 (ผู้ใช้ตอบ 2026-11-18: ตามข้อเสนอทั้งสองข้อ)
- **(ก) ป้าย `cause` / `weather`:** ข้อเสนอ: คงบทบาทเดิมในผลสรุป (ป้ายใช้คัดคำแนะนำ) และแสดงป้ายทั้ง 4 แบบใน trace และโหมดทั่วไปเท่านั้น · ถ้าเพิ่มส่วน "สาเหตุ" ในสรุปรายวัน/7 วัน ผล 35 ไฟล์จะเปลี่ยน ขัดเป้าของแผน 10 ("ชนิดเดิมไม่เปลี่ยนแม้แต่ไบต์เดียว")
- **(ข) ขนาด trace:** ข้อเสนอ: ไม่เกิน 256 KB ต่อคำตอบ และทุกรายการไม่เกิน 50 ชิ้น (หน่วย โทเคน คำเด่น)
