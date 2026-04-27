/** Filter bar for session list. */

import type { FilterGroup } from '../types';
import './FilterBar.css';

interface Props {
  current: FilterGroup;
  onChange: (group: FilterGroup) => void;
  counts: Record<FilterGroup, number>;
}

const FILTER_ORDER: FilterGroup[] = ['ALL', 'NEED_ATTENTION', 'RUNNING', 'DONE', 'DEAD'];

export function FilterBar({ current, onChange, counts }: Props) {
  return (
    <div data-testid="filter-bar" className="filter-bar">
      {FILTER_ORDER.map(group => (
        <button
          key={group}
          className={`filter-btn ${group === current ? 'active' : ''}`}
          onClick={() => onChange(group)}
        >
          {group.replace('_', ' ')}
          <span className="filter-count">{counts[group]}</span>
        </button>
      ))}
    </div>
  );
}
