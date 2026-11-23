import { describe, expect, it } from "vitest";

import { collectNotes } from "@/lib/notes";

describe("collectNotes", () => {
  it("รวมไม่ซ้ำ เรียงตามที่พบครั้งแรก", () => {
    const lines = [
      { notes: ["ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร"] },
      { notes: [] },
      { notes: ["อากาศเย็น คือ อุณหภูมิ 16.0-22.9 องศาเซลเซียส", "ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร"] },
    ];
    expect(collectNotes(lines)).toEqual([
      "ฝนหนัก คือ ฝน 35.1-90.0 มิลลิเมตร",
      "อากาศเย็น คือ อุณหภูมิ 16.0-22.9 องศาเซลเซียส",
    ]);
  });

  it("ไม่มีความหมายเลย = รายการว่าง", () => {
    expect(collectNotes([{ notes: [] }])).toEqual([]);
  });
});
