'use client';
import { useEffect, useState } from 'react';
import {
  ArrowUpRight,
  Download,
  CircleAlert,
  Info,
  FileCheck2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { fmt, monthName, Picker, Stat, Plot } from './components';
import { useQuery, oneOf, dateValue } from './use-query';
import {
  asOf,
  impliedHistory,
  withGaps,
  priceGroups,
  downloadCsv,
} from './analysis.mjs';
import type { Summary, Month, ParkDetail, SpotRow, Quote } from './types';
const cache = new Map<string, unknown>();
export function useData<T>(url: string | null) {
  const [state, setState] = useState<{
    url: string | null;
    data: T | null;
    error: string | null;
  }>({ url: null, data: null, error: null });
  useEffect(() => {
    if (!url) return;
    const control = new AbortController();
    if (cache.has(url)) {
      void Promise.resolve().then(() =>
        setState({ url, data: cache.get(url) as T, error: null }),
      );
      return;
    }
    fetch(url, { signal: control.signal })
      .then((r) => {
        if (!r.ok) throw new Error('Datautdraget kunde inte läsas.');
        return r.json();
      })
      .then((data) => {
        cache.set(url, data);
        setState({ url, data: data as T, error: null });
      })
      .catch((e) => {
        if (e.name !== 'AbortError')
          setState({ url, data: null, error: e.message });
      });
    return () => control.abort();
  }, [url]);
  return state.url === url ? state : { data: null, error: null };
}
export function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice">
      <Info size={17} />
      <span>{children}</span>
    </div>
  );
}
export function ErrorState({ error }: { error: string | null }) {
  return (
    <div className="empty" role={error ? 'alert' : 'status'}>
      {error || 'Läser valt datautdrag…'}
    </div>
  );
}
const opts = (values: string[]) => values.map((v) => ({ value: v, label: v }));
const monthOpts = Array.from({ length: 12 }, (_, i) => ({
  value: String(i + 1).padStart(2, '0'),
  label: new Date(2024, i, 15).toLocaleDateString('sv-SE', { month: 'long' }),
}));
export const selectedParks = (data: Summary, zone: string, month: string) =>
  Object.entries(data.parks)
    .filter(([, p]) => zone === 'all' || p.zone === zone)
    .map(([key, p]) => ({
      key,
      ...p,
      m: p.months.find((m) => m.month === month),
    }))
    .filter((p) => p.m);
const goodMonth = (m: Month) => m.complete && m.coverage >= 99.9;
function exportParks(data: Summary, zone: string, month: string) {
  downloadCsv(
    'parker-' + month + '.csv',
    [
      'Park',
      'Period',
      'MWh netto',
      'Budget MWh',
      'Energitäckning %',
      'PR % (matchade intervall)',
      'PR status',
      'Capture EUR/MWh',
      'Prisenergitäckning %',
      'Inverterestimat MWh',
      'Dataversion',
    ],
    selectedParks(data, zone, month).map((p) => [
      p.name,
      month,
      p.m!.energy_mwh,
      p.m!.budget_mwh,
      p.m!.coverage,
      p.m!.pr_quality === 'insufficient' ? null : p.m!.pr,
      p.m!.pr_quality,
      p.m!.capture,
      p.m!.price_coverage,
      p.m!.estimated_mwh,
      data.dataset_version,
    ]),
  );
}
export function ParksView({
  data,
  month,
  zone,
}: {
  data: Summary;
  month: string;
  zone: string;
}) {
  const [detail, setDetail] = useState<string | null>(null),
    [sort, setSort] = useState('capacity');
  const selected = selectedParks(data, zone, month);
  const complete =
    selected.length > 0 && selected.every((p) => goodMonth(p.m!));
  const energy = selected.reduce((s, p) => s + (p.m!.energy_mwh || 0), 0),
    budget = selected.reduce((s, p) => s + p.m!.budget_mwh, 0),
    priced = selected.reduce((s, p) => s + p.m!.priced_mwh, 0),
    revenue = selected.reduce((s, p) => s + (p.m!.spot_value_eur || 0), 0),
    exported = selected.reduce((s, p) => s + (p.m!.export_mwh || 0), 0),
    estimated = selected.reduce((s, p) => s + p.m!.estimated_mwh, 0);
  const monthList = [
    ...new Set(selected.flatMap((p) => p.months.map((m) => m.month))),
  ]
    .filter((m) => m <= month)
    .sort()
    .slice(-12);
  const trend = monthList.map((mo) => {
    const ms = selected.map((p) => p.months.find((m) => m.month === mo));
    return {
      label: mo.slice(2),
      energy: ms.every((m) => m && goodMonth(m))
        ? ms.reduce((s, m) => s + (m!.energy_mwh || 0), 0)
        : null,
      partial: ms.some((m) => !m || !goodMonth(m))
        ? ms.reduce((s, m) => s + (m?.energy_mwh || 0), 0)
        : null,
      budget: ms.every(Boolean)
        ? ms.reduce((s, m) => s + m!.budget_mwh, 0)
        : null,
    };
  });
  if (!selected.length)
    return (
      <div className="empty">
        Inga parkobservationer finns för det valda elområdet och månaden.
      </div>
    );
  const sorted = [...selected].sort((a, b) =>
    sort === 'capture'
      ? (b.m!.capture || 0) - (a.m!.capture || 0)
      : sort === 'energy'
        ? (b.m!.energy_mwh || 0) - (a.m!.energy_mwh || 0)
        : b.capacity_kwp - a.capacity_kwp,
  );
  const findings = selected
    .filter((p) => !goodMonth(p.m!) || p.m!.pr_quality !== 'provisional')
    .slice(0, 3);
  return (
    <>
      <div className="stats">
        <Stat
          label="Nätleverans · netto"
          value={fmt(energy, 0)}
          unit="MWh"
          context={
            (complete ? '' : 'Ofullständig period · ') +
            fmt(estimated, 0) +
            ' MWh via inverterestimat'
          }
        />
        <Stat
          label="Mot månadsbudget"
          value={complete ? fmt((energy / budget - 1) * 100) : '—'}
          unit={complete ? '%' : undefined}
          context={
            complete
              ? fmt(budget, 0) + ' MWh · PVsyst'
              : 'Bedöms när hela periodens energi finns'
          }
        />
        <Stat
          label="Parkcapture · spot"
          value={fmt(priced ? revenue / priced : null)}
          unit="€/MWh"
          context={
            fmt(exported ? (priced / exported) * 100 : null) +
            ' % av känd exporterad energi prismatchad'
          }
        />
      </div>
      <div className="main-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>Produktion över tid</h2>
            <div className="legend">
              <span>
                <i />
                Nätleverans
              </span>
              <span>
                <i className="budget" />
                Budget
              </span>
              <span>
                <i className="partial" />
                Delvis data
              </span>
            </div>
          </div>
          <Plot
            rows={trend}
            series={[
              {
                key: 'energy',
                name: 'Nätleverans',
                color: 'var(--chart-1)',
                bar: true,
              },
              {
                key: 'partial',
                name: 'Tillgänglig del av perioden',
                color: 'var(--chart-4)',
                bar: true,
              },
              { key: 'budget', name: 'Budget', color: 'var(--chart-2)' },
            ]}
          />
        </section>
        <section className="attention">
          <p className="eyebrow">ATT UNDERSÖKA</p>
          {findings.length ? (
            findings.map((p) => (
              <button key={p.key} onClick={() => setDetail(p.key)}>
                <CircleAlert size={17} />
                <span>
                  <strong>{p.name}</strong>
                  <span>
                    {!goodMonth(p.m!)
                      ? 'Energisignalen är ofullständig'
                      : p.m!.pr_quality === 'review'
                        ? 'PR behöver granskas'
                        : 'PR behöver bättre underlag'}
                  </span>
                  <small>
                    Energi {fmt(p.m!.coverage)} % · POA {fmt(p.m!.poa_coverage)}{' '}
                    %
                  </small>
                </span>
                <ArrowUpRight size={15} />
              </button>
            ))
          ) : (
            <p>Inga automatiska kvalitetsflaggor i den valda månaden.</p>
          )}
          <div className="attention-note">
            <Info size={16} />
            <span>
              Kvalitetsflaggorna fastställer inte orsaken till en
              produktionsavvikelse.
            </span>
          </div>
        </section>
      </div>
      <section className="panel park-table">
        <div className="panel-heading">
          <h2>Parker · {monthName(month)}</h2>
          <div className="inline-controls">
            <Picker
              label="Sortering"
              value={sort}
              onChange={setSort}
              options={[
                { value: 'capacity', label: 'Storlek' },
                { value: 'energy', label: 'Produktion' },
                { value: 'capture', label: 'Capture' },
              ]}
            />
            <Button
              variant="outline"
              className="h-10"
              onClick={() => exportParks(data, zone, month)}
            >
              <Download />
              CSV
            </Button>
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Park</TableHead>
              <TableHead className="text-right">MWh</TableHead>
              <TableHead className="text-right">Mot budget</TableHead>
              <TableHead className="text-right">kWh/kWp</TableHead>
              <TableHead className="text-right">PR</TableHead>
              <TableHead className="text-right">Capture €/MWh</TableHead>
              <TableHead className="text-right">Energitäckning</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((p) => (
              <TableRow key={p.key}>
                <TableCell>
                  <button
                    className="park-link"
                    onClick={() => setDetail(p.key)}
                  >
                    {p.name}
                    <ArrowUpRight size={14} />
                  </button>
                  <small>
                    {p.zone} · {fmt(p.capacity_kwp / 1000)} MWp
                  </small>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fmt(p.m!.energy_mwh, 0)}
                </TableCell>
                <TableCell className="text-right">
                  {goodMonth(p.m!)
                    ? fmt(
                        ((p.m!.energy_mwh || 0) / p.m!.budget_mwh - 1) * 100,
                      ) + ' %'
                    : 'Delvis data'}
                </TableCell>
                <TableCell className="text-right">
                  {fmt(
                    p.m!.energy_mwh == null
                      ? null
                      : p.m!.energy_mwh / (p.capacity_kwp / 1000),
                    0,
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {p.m!.pr_quality === 'insufficient' ? (
                    <span className="quality-label">Otillräcklig POA</span>
                  ) : (
                    fmt(p.m!.pr) + ' %'
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fmt(p.m!.capture)}
                </TableCell>
                <TableCell className="text-right">
                  {fmt(p.m!.coverage)} %
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>
      <Notice>
        PR är preliminär. Nätleverans använder giltig grid-mätare, inklusive
        verkliga nollvärden. Saknad eller ogiltig mätare kan ersättas av ett
        märkt inverterestimat. Det är en annan energidefinition än i tidigare
        rapporter.
      </Notice>
      <Sheet open={!!detail} onOpenChange={(v) => !v && setDetail(null)}>
        <SheetContent className="w-full sm:max-w-3xl overflow-y-auto p-6">
          <SheetHeader>
            <SheetTitle>{detail && data.parks[detail].name}</SheetTitle>
            <SheetDescription>
              {monthName(month)} · Daglig produktion och beräkningsunderlag
            </SheetDescription>
          </SheetHeader>
          {detail && (
            <ParkDetails
              key={detail + month}
              data={data}
              parkKey={detail}
              month={month}
            />
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
function ParkDetails({
  data,
  parkKey,
  month,
}: {
  data: Summary;
  parkKey: string;
  month: string;
}) {
  const p = data.parks[parkKey],
    m = p.months.find((m) => m.month === month)!;
  const { data: detail, error } = useData<ParkDetail>(
    data.data_path + '/parks/' + parkKey + '/' + month + '.json',
  );
  const [day, setDay] = useState('all');
  if (!detail) return <ErrorState error={error} />;
  const rows =
    day === 'all'
      ? detail.daily.map((d) => ({
          label: d.date.slice(8),
          energy: d.energy_mwh,
        }))
      : detail.intervals
          .filter((r) => r[0].slice(0, 10) === day)
          .map((r) => ({ label: r[0].slice(11, 16), energy: r[1] }));
  return (
    <>
      <div className="detail-metrics">
        <Stat
          label="Nätleverans"
          value={fmt(m.energy_mwh, 0)}
          unit="MWh"
          context={fmt(m.coverage) + ' % energitäckning'}
        />
        <Stat
          label="Performance ratio"
          value={m.pr_quality === 'insufficient' ? '—' : fmt(m.pr)}
          unit={m.pr_quality === 'insufficient' ? undefined : '%'}
          context={fmt(m.poa_coverage) + ' % matchad POA-täckning'}
        />
      </div>
      <Picker
        label="Detaljnivå"
        value={day}
        onChange={setDay}
        options={[
          { value: 'all', label: 'Alla dagar' },
          ...detail.daily.map((d) => ({ value: d.date, label: d.date })),
        ]}
      />
      <Plot
        rows={rows}
        unit={day === 'all' ? 'MWh' : 'MW'}
        series={[
          {
            key: 'energy',
            name: day === 'all' ? 'Nätleverans' : 'Effekt',
            color: 'var(--chart-1)',
            bar: day === 'all',
          },
        ]}
      />
      <Button
        variant="outline"
        onClick={() =>
          downloadCsv(
            p.name + '-' + month + '.csv',
            [
              'Lokal tid',
              'Effektiv MW',
              'Grid MW',
              'Inverter MW',
              'POA W/m²',
              'Spot EUR/MWh',
              'Energikälla',
            ],
            detail.intervals.filter(
              (r) => day === 'all' || r[0].slice(0, 10) === day,
            ),
          )
        }
      >
        <Download />
        Exportera kvartunderlaget
      </Button>
      <h3>Nyckeltalets underlag</h3>
      <dl className="facts">
        <dt>Specifik produktion</dt>
        <dd>
          {fmt(
            m.energy_mwh == null
              ? null
              : m.energy_mwh / (p.capacity_kwp / 1000),
          )}{' '}
          kWh/kWp
        </dd>
        <dt>Inverterestimat</dt>
        <dd>{fmt(m.estimated_mwh)} MWh</dd>
        <dt>Energi med spotpris</dt>
        <dd>{fmt(m.priced_mwh)} MWh</dd>
        <dt>Energi-/prismatchning</dt>
        <dd>{fmt(m.price_coverage)} % av känd export</dd>
        <dt>Capture rate</dt>
        <dd>
          {fmt(m.capture_rate)} % · matchad baseload{' '}
          {fmt(m.matched_baseload_eur)} €/MWh
        </dd>
        <dt>Export vid negativa priser</dt>
        <dd>
          {fmt(m.negative_mwh)} MWh · {fmt(m.negative_value_eur)} €
        </dd>
        <dt>POA-intervall</dt>
        <dd>{fmt(m.poa_coverage)} % av hela perioden</dd>
        <dt>Tillgänglighetssignal</dt>
        <dd>
          {fmt(m.availability)} % · {fmt(m.availability_coverage)} % täckning
        </dd>
        <dt>PR-status</dt>
        <dd>
          {m.pr_quality === 'insufficient'
            ? 'Otillräckligt underlag'
            : m.pr_quality === 'review'
              ? 'Behöver granskas'
              : 'Preliminär'}
        </dd>
        <dt>PR-formel</dt>
        <dd>Energi / (MWp × kWh/m²), på samma giltiga intervall</dd>
        <dt>Källa</dt>
        <dd>Bazefield · elprisetjustnu.se · PVsyst</dd>
        <dt>Version</dt>
        <dd>
          {data.metric_version} / {data.dataset_version}
        </dd>
      </dl>
      <Notice>
        Förlustorsaker kräver verifierad instrålning och driftsinformation. En
        energilucka tolkas aldrig automatiskt som driftstopp eller svagt väder.
      </Notice>
    </>
  );
}
export function MarketView({ data }: { data: Summary }) {
  const years = [...new Set(data.market.SE3.map((m) => m.month.slice(0, 4)))]
    .sort()
    .reverse();
  const [year, setYear] = useQuery('market_year', '2024', oneOf(years)),
    [zone, setZone] = useQuery(
      'market_zone',
      'SE3',
      oneOf(['SE1', 'SE2', 'SE3', 'SE4']),
    ),
    [compare, setCompare] = useQuery(
      'compare',
      '2023',
      oneOf(['none', ...years]),
    ),
    [grain, setGrain] = useQuery(
      'grain',
      'month',
      oneOf(['month', 'day', 'interval']),
    ),
    [month, setMonth] = useQuery(
      'market_month',
      '06',
      oneOf(monthOpts.map((m) => m.value)),
    ),
    [day, setDay] = useQuery(
      'day',
      '01',
      (v) => /^\d{2}$/.test(v) && +v >= 1 && +v <= 31,
    ),
    [shape, setShape] = useQuery(
      'shape',
      'time',
      oneOf(['time', 'duration', 'hour']),
    );
  useEffect(() => {
    if (+day > new Date(+year, +month, 0).getDate()) setDay('01');
  }, [year, month, day, setDay]);
  const { data: raw, error } = useData<SpotRow[]>(
    grain !== 'month'
      ? data.data_path + '/spot/' + zone + '-' + year + '.json'
      : null,
  );
  const ms = data.market[zone].filter((m) => m.month.startsWith(year));
  const chosenRaw =
    raw?.filter(
      (r) =>
        r[0].slice(0, 7) === year + '-' + month &&
        (grain !== 'interval' || r[0].slice(8, 10) === day),
    ) || [];
  const ready = grain === 'month' || !!raw;
  const rs =
    grain === 'month'
      ? ms.map((m) => ({
          label: monthOpts[Number(m.month.slice(5)) - 1].label,
          price: m.baseload,
          comparison:
            compare === 'none'
              ? null
              : (data.market[zone].find(
                  (c) => c.month === compare + m.month.slice(4),
                )?.baseload ?? null),
          hours: m.hours,
          negative_hours: m.negative_hours,
        }))
      : shape === 'duration'
        ? [...chosenRaw]
            .sort((a, b) => b[1] - a[1])
            .filter(
              (_, i) =>
                i % Math.max(1, Math.floor(chosenRaw.length / 400)) === 0,
            )
            .map((r, i) => ({
              label: String(
                i * Math.max(1, Math.floor(chosenRaw.length / 400)) * 0.25,
              ),
              price: r[1],
              comparison: null,
            }))
        : priceGroups(chosenRaw, shape === 'hour' ? 'hour' : grain).map(
            (r) => ({
              ...r,
              label:
                shape === 'hour'
                  ? r.label + ':00'
                  : grain === 'day'
                    ? r.label.slice(8)
                    : r.label.slice(11, 16) +
                      (r.label.includes('+01:00') ? ' CET' : ' CEST'),
              comparison: null,
            }),
          );
  const hours =
    grain === 'month'
      ? ms.reduce((s, m) => s + m.hours, 0)
      : chosenRaw.length * 0.25;
  const avg =
    grain === 'month'
      ? hours
        ? ms.reduce((s, m) => s + m.baseload * m.hours, 0) / hours
        : null
      : chosenRaw.length
        ? chosenRaw.reduce((s, r) => s + r[1], 0) / chosenRaw.length
        : null;
  const neg =
    grain === 'month'
      ? ms.reduce((s, m) => s + m.negative_hours, 0)
      : chosenRaw.filter((r) => r[1] < 0).length * 0.25;
  const full =
    grain === 'month'
      ? ms.length === 12 && ms.every((m) => m.coverage >= 99.99)
      : true;
  return (
    <>
      <div className="filters">
        <Picker
          label="Elområde"
          value={zone}
          onChange={setZone}
          options={opts(['SE1', 'SE2', 'SE3', 'SE4'])}
        />
        <Picker
          label="Kalenderår"
          value={year}
          onChange={setYear}
          options={opts(years)}
        />
        <Picker
          label="Upplösning"
          value={grain}
          onChange={(v) => {
            setGrain(v);
            setShape('time');
          }}
          options={[
            { value: 'month', label: 'Månader' },
            { value: 'day', label: 'Dagar' },
            { value: 'interval', label: 'Kvartar' },
          ]}
        />
        {grain === 'month' ? (
          <Picker
            label="Jämför år"
            value={compare}
            onChange={setCompare}
            options={[
              { value: 'none', label: 'Ingen jämförelse' },
              ...opts(years),
            ]}
          />
        ) : (
          <Picker
            label="Månad"
            value={month}
            onChange={setMonth}
            options={monthOpts}
          />
        )}
        {grain === 'interval' && (
          <Picker
            label="Dag"
            value={day}
            onChange={setDay}
            options={opts(
              Array.from(
                { length: new Date(Number(year), Number(month), 0).getDate() },
                (_, i) => String(i + 1).padStart(2, '0'),
              ),
            )}
          />
        )}
      </div>
      <div className="stats">
        <Stat
          label={zone + ' · spotpris'}
          value={ready ? fmt(avg) : '…'}
          unit="€/MWh"
          context={
            full ? 'Tidsviktat för valt urval' : 'Ofullständigt kalenderår'
          }
        />
        <Stat
          label="Negativa priser"
          value={ready ? fmt(neg) : '…'}
          unit="h"
          context="Antal kvartar × 0,25 timmar"
        />
        <Stat
          label="Tillgänglig period"
          value={ready ? fmt(hours, 0) : '…'}
          unit="h"
          context={
            grain === 'month'
              ? year
              : year + '-' + month + (grain === 'interval' ? '-' + day : '')
          }
        />
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>
            {shape === 'duration'
              ? 'Prisernas varaktighet'
              : shape === 'hour'
                ? 'Genomsnittlig dygnsprofil'
                : 'Spotpriser över tid'}{' '}
            · {zone}
          </h2>
          {grain !== 'month' && (
            <Tabs value={shape} onValueChange={(v) => setShape(String(v))}>
              <TabsList>
                <TabsTrigger value="time">Tidsserie</TabsTrigger>
                <TabsTrigger value="duration">Varaktighet</TabsTrigger>
                <TabsTrigger value="hour">Dygnsprofil</TabsTrigger>
              </TabsList>
            </Tabs>
          )}
        </div>
        {ready && rs.length === 0 ? (
          <div className="empty">Spotdata saknas för det valda urvalet.</div>
        ) : ready ? (
          <Plot
            rows={rs}
            unit="€/MWh"
            series={[
              { key: 'price', name: year, color: 'var(--chart-1)' },
              ...(grain === 'month' && compare !== 'none'
                ? [
                    {
                      key: 'comparison',
                      name: compare,
                      color: 'var(--chart-2)',
                    },
                  ]
                : []),
            ]}
          />
        ) : (
          <ErrorState error={error} />
        )}
        <div className="chart-bottom">
          <span>
            {shape === 'duration'
              ? 'X: antal timmar sorterade från högst till lägst pris'
              : shape === 'hour'
                ? 'X: lokal timme, Europe/Stockholm'
                : grain === 'month'
                  ? 'X: månad'
                  : grain === 'day'
                    ? 'X: dag i vald månad'
                    : 'X: svensk lokaltid'}
          </span>
          <Button
            variant="outline"
            disabled={!ready || !rs.length}
            onClick={() =>
              downloadCsv(
                'spot-' + zone + '-' + year + '.csv',
                grain === 'month'
                  ? [
                      'Månad',
                      'År ' + year + ' EUR/MWh',
                      'År ' + compare + ' EUR/MWh',
                      'Timmar',
                      'Negativa timmar',
                    ]
                  : [
                      'Tid',
                      'EUR/MWh',
                      'SEK/MWh',
                      'Ursprunglig upplösning minuter',
                    ],
                grain === 'month'
                  ? rs.map((r) => [
                      r.label,
                      r.price,
                      r.comparison,
                      'hours' in r ? r.hours : null,
                      'negative_hours' in r ? r.negative_hours : null,
                    ])
                  : chosenRaw,
              )
            }
          >
            <Download />
            Exportera urval
          </Button>
        </div>
      </section>
      <Notice>
        Day-ahead-priser via elprisetjustnu.se. Ursprungliga timpriser återges i
        fyra kvartar med samma pris; det tillför ingen ny prisupplösning.
        Varaktighetsgrafen visar ett urval av punkter, CSV innehåller samtliga
        kvartar.
      </Notice>
      <details className="data-table">
        <summary>Visa diagramvärden</summary>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tid</TableHead>
              <TableHead>EUR/MWh · {year}</TableHead>
              {grain === 'month' && compare !== 'none' && (
                <TableHead>{compare}</TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rs.map((r, i) => (
              <TableRow key={i}>
                <TableCell>{r.label}</TableCell>
                <TableCell>{fmt(r.price, 2)}</TableCell>
                {grain === 'month' && compare !== 'none' && (
                  <TableCell>{fmt(r.comparison, 2)}</TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </details>
    </>
  );
}
function useFutures(data: Summary) {
  const [value, setValue] = useState<Record<string, Quote[]> | null>(null),
    [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all(
      data.futures.map(async (c) => {
        const url = data.data_path + '/futures/' + c.symbol + '.json';
        if (cache.has(url)) return [c.symbol, cache.get(url)] as const;
        const r = await fetch(url);
        if (!r.ok) throw new Error('Terminsutdrag kunde inte läsas');
        const rows = await r.json();
        cache.set(url, rows);
        return [c.symbol, rows] as const;
      }),
    )
      .then((r) => {
        if (active) setValue(Object.fromEntries(r) as Record<string, Quote[]>);
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [data]);
  return { value, error };
}
export function FuturesView({ data }: { data: Summary }) {
  const latest =
    data.futures
      .map((c) => c.last)
      .sort()
      .at(-1) || '';
  const [mode, setMode] = useQuery(
      'futures_mode',
      'history',
      oneOf(['history', 'curve']),
    ),
    [contract, setContract] = useQuery(
      'contract',
      'YR-27',
      oneOf(['YR-23', 'YR-24', ...data.futures.map((c) => c.label)]),
    ),
    [zone, setZone] = useQuery(
      'futures_zone',
      'SYS',
      oneOf(['SYS', 'SE1', 'SE2', 'SE3', 'SE4']),
    ),
    [from, setFrom] = useQuery('from', '2024-01-01', dateValue),
    [to, setTo] = useQuery('to', latest, dateValue),
    [dateA, setDateA] = useQuery('date_a', latest, dateValue),
    [dateB, setDateB] = useQuery('date_b', '2024-12-30', dateValue);
  const { value: all, error } = useFutures(data);
  const labels = [
    ...new Set(['YR-23', 'YR-24', ...data.futures.map((c) => c.label)]),
  ].sort(
    (a, b) => a.slice(-2).localeCompare(b.slice(-2)) || a.localeCompare(b),
  );
  if (!all) return <ErrorState error={error} />;
  const seriesFor = (label: string, market: string): Quote[] => {
    const sys = data.futures.find(
      (c) => c.label === label && c.market === 'SYS',
    );
    const s = sys ? all[sys.symbol] || [] : [];
    if (market === 'SYS') return s;
    const epad = data.futures.find(
      (c) => c.label === label && c.market === market,
    );
    return impliedHistory(s, epad ? all[epad.symbol] || [] : []) as Quote[];
  };
  const series = seriesFor(contract, zone),
    sysSeries = seriesFor(contract, 'SYS');
  const filtered = series.filter((r) => r[0] >= from && r[0] <= to);
  const last = filtered.at(-1);
  const first = filtered[0];
  const activeLabels = labels.filter((l) =>
    data.futures.some(
      (c) => c.label === l && c.market === 'SYS' && c.label.startsWith('YR'),
    ),
  );
  const curves = activeLabels.map((label) => {
    const a = asOf(seriesFor(label, zone), dateA),
      b = asOf(seriesFor(label, zone), dateB);
    return {
      label,
      a: a?.[1] ?? null,
      b: b?.[1] ?? null,
      dateA: a?.[0] ?? null,
      dateB: b?.[0] ?? null,
    };
  });
  const gapRows = withGaps(filtered).map(
    (r: [string, number | null, number | null]) => ({
      label: r[0],
      price: r[1],
      sys:
        zone === 'SYS'
          ? null
          : (sysSeries.find((s) => s[0] === r[0])?.[1] ?? null),
    }),
  );
  const period = data.futures.find((c) => c.label === contract);
  return (
    <>
      <div className="view-tabs">
        <Tabs value={mode} onValueChange={(v) => setMode(String(v))}>
          <TabsList className="h-11">
            <TabsTrigger value="history" className="px-4">
              Kontrakt över tid
            </TabsTrigger>
            <TabsTrigger value="curve" className="px-4">
              Kurvan vid ett datum
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <div className="filters">
        <Picker
          label="Prisreferens"
          value={zone}
          onChange={setZone}
          options={[
            { value: 'SYS', label: 'Nordiskt systempris' },
            ...['SE1', 'SE2', 'SE3', 'SE4'].map((z) => ({
              value: z,
              label: z + ' · SYS + EPAD',
            })),
          ]}
        />
        {mode === 'history' ? (
          <>
            <Picker
              label="Leveranskontrakt"
              value={contract}
              onChange={setContract}
              options={opts(labels)}
            />
            <label className="picker" htmlFor="future-from">
              <span>Handelsdatum från</span>
              <Input
                id="future-from"
                type="date"
                aria-label="Handelsdatum från"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className="h-10"
              />
            </label>
            <label className="picker" htmlFor="future-to">
              <span>Handelsdatum till</span>
              <Input
                id="future-to"
                type="date"
                aria-label="Handelsdatum till"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className="h-10"
              />
            </label>
          </>
        ) : (
          <>
            <label className="picker" htmlFor="future-dateA">
              <span>Marknadsläge A</span>
              <Input
                id="future-dateA"
                type="date"
                aria-label="Marknadsläge A"
                value={dateA}
                onChange={(e) => setDateA(e.target.value)}
                className="h-10"
              />
            </label>
            <label className="picker" htmlFor="future-dateB">
              <span>Jämför med B</span>
              <Input
                id="future-dateB"
                type="date"
                aria-label="Jämför med B"
                value={dateB}
                onChange={(e) => setDateB(e.target.value)}
                className="h-10"
              />
            </label>
          </>
        )}
      </div>
      {mode === 'history' ? (
        <>
          <div className="stats">
            <Stat
              label="Senaste i urvalet"
              value={fmt(last?.[1], 2)}
              unit="€/MWh"
              context={last?.[0] || 'Ingen observation i urvalet'}
            />
            <Stat
              label="Förändring i urvalet"
              value={fmt(last && first ? last[1] - first[1] : null, 2)}
              unit="€/MWh"
              context={first?.[0] || 'Historik saknas'}
            />
            <Stat
              label="Handlad volym"
              value="—"
              context="Finns inte i nuvarande dataimport"
            />
          </div>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>
                  {zone} baseload · {contract}
                </h2>
                <p className="panel-sub">
                  {period
                    ? 'Leverans ' + period.start + ' till ' + period.end
                    : 'Leveransår 20' + contract.slice(-2)}
                </p>
              </div>
              <div className="legend">
                <span>
                  <i />
                  {zone === 'SYS' ? 'SYS settlement' : zone + ' områdespris'}
                </span>
                {zone !== 'SYS' && (
                  <span>
                    <i className="budget" />
                    SYS settlement
                  </span>
                )}
              </div>
            </div>
            {filtered.length ? (
              <Plot
                rows={gapRows}
                unit="€/MWh"
                series={[
                  { key: 'price', name: zone, color: 'var(--chart-1)' },
                  ...(zone !== 'SYS'
                    ? [{ key: 'sys', name: 'SYS', color: 'var(--chart-2)' }]
                    : []),
                ]}
              />
            ) : (
              <div className="empty">
                <FileCheck2 />
                <h3>
                  {series.length
                    ? 'Inga noteringar inom handelsdatumen'
                    : 'Leveranskontraktet saknas i det lokala arkivet'}
                </h3>
                <p>
                  {['YR-23', 'YR-24'].includes(contract)
                    ? 'För 2023 och 2024 behöver kontraktens historiska settlement och volym importeras. Spotpriser för kalenderåren finns under Elmarknad.'
                    : 'Välj en annan period eller prisreferens.'}
                </p>
              </div>
            )}
            <div className="chart-bottom">
              <span>
                Värdedatum på x-axeln · luckor över sju dagar bryter linjen
              </span>
              <Button
                variant="outline"
                disabled={!filtered.length}
                onClick={() =>
                  downloadCsv(
                    'futures-' + zone + '-' + contract + '.csv',
                    [
                      'Värdedag',
                      'Settlement EUR/MWh',
                      'OI original, enhet ej verifierad',
                    ],
                    filtered,
                  )
                }
              >
                <Download />
                CSV
              </Button>
            </div>
          </section>
          {period && (
            <div className="lookback">
              <h2>Priset före leverans</h2>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tid till leverans</TableHead>
                    <TableHead>Vald referensdag</TableHead>
                    <TableHead>Faktisk värdedag</TableHead>
                    <TableHead>EUR/MWh</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[24, 12, 6, 3, 1].map((n) => {
                    const target = new Date(period.start + 'T12:00:00Z');
                    target.setUTCMonth(target.getUTCMonth() - n);
                    const day = target.toISOString().slice(0, 10);
                    const r = asOf(series, day);
                    return (
                      <TableRow key={n}>
                        <TableCell>{n} månader</TableCell>
                        <TableCell>{day}</TableCell>
                        <TableCell>{r?.[0] || 'Saknas'}</TableCell>
                        <TableCell>{fmt(r?.[1], 2)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      ) : (
        <section className="panel">
          <div className="panel-heading">
            <h2>Årskurvan · {zone}</h2>
            <div className="legend">
              <span>
                <i />
                {dateA}
              </span>
              <span>
                <i className="budget" />
                {dateB}
              </span>
            </div>
          </div>
          <Plot
            rows={curves}
            unit="€/MWh"
            series={[
              { key: 'a', name: dateA, color: 'var(--chart-1)' },
              { key: 'b', name: dateB, color: 'var(--chart-2)' },
            ]}
          />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Leverans</TableHead>
                <TableHead>A €/MWh</TableHead>
                <TableHead>Värdedag A</TableHead>
                <TableHead>B €/MWh</TableHead>
                <TableHead>Värdedag B</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {curves.map((r) => (
                <TableRow key={r.label}>
                  <TableCell>{r.label}</TableCell>
                  <TableCell>{fmt(r.a, 2)}</TableCell>
                  <TableCell>{r.dateA || 'Saknas'}</TableCell>
                  <TableCell>{fmt(r.b, 2)}</TableCell>
                  <TableCell>{r.dateB || 'Saknas'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Button
            variant="outline"
            onClick={() =>
              downloadCsv(
                'terminskurva.csv',
                [
                  'Leverans',
                  'A EUR/MWh',
                  'Värdedag A',
                  'B EUR/MWh',
                  'Värdedag B',
                ],
                curves.map((r) => [r.label, r.a, r.dateA, r.b, r.dateB]),
              )
            }
          >
            <Download />
            Exportera jämförelse
          </Button>
        </section>
      )}
      <Notice>
        Historiska datum använder endast noteringar på eller före vald dag,
        högst sju kalenderdagar gamla. Områdespris kräver SYS och EPAD samma
        värdedag. Nasdaq-/Euronext-filerna saknar källmetadata per rad; open
        interest visas inte som en jämförbar volymserie innan enheterna
        verifierats.
      </Notice>
    </>
  );
}
export function RevenueView({
  data,
  month,
  zone,
}: {
  data: Summary;
  month: string;
  zone: string;
}) {
  const ps = selectedParks(data, zone, month),
    active = ps.filter((p) => p.ppa),
    known = ps.every((p) => goodMonth(p.m!));
  if (!ps.length)
    return (
      <div className="empty">
        Inga parkobservationer finns för det valda elområdet och månaden.
      </div>
    );
  const spot = ps.reduce((s, p) => s + (p.m!.spot_value_eur || 0), 0),
    hasModels = active.every((p) => p.m!.ppa_model_eur !== null);
  const model = hasModels
    ? ps.reduce(
        (s, p) =>
          s + (p.ppa ? p.m!.ppa_model_eur || 0 : p.m!.spot_value_eur || 0),
        0,
      )
    : null;
  const total = ps.reduce((s, p) => s + (p.m!.export_mwh || 0), 0),
    hedged = ps.reduce(
      (s, p) => s + ((p.m!.export_mwh || 0) * (p.ppa?.share_pct || 0)) / 100,
      0,
    );
  return (
    <>
      <Notice>
        PPA-scenariot tillämpar dagens fasta pris och andel på vald månads kända
        produktion. Avtalens giltighetsdatum, negativa-prisvillkor, avgifter och
        faktisk avräkning ingår ännu inte.
      </Notice>
      <div className="stats">
        <Stat
          label="Spotvärde"
          value={fmt(spot / 1000)}
          unit="k€"
          context={
            known
              ? 'Känd export × spotpris'
              : 'Partiellt underlag · inte hela periodens intäkt'
          }
        />
        <Stat
          label="Med PPA-antaganden"
          value={fmt(model == null ? null : model / 1000)}
          unit="k€"
          context="Modellvärde · inte avräknad intäkt"
        />
        <Stat
          label="Skillnad mot spot"
          value={fmt(model == null ? null : (model - spot) / 1000)}
          unit="k€"
          context={
            fmt(total ? (hedged / total) * 100 : null) +
            ' % modellerad PPA-andel av export'
          }
        />
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Spotvärde och PPA-scenario</h2>
          <div className="legend">
            <span>
              <i />
              Spot
            </span>
            <span>
              <i className="budget" />
              Med PPA
            </span>
          </div>
        </div>
        <Plot
          rows={ps.map((p) => ({
            label: p.name,
            spot:
              p.m!.spot_value_eur == null ? null : p.m!.spot_value_eur / 1000,
            ppa:
              (p.ppa ? p.m!.ppa_model_eur : p.m!.spot_value_eur) == null
                ? null
                : (p.ppa ? p.m!.ppa_model_eur! : p.m!.spot_value_eur!) / 1000,
          }))}
          unit="k€"
          series={[
            {
              key: 'spot',
              name: 'Spotvärde',
              color: 'var(--chart-1)',
              bar: true,
            },
            {
              key: 'ppa',
              name: 'PPA-scenario',
              color: 'var(--chart-2)',
              bar: true,
            },
          ]}
        />
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Park</TableHead>
              <TableHead>SEK/MWh</TableHead>
              <TableHead>Andel</TableHead>
              <TableHead>Spotvärde €</TableHead>
              <TableHead>PPA-scenario €</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ps.map((p) => (
              <TableRow key={p.key}>
                <TableCell>{p.name}</TableCell>
                <TableCell>{fmt(p.ppa?.price_sek_mwh, 0)}</TableCell>
                <TableCell>
                  {p.ppa ? fmt(p.ppa.share_pct, 0) + ' %' : 'Spot'}
                </TableCell>
                <TableCell>{fmt(p.m!.spot_value_eur, 0)}</TableCell>
                <TableCell>
                  {fmt(p.ppa ? p.m!.ppa_model_eur : p.m!.spot_value_eur, 0)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Button
          variant="outline"
          onClick={() =>
            downloadCsv(
              'ppa-scenario-' + month + '.csv',
              [
                'Park',
                'Månad',
                'Antaget PPA SEK/MWh',
                'Antagen andel %',
                'Spotvärde EUR',
                'PPA-scenario EUR',
                'Energitäckning %',
                'Dataversion',
              ],
              ps.map((p) => [
                p.name,
                month,
                p.ppa?.price_sek_mwh,
                p.ppa?.share_pct,
                p.m!.spot_value_eur,
                p.ppa ? p.m!.ppa_model_eur : p.m!.spot_value_eur,
                p.m!.coverage,
                data.dataset_version,
              ]),
            )
          }
        >
          <Download />
          Exportera scenario
        </Button>
      </section>
      <Notice>
        Capture och spotvärde avser exporterad energi. Små negativa mätvärden
        ingår i nettoenergin men inte i exportvolymen. PPA i SEK konverteras med
        intervallets FX från spotkällan. Saknad FX ger inget PPA-modellvärde.
      </Notice>
    </>
  );
}
export function QualityView({ data }: { data: Summary }) {
  const groups = [
    { name: 'Day-ahead · råa spotpriser', match: 'spotpriser/' },
    { name: 'Parkproduktion · Bazefield', match: 'profiler/parker/' },
    { name: 'Terminer · Nasdaq/Euronext', match: 'nasdaq/futures/' },
  ];
  return (
    <>
      <div className="stats">
        {groups.map((g) => {
          const fs = data.sources.filter((f) => f.path.includes(g.match));
          const last = fs
            .map((f) => f.last || '')
            .sort()
            .at(-1);
          return (
            <Stat
              key={g.name}
              label={g.name}
              value={last?.slice(0, 10) || '—'}
              context={fs.length + ' källfiler · senaste observation'}
            />
          );
        })}
      </div>
      <Notice>
        Byggdatum är inte datadatum. Datasetet är ett lokalt, reproducerbart
        utdrag. Inga liveuppdateringar sker i webbläsaren. Nya utdrag genereras
        med projektets Python-export.
      </Notice>
      <section className="panel">
        <div className="panel-heading">
          <h2>Definitioner och begränsningar</h2>
          <span>{data.metric_version}</span>
        </div>
        <ul className="definition-list">
          {data.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          <li>
            Budget jämförs med hela samma månad. Vid ofullständig energi hålls
            procentavvikelsen tillbaka.
          </li>
          <li>
            Portföljcapture viktas med prismatchad exportenergi. Täckning avser
            känd energi och intygar inte att saknade intervall saknat
            produktion.
          </li>
          <li>
            Baseload är tidsviktat områdessnitt. Nordiskt systemspotpris finns
            ännu inte i underlaget.
          </li>
          <li>
            Kalenderår 2023/2024 finns för spot. Leveranskontrakt 2023/2024 och
            handlad terminsvolym behöver kompletteras.
          </li>
        </ul>
      </section>
      <details className="data-table">
        <summary>
          Källfiler och kontrollsummor · {data.sources.length} filer
        </summary>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Källa</TableHead>
              <TableHead>Rader</TableHead>
              <TableHead>Senaste observation</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.sources.map((f) => (
              <TableRow key={f.path}>
                <TableCell className="break-all">
                  {f.path}
                  <small className="hash">SHA-256 {f.sha256}</small>
                </TableCell>
                <TableCell>{fmt(f.rows, 0)}</TableCell>
                <TableCell>
                  {f.last?.slice(0, 10) || 'Beräkningsdefinition'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </details>
      <Button
        variant="outline"
        onClick={() =>
          downloadCsv(
            'datamanifest.csv',
            ['Källa', 'Rader', 'Första', 'Senaste', 'SHA256', 'Dataversion'],
            data.sources.map((f) => [
              f.path,
              f.rows,
              f.first,
              f.last,
              f.sha256,
              data.dataset_version,
            ]),
          )
        }
      >
        <Download />
        Exportera datamanifest
      </Button>
    </>
  );
}
