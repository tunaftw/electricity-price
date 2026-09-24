'use client';
import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import {
  Sun,
  LayoutDashboard,
  ChartNoAxesCombined,
  TrendingUp,
  Wallet,
  Database,
  Link as LinkIcon,
  Check,
} from 'lucide-react';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarInset,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import {
  ParksView,
  MarketView,
  FuturesView,
  RevenueView,
  QualityView,
  selectedParks,
} from './Views';
import { useQuery, oneOf } from './use-query';
import { fmt, monthName, Picker } from './components';
import type { Summary } from './types';
const views = [
  {
    key: 'portfolio',
    label: 'Portföljen',
    eyebrow: 'PRODUKTION & MARKNADSVÄRDE',
    icon: LayoutDashboard,
    description: 'Följ produktionen. Förstå avvikelserna.',
  },
  {
    key: 'market',
    label: 'Elmarknaden',
    eyebrow: 'DAY-AHEAD · SVERIGE',
    icon: ChartNoAxesCombined,
    description: 'Utforska prisnivåer, dygnsmönster och negativa priser.',
  },
  {
    key: 'futures',
    label: 'Terminer',
    eyebrow: 'NORDISKT SYSTEMPRIS & EPAD',
    icon: TrendingUp,
    description: 'Se vad marknaden prissatte – och när.',
  },
  {
    key: 'revenue',
    label: 'Intäkt & PPA',
    eyebrow: 'EXPORTENS VÄRDE',
    icon: Wallet,
    description: 'Jämför spotvärde med ett transparent PPA-scenario.',
  },
  {
    key: 'quality',
    label: 'Underlaget',
    eyebrow: 'KÄLLOR & BERÄKNINGAR',
    icon: Database,
    description: 'Spåra varje utdrag till dess källor och definitioner.',
  },
];
export default function Dashboard({ data }: { data: Summary }) {
  const months = useMemo(
    () =>
      [
        ...new Set(
          Object.values(data.parks).flatMap((p) =>
            p.months.map((m) => m.month),
          ),
        ),
      ]
        .sort()
        .reverse(),
    [data.parks],
  );
  const defaultMonth =
    months.find(
      (mo) =>
        Object.values(data.parks).filter((p) =>
          p.months.some(
            (m) =>
              m.month === mo && m.pr_quality !== 'insufficient' && m.complete,
          ),
        ).length >= 4,
    ) || months[0];
  const [view, setView] = useQuery(
      'view',
      'portfolio',
      oneOf(views.map((v) => v.key)),
    ),
    [month, setMonth] = useQuery('month', defaultMonth, oneOf(months)),
    [zone, setZone] = useQuery('zone', 'all', oneOf(['all', 'SE3', 'SE4'])),
    [copied, setCopied] = useState(false);
  const active = views.find((v) => v.key === view)!;
  const selected = selectedParks(data, zone, month);
  const select = setView;
  const setFilter = useCallback(
    (key: string, value: string) => {
      if (key === 'month') setMonth(value);
      else setZone(value);
    },
    [setMonth, setZone],
  );
  async function copy() {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('view', view);
      url.searchParams.set('month', month);
      url.searchParams.set('zone', zone);
      await navigator.clipboard.writeText(url.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  const live = useRef({ view, month, zone, select, setFilter });
  useEffect(() => {
    live.current = { view, month, zone, select, setFilter };
  }, [view, month, zone, select, setFilter]);
  useEffect(() => {
    // The browser contract mirrors visible navigation and validated portfolio filters.
    type ModelContext = {
      registerTool: (
        tool: unknown,
        options: { signal: AbortSignal },
      ) => void | Promise<void>;
    };
    const mc = (document as Document & { modelContext?: ModelContext })
      .modelContext;
    if (!mc?.registerTool) return;
    const lifecycle = new AbortController();
    const register = (tool: unknown) => {
      try {
        void Promise.resolve(
          mc.registerTool(tool, { signal: lifecycle.signal }),
        ).catch(() => {});
      } catch {
        /* Optional browser capability; visible controls remain available. */
      }
    };
    const get = () => ({
      view: live.current.view,
      month: live.current.month,
      zone: live.current.zone,
      dataset_version: data.dataset_version,
      available_views: views.map((v) => v.key),
      available_months: months,
    });
    register({
      name: 'get_analysis_context',
      description:
        'Read the visible Elpris workspace, portfolio filters and dataset version.',
      annotations: { readOnlyHint: true, untrustedContentHint: false },
      inputSchema: {
        type: 'object',
        properties: {},
        additionalProperties: false,
      },
      execute: async () => ({
        content: [{ type: 'text', text: JSON.stringify(get()) }],
      }),
    });
    register({
      name: 'configure_analysis',
      description:
        'Select an existing Elpris workspace and optional portfolio month and zone, matching visible controls. No source data changes.',
      annotations: { readOnlyHint: false, untrustedContentHint: false },
      inputSchema: {
        type: 'object',
        properties: {
          view: { type: 'string', enum: views.map((v) => v.key) },
          month: { type: 'string', enum: months },
          zone: { type: 'string', enum: ['all', 'SE3', 'SE4'] },
        },
        additionalProperties: false,
      },
      execute: async (args: {
        view?: string;
        month?: string;
        zone?: string;
      }) => {
        if (
          !args ||
          typeof args !== 'object' ||
          Array.isArray(args) ||
          Object.keys(args).some(
            (k) => !['view', 'month', 'zone'].includes(k),
          ) ||
          Object.values(args).some((v) => typeof v !== 'string')
        )
          throw new Error('Invalid analysis selection');
        if (
          (args.view && !views.some((v) => v.key === args.view)) ||
          (args.month && !months.includes(args.month)) ||
          (args.zone && !['all', 'SE3', 'SE4'].includes(args.zone))
        )
          throw new Error('Invalid analysis selection');
        if (args.view) live.current.select(args.view);
        if (args.month) live.current.setFilter('month', args.month);
        if (args.zone) live.current.setFilter('zone', args.zone);
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
        );
        return { content: [{ type: 'text', text: JSON.stringify(get()) }] };
      },
    });
    return () => lifecycle.abort();
  }, [data.dataset_version, months]);
  return (
    <SidebarProvider
      style={{ '--sidebar-width': '14rem' } as React.CSSProperties}
    >
      <Sidebar>
        <SidebarHeader className="brand">
          <Sun />
          <span>
            elpris<span>ANALYSRUM</span>
          </span>
        </SidebarHeader>
        <SidebarContent className="p-3">
          <p className="nav-label">ARBETSYTOR</p>
          <SidebarMenu>
            {views.map((v) => (
              <SidebarMenuItem key={v.key}>
                <SidebarMenuButton
                  isActive={view === v.key}
                  onClick={() => select(v.key)}
                  className="h-11 px-3"
                >
                  <v.icon />
                  {v.label}
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
          <div className="coming-next">
            <span>NÄSTA STEG</span>
            <p>Batterier & flexibilitet</p>
            <small>Utbyggbar analysmodell</small>
          </div>
        </SidebarContent>
        <SidebarFooter className="sidebar-foot">
          <span>Svea Solar</span>
          <small>Intern analys · Första version</small>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="topbar">
          <div>
            <SidebarTrigger />
            <span>
              Analysrum / <b>{active.label}</b>
            </span>
          </div>
          <span className="build-label">
            Lokalt datautdrag · {data.generated.slice(0, 10)}
          </span>
        </header>
        <main className="workspace">
          <div className="page-heading">
            <div>
              <p className="eyebrow">{active.eyebrow}</p>
              <h1>{active.label}</h1>
              <p className="page-description">{active.description}</p>
            </div>
            <Button
              variant="outline"
              onClick={copy}
              title="Kopiera en lokal länk med analysens urval"
            >
              {copied ? <Check /> : <LinkIcon />}
              {copied ? 'Kopierad' : 'Kopiera vy'}
            </Button>
          </div>
          {['portfolio', 'revenue'].includes(view) && (
            <div className="filters">
              <Picker
                label="Analysperiod"
                value={month}
                onChange={(v) => setFilter('month', v)}
                options={months.map((m) => ({ value: m, label: monthName(m) }))}
              />
              <Picker
                label="Elområde"
                value={zone}
                onChange={(v) => setFilter('zone', v)}
                options={[
                  { value: 'all', label: 'Alla parker' },
                  { value: 'SE3', label: 'SE3' },
                  { value: 'SE4', label: 'SE4' },
                ]}
              />
              <span className="context">
                {selected.length} parker ·{' '}
                {fmt(selected.reduce((s, p) => s + p.capacity_kwp, 0) / 1000)}{' '}
                MWp
              </span>
            </div>
          )}
          {view === 'portfolio' && (
            <ParksView data={data} month={month} zone={zone} />
          )}
          {view === 'market' && <MarketView data={data} />}
          {view === 'futures' && <FuturesView data={data} />}
          {view === 'revenue' && (
            <RevenueView data={data} month={month} zone={zone} />
          )}
          {view === 'quality' && <QualityView data={data} />}
          <footer className="page-footer">
            {data.metric_version} · Data {data.dataset_version} ·
            Europe/Stockholm
          </footer>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
