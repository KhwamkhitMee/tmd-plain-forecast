import type { CSSProperties } from "react";

import { AdviceList } from "@/components/features/advice-list";
import { ExpandableText } from "@/components/features/expandable-text";
import { LineIcon } from "@/components/features/line-icon";
import { Card } from "@/components/ui/card";
import type { RegionSummary, SummaryLine } from "@/lib/contract/issue";
import { cn } from "@/lib/cn";
import { LINE_KIND_LABELS, thaiDateRange } from "@/lib/format/thai";

type ForecastCardProps = {
  title: string;
  summary: RegionSummary;
  className?: string;
  // โหมดโฟกัสภาคเดียว: หัวข้อใหญ่ขึ้น
  focused?: boolean;
  // ลำดับการ์ด ใช้เหลื่อมเวลาตอนการ์ดเข้า (D13)
  index?: number;
};

// บรรทัดสรุปพร้อมไอคอนและป้ายชนิด ใช้ร่วมกับการ์ดพื้นที่ทะเล (shipping-summary.tsx)
export function SummaryLines({ lines }: { lines: SummaryLine[] }) {
  return (
    <dl className="grid content-start gap-3.5">
      {lines.map((line, i) => (
        <div key={`${line.kind}-${i}`}>
          <dt className="flex items-center gap-1.5 text-caption font-semibold text-body">
            <LineIcon kind={line.kind} />
            {LINE_KIND_LABELS[line.kind]}
          </dt>
          <dd className="mt-0.5 text-body-md text-ink">{line.text}</dd>
          {line.detail.map((item) => (
            <dd key={item} className="mt-1">
              <ExpandableText text={item} />
            </dd>
          ))}
        </div>
      ))}
    </dl>
  );
}

// การ์ดภาค (ดีไซน์ A): บรรทัดสรุปมีไอคอน + ป้ายชนิด, คำแนะนำของภาคใต้เส้นคั่น · เข้าแบบเหลื่อมเวลา ยกขึ้นตอนโฮเวอร์
export function ForecastCard({ title, summary, className, focused = false, index = 0 }: ForecastCardProps) {
  return (
    <Card
      motion="lift"
      className={cn("flex animate-enter-up flex-col gap-4 stagger", className)}
      style={{ "--i": index } as CSSProperties}
    >
      <h3 className={focused ? "text-display-sm" : "text-title-md"}>{title}</h3>
      {summary.lines.length > 0 ? <SummaryLines lines={summary.lines} /> : null}
      {summary.periods.map((period) => (
        <section key={`${period.start}-${period.end}`} className="space-y-2">
          <h4 className="text-title-sm">{thaiDateRange(period.start, period.end)}</h4>
          <SummaryLines lines={period.lines} />
        </section>
      ))}
      {summary.advice.length > 0 ? (
        <section className="mt-auto space-y-2 border-t border-hairline pt-4">
          <h4 className="text-title-sm">คำแนะนำสำหรับภาคนี้</h4>
          <AdviceList items={summary.advice} />
        </section>
      ) : null}
    </Card>
  );
}
