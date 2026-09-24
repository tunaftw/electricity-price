export type Month = {
  matched_baseload_eur: number | null;
  capture_rate: number | null;
  month: string;
  energy_mwh: number | null;
  export_mwh: number | null;
  estimated_mwh: number;
  priced_mwh: number;
  spot_value_eur: number | null;
  capture: number | null;
  budget_mwh: number;
  budget_pr: number;
  coverage: number;
  poa_coverage: number;
  availability_coverage: number;
  complete: boolean;
  pr: number | null;
  pr_quality: string;
  poa_kwh_m2: number;
  pr_paired_energy_mwh: number;
  availability: number | null;
  price_coverage: number | null;
  negative_mwh: number;
  negative_value_eur: number;
  ppa_model_eur: number | null;
  valid_intervals: number;
  expected_intervals: number;
};
export type Park = {
  name: string;
  zone: string;
  capacity_kwp: number;
  ppa: { share_pct: number; price_sek_mwh: number } | null;
  months: Month[];
  latest: string | null;
};
export type MarketMonth = {
  month: string;
  baseload: number;
  negative_hours: number;
  coverage: number;
  hours: number;
  min: number;
  max: number;
};
export type Instrument = {
  symbol: string;
  market: string;
  label: string;
  start: string;
  end: string;
  year: number;
  first: string;
  last: string;
  points: number;
  source_file: string;
};
export type Summary = {
  data_path: string;
  generated: string;
  dataset_version: string;
  metric_version: string;
  sources: {
    path: string;
    rows: number;
    first: string | null;
    last: string | null;
    sha256: string;
  }[];
  parks: Record<string, Park>;
  market: Record<string, MarketMonth[]>;
  futures: Instrument[];
  notes: string[];
};
export type Quote = [string, number, number | null];
export type SpotRow = [string, number, number | null, number];
export type ParkDetail = {
  daily: ({ date: string } & Month)[];
  intervals: [
    string,
    number | null,
    number | null,
    number | null,
    number | null,
    number | null,
    string,
  ][];
};
