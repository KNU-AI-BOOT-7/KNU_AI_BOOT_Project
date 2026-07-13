/** 날짜/시간/전화번호 포맷 헬퍼 */

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** ISO 문자열 → "오늘 14:20" / "어제 09:12" / "4월 17일" */
export function formatRelativeDate(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';

  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dayDiff = Math.round((startOf(now) - startOf(d)) / 86400000);
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  if (dayDiff === 0) return `오늘 ${hm}`;
  if (dayDiff === 1) return `어제 ${hm}`;
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}월 ${d.getDate()}일`;
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}`;
}

/** 근거 상세 헤더용 "23.02.02" */
export function formatShortDate(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const yy = String(d.getFullYear()).slice(2);
  return `${yy}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`;
}

/** 초 → "01:12" (통화 시간/타임스탬프) */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${pad(m)}:${pad(sec)}`;
}

/** 전화번호 하이픈 정리 (예: 01074125290 → 010-7412-5290) */
export function formatPhone(raw?: string | null): string {
  if (!raw) return '알 수 없음';
  const digits = raw.replace(/\D/g, '');
  if (digits.length === 11) return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  if (digits.length === 10) return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  return raw;
}
