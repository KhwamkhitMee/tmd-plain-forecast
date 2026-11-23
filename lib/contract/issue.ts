// สัญญาข้อมูล Issue ฝั่งเว็บ (Zod) เขียนมือให้ตรงกับ lib/contract/issue.schema.json ที่ส่งออกจาก Pydantic
// เทสต์ issue.test.ts ตรวจว่าชื่อฟิลด์ตรงกับ JSON Schema และไฟล์ใน data/processed ผ่านทุกไฟล์
import { z } from "zod";

export const REGION_KEYS = [
  "north",
  "northeast",
  "central",
  "east",
  "south_east_coast",
  "south_west_coast",
  "bangkok_vicinity",
] as const;

export const regionKeySchema = z.enum(REGION_KEYS);
export const docTypeSchema = z.enum(["daily", "sevenday"]);
export const lineKindSchema = z.enum(["rain", "temperature", "wind", "wave", "fog", "other"]);

export const factValueSchema = z.union([z.string(), z.number(), z.boolean(), z.array(z.string())]);

export const summaryLineSchema = z.strictObject({
  kind: lineKindSchema,
  text: z.string().min(1),
  facts: z.record(z.string(), factValueSchema).default({}),
  // ข้อความรอง (รายชื่อจังหวัด) และความหมายระดับฝน/หนาวตามหมายเหตุ TMD (ADR 0020)
  detail: z.array(z.string()).default([]),
  notes: z.array(z.string()).default([]),
});

export const periodSchema = z
  .strictObject({
    start: z.iso.date(),
    end: z.iso.date(),
    lines: z.array(summaryLineSchema).min(1),
  })
  .refine((p) => p.start <= p.end, { message: "start ต้องไม่หลัง end" });

export const adviceItemSchema = z
  .strictObject({
    // คัดจากต้นฉบับตรงๆ ห้ามเขียนเอง
    text: z.string().min(1),
    scope: z.array(regionKeySchema).min(1),
    general: z.boolean(),
    source_unit_id: z.string().min(1),
  })
  .refine((a) => new Set(a.scope).size === a.scope.length, { message: "scope มีภาคซ้ำ" })
  .refine((a) => !a.general || a.scope.length === REGION_KEYS.length, {
    message: "ข้อแนะนำทั่วไปต้องมี scope ครบ 7 ภาค",
  });

export const regionSummarySchema = z.strictObject({
  lines: z.array(summaryLineSchema).default([]),
  periods: z.array(periodSchema).default([]),
  advice: z.array(adviceItemSchema).default([]),
});

export const issueSchema = z
  .strictObject({
    issue_id: z.string(),
    doc_type: docTypeSchema,
    issued_at: z.iso.datetime({ offset: true }),
    source_label: z.string().min(1),
    regions: z.record(regionKeySchema, regionSummarySchema),
    general_advice: z.array(adviceItemSchema).default([]),
    pipeline_version: z.string().min(1),
  })
  .superRefine((issue, ctx) => {
    const idPattern = issue.doc_type === "daily" ? /^\d{12}$/ : /^\d{6}$/;
    if (!idPattern.test(issue.issue_id)) {
      ctx.addIssue({ code: "custom", message: `issue_id ไม่ตรงรูปแบบของ ${issue.doc_type}` });
    }
    for (const key of REGION_KEYS) {
      const region = issue.regions[key];
      if (issue.doc_type === "daily" && (region.periods.length > 0 || region.lines.length === 0)) {
        ctx.addIssue({ code: "custom", message: `พยากรณ์รายวันต้องมี lines และไม่มี periods (${key})` });
      }
      if (issue.doc_type === "sevenday" && region.periods.length === 0) {
        ctx.addIssue({ code: "custom", message: `พยากรณ์ 7 วันต้องมี periods (${key})` });
      }
      if (region.advice.some((a) => !a.scope.includes(key))) {
        ctx.addIssue({ code: "custom", message: `คำแนะนำในภาค ${key} ต้องมี ${key} ใน scope` });
      }
    }
    if (issue.general_advice.some((a) => !a.general)) {
      ctx.addIssue({ code: "custom", message: "general_advice รับเฉพาะรายการที่ general=true" });
    }
  });

export type RegionKey = z.infer<typeof regionKeySchema>;
export type LineKind = z.infer<typeof lineKindSchema>;
export type DocType = z.infer<typeof docTypeSchema>;
export type SummaryLine = z.infer<typeof summaryLineSchema>;
export type Period = z.infer<typeof periodSchema>;
export type AdviceItem = z.infer<typeof adviceItemSchema>;
export type RegionSummary = z.infer<typeof regionSummarySchema>;
export type Issue = z.infer<typeof issueSchema>;
