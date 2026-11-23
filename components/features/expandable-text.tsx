"use client";

import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/cn";

// ข้อความรอง (รายชื่อจังหวัด) ยาวเกิน 2 บรรทัดพับไว้ กด "ดูทั้งหมด" เพื่อกาง · ข้อความครบอยู่ใน DOM เสมอ (พับด้วย CSS)
// ปุ่มโผล่เฉพาะเมื่อข้อความถูกตัดจริง (วัดจากความสูง) ข้อความสั้นไม่มีปุ่ม
export function ExpandableText({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const [clamped, setClamped] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);
  const id = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // วัดใน callback ของ ResizeObserver (เรียกครั้งแรกทันทีที่ observe และเมื่อความกว้างเปลี่ยน)
    const observer = new ResizeObserver(() => {
      if (!open) setClamped(el.scrollHeight > el.clientHeight + 1);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [open, text]);

  return (
    <div>
      <p ref={ref} id={id} className={cn("text-body-sm text-body", !open && "line-clamp-2")}>
        {text}
      </p>
      {clamped || open ? (
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex min-h-9 items-center text-body-sm font-semibold text-ink underline underline-offset-2 pointer-coarse:min-h-11"
        >
          {open ? "ย่อ" : "ดูทั้งหมด"}
        </button>
      ) : null}
    </div>
  );
}
