export function asOf(series, date, maxAgeDays = 7) {
  const row = series
    .filter((r) => r[0] <= date)
    .sort((a, b) => b[0].localeCompare(a[0]))[0];
  if (!row) return null;
  return (Date.parse(date) - Date.parse(row[0])) / 86400000 <= maxAgeDays
    ? row
    : null;
}
export function impliedHistory(sys, epad) {
  const lookup = new Map(epad.map((r) => [r[0], r[1]]));
  return sys
    .map((r) => [r[0], lookup.has(r[0]) ? r[1] + lookup.get(r[0]) : null, null])
    .filter((r) => r[1] !== null);
}
export function withGaps(series) {
  return series.flatMap((row, i) =>
    i && (Date.parse(row[0]) - Date.parse(series[i - 1][0])) / 86400000 > 7
      ? [
          [
            new Date(Date.parse(series[i - 1][0]) + 86400000)
              .toISOString()
              .slice(0, 10),
            null,
            null,
          ],
          row,
        ]
      : [row],
  );
}
export function priceGroups(rows, grain) {
  const map = new Map();
  for (const row of rows) {
    const key =
      grain === 'month'
        ? row[0].slice(0, 7)
        : grain === 'day'
          ? row[0].slice(0, 10)
          : grain === 'hour'
            ? row[0].slice(11, 13)
            : row[0];
    const v = map.get(key) || { label: key, sum: 0, count: 0, negative: 0 };
    v.sum += row[1];
    v.count++;
    v.negative += row[1] < 0 ? 1 : 0;
    map.set(key, v);
  }
  return [...map.values()]
    .sort((a, b) =>
      grain === 'interval'
        ? Date.parse(a.label) - Date.parse(b.label)
        : a.label.localeCompare(b.label),
    )
    .map((v) => ({
      ...v,
      price: v.sum / v.count,
      negative_hours: v.negative * 0.25,
    }));
}
export function csvText(headers, rows) {
  const safe = (v) => {
    let t = v == null ? '' : String(v);
    if (typeof v === 'string' && /^[=+@\-\t\r]/.test(t)) t = "'" + t;
    return '"' + t.replaceAll('"', '""') + '"';
  };
  return (
    '\uFEFF' +
    [headers, ...rows].map((row) => row.map(safe).join(';')).join('\r\n')
  );
}
export function downloadCsv(name, headers, rows) {
  const u = URL.createObjectURL(
    new Blob([csvText(headers, rows)], { type: 'text/csv;charset=utf-8' }),
  );
  const a = document.createElement('a');
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
