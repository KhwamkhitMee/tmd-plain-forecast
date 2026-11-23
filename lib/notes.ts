// รวมความหมายระดับฝน/ความหนาว (SummaryLine.notes) ของหลายบรรทัดเป็นรายการเดียว ไม่ซ้ำ เรียงตามที่พบครั้งแรก (ADR 0020)
import type { SummaryLine } from "@/lib/contract/issue";

export function collectNotes(lines: Pick<SummaryLine, "notes">[]): string[] {
  const seen = new Set<string>();
  for (const line of lines) for (const note of line.notes) seen.add(note);
  return [...seen];
}
