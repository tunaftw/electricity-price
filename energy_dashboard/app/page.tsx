import Dashboard from './Dashboard';
import summary from '../public/data/summary.json';
import type { Summary } from './types';
export default function Page() {
  return <Dashboard data={summary as unknown as Summary} />;
}
