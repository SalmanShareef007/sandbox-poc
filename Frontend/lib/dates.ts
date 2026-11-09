const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const pad = (n: number) => String(n).padStart(2, "0");

/** Parses the demo "DD Mon YYYY" format, e.g. "17 Dec 2026". */
export function parseDemoDate(value: string): Date {
  const [day, month, year] = value.split(" ");
  const m = MONTHS.indexOf((month ?? "").slice(0, 3));
  if (!day || m < 0 || !year) return new Date(NaN);
  return new Date(Number(year), m, Number(day));
}

export const formatDemoDate = (d: Date) =>
  `${pad(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;

export const toIsoDate = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export const addDays = (d: Date, days: number) =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);

export const monthLabel = (d: Date) => `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
