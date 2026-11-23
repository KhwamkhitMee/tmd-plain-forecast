import { ViewTransition } from "react";

import { AdviceList } from "@/components/features/advice-list";
import { ForecastCard } from "@/components/features/forecast-card";
import { Card } from "@/components/ui/card";
import { Disclosure } from "@/components/ui/disclosure";
import { REGION_KEYS, type Issue, type RegionKey } from "@/lib/contract/issue";
import { cn } from "@/lib/cn";
import { REGION_LABELS } from "@/lib/format/thai";
import { collectNotes } from "@/lib/notes";

type IssueSummaryProps = {
  issue: Issue;
  // null = ครบ 7 ภาค, มีค่า = โฟกัสภาคเดียว
  region?: RegionKey | null;
};

// ข้อแนะนำทั่วไป + การ์ด 7 ภาค ของฉบับหนึ่ง ใช้ร่วมกันทั้งหน้า / และ /demo
// การ์ดแต่ละภาคมีชื่อ view transition ของตัวเอง เปลี่ยนภาค/ชนิดพยากรณ์ (query ในหน้าเดียวกัน):
// การ์ดที่ยังอยู่ = update (เลื่อนและขยายเข้าที่ใหม่), การ์ดที่หาย = exit (จางออก)
// การ์ดที่มาใหม่ใช้อนิเมชัน CSS ของการ์ดเอง (enter-up เหลื่อมเวลา) ไม่ซ้อนกับ view transition
// การ์ดคีย์เดิมเป็น element เดิม จึงเป็น update ไม่ใช่ share · default="none" กันทรานสิชันอื่นที่ไม่เกี่ยว
export function IssueSummary({ issue, region = null }: IssueSummaryProps) {
  const regions = region ? [region] : REGION_KEYS;
  // ความหมายระดับฝน/ความหนาวของการ์ดที่แสดงอยู่ รวมเป็นกล่องพับเดียว (ADR 0020) ไม่แทรกทุกบรรทัด
  const notes = collectNotes(
    regions.flatMap((key) => [...issue.regions[key].lines, ...issue.regions[key].periods.flatMap((p) => p.lines)]),
  );
  return (
    <>
      {issue.general_advice.length > 0 ? (
        <Card className="animate-enter-up space-y-3">
          <h2 className="text-title-md">ข้อแนะนำทั่วไป (ทุกภาค)</h2>
          <AdviceList items={issue.general_advice} />
        </Card>
      ) : null}

      <h2 className="sr-only">สรุปรายภาค</h2>
      <div className={cn("grid gap-4", !region && "sm:grid-cols-2 lg:grid-cols-3")}>
        {regions.map((key, i) => (
          <ViewTransition
            key={key}
            name={`region-${key}`}
            update="region-morph"
            share="region-morph"
            exit="region-exit"
            default="none"
          >
            <ForecastCard
              title={REGION_LABELS[key]}
              summary={issue.regions[key]}
              focused={region !== null}
              index={i}
              className={cn(
                region && "mx-auto w-full max-w-3xl",
                // 7 ใบ: ใบสุดท้ายกว้างเต็มแถว ไม่เหลือช่องว่าง (ui-spec หัวข้อ 4)
                !region && i === regions.length - 1 && "sm:col-span-2 lg:col-span-3",
              )}
            />
          </ViewTransition>
        ))}
      </div>

      {notes.length > 0 ? (
        <Disclosure summary="ความหมายระดับฝนและอากาศ (ตามหมายเหตุของ TMD)">
          <ul className="space-y-1.5 text-body-md text-ink">
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </>
  );
}
