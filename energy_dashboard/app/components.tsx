'use client';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
export const fmt = (v: number | null | undefined, d = 1) =>
  v == null || !Number.isFinite(v)
    ? '—'
    : new Intl.NumberFormat('sv-SE', {
        maximumFractionDigits: d,
        minimumFractionDigits: d,
      }).format(v);
export const monthName = (s: string) =>
  new Date(s + '-15T12:00:00Z').toLocaleDateString('sv-SE', {
    month: 'long',
    year: 'numeric',
  });
export function Picker({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="picker">
      <span>{label}</span>
      <Select
        value={value}
        onValueChange={(v) => v && onChange(v)}
        items={options}
      >
        <SelectTrigger
          className="h-10 min-w-36 bg-card px-3"
          aria-label={label}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
export function Stat({
  label,
  value,
  unit,
  context,
}: {
  label: string;
  value: string;
  unit?: string;
  context: string;
}) {
  return (
    <div className="stat">
      <p>{label}</p>
      <div>
        {value}
        <span>{unit}</span>
      </div>
      <small>{context}</small>
    </div>
  );
}
export function Plot({
  rows,
  series,
  unit = 'MWh',
}: {
  rows: Record<string, unknown>[];
  series: { key: string; name: string; color: string; bar?: boolean }[];
  unit?: string;
}) {
  return (
    <figure
      className="plot"
      aria-label={series.map((s) => s.name).join(' och ') + ', ' + unit}
    >
      <span className="plot-unit">{unit}</span>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <ComposedChart
          data={rows}
          margin={{ left: 0, right: 12, top: 28, bottom: 12 }}
        >
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="label"
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            minTickGap={28}
          />
          <YAxis
            width={58}
            tickFormatter={(v) => fmt(v, 0)}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--card)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
              borderRadius: 8,
            }}
            formatter={(v) => fmt(Number(v), 2) + ' ' + unit}
          />
          {series.map((s) =>
            s.bar ? (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.name}
                fill={s.color}
                radius={[3, 3, 0, 0]}
                maxBarSize={36}
                isAnimationActive={false}
              />
            ) : (
              <Line
                key={s.key}
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ),
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </figure>
  );
}
