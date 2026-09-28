import { useEffect, useMemo, useState } from 'react';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
} from 'chart.js';
import { Bar, Pie } from 'react-chartjs-2';
import { api, money, todayMonth } from '../api.js';
import { useAuth } from '../auth.jsx';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Legend, Title, Tooltip);

const PIE_COLORS = [
  '#4f46e5', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#64748b',
  '#a3e635', '#6366f1',
];

function StatCard({ label, value, tone }) {
  return (
    <div className={`card stat ${tone || ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { token } = useAuth();
  const [month, setMonth] = useState(todayMonth());
  const [summary, setSummary] = useState(null);
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState('');
  const [newBudgetCat, setNewBudgetCat] = useState('');
  const [newBudgetAmt, setNewBudgetAmt] = useState('');

  const refresh = () => {
    api(`/api/summary?month=${month}`, { token }).then(setSummary).catch((e) => setError(e.message));
    api('/api/categories', { token }).then(setCategories).catch(() => {});
  };

  useEffect(() => {
    setError('');
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, token]);

  const addBudget = async (e) => {
    e.preventDefault();
    if (!newBudgetCat || !newBudgetAmt) return;
    try {
      await api('/api/budgets', {
        method: 'POST',
        token,
        body: { category_id: Number(newBudgetCat), month, amount: Number(newBudgetAmt) },
      });
      setNewBudgetCat('');
      setNewBudgetAmt('');
      refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteBudget = async (categoryId) => {
    const existing = await api(`/api/budgets?month=${month}`, { token });
    const match = existing.find((b) => b.category_id === categoryId);
    if (!match) return;
    if (!window.confirm('Delete this budget?')) return;
    await api(`/api/budgets/${match.id}`, { method: 'DELETE', token });
    refresh();
  };

  const pieData = useMemo(() => {
    const items = summary?.spending_by_category ?? [];
    return {
      labels: items.map((c) => c.category_name),
      datasets: [
        {
          data: items.map((c) => c.total),
          backgroundColor: items.map((_, i) => PIE_COLORS[i % PIE_COLORS.length]),
          borderWidth: 2,
          borderColor: '#ffffff',
        },
      ],
    };
  }, [summary]);

  const barData = useMemo(() => {
    const months = summary?.monthly_totals ?? [];
    return {
      labels: months.map((m) => m.month),
      datasets: [
        { label: 'Income', data: months.map((m) => m.income), backgroundColor: '#10b981' },
        { label: 'Expenses', data: months.map((m) => m.expenses), backgroundColor: '#ef4444' },
      ],
    };
  }, [summary]);

  if (error) return <div className="page"><div className="error">{error}</div></div>;
  if (!summary) return <div className="page">Loading dashboard…</div>;

  const netWorth = summary.net_by_account.reduce((s, a) => s + a.balance, 0);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <input
          type="month"
          className="input"
          value={month}
          max={todayMonth()}
          onChange={(e) => setMonth(e.target.value)}
          aria-label="Month"
        />
      </div>

      <div className="stats-grid">
        <StatCard label={`Income · ${summary.month}`} value={money(summary.total_income)} tone="good" />
        <StatCard label={`Expenses · ${summary.month}`} value={money(summary.total_expenses)} tone="bad" />
        <StatCard label={`Net savings · ${summary.month}`} value={money(summary.net_savings)} />
        <StatCard label="Net worth (all accounts)" value={money(netWorth)} />
      </div>

      <div className="grid-2">
        <div className="card">
          <h2>Spending by category · {summary.month}</h2>
          {summary.spending_by_category.length === 0 ? (
            <p className="muted">No expenses recorded this month yet.</p>
          ) : (
            <div className="chart-wrap">
              <Pie
                data={pieData}
                options={{
                  plugins: {
                    legend: { position: 'right' },
                    tooltip: { callbacks: { label: (c) => ` ${c.label}: ${money(c.parsed)}` } },
                  },
                  maintainAspectRatio: false,
                }}
              />
            </div>
          )}
        </div>
        <div className="card">
          <h2>Income vs expenses</h2>
          <div className="chart-wrap">
            <Bar
              data={barData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'top' },
                  tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${money(c.parsed.y)}` } },
                },
                scales: { y: { ticks: { callback: (v) => '$' + Number(v).toLocaleString() } } },
              }}
            />
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h2>Budgets · {summary.month}</h2>
          {summary.budget_progress.length === 0 ? (
            <p className="muted">No budgets set for this month yet.</p>
          ) : (
            summary.budget_progress.map((b) => {
              const pct = b.budgeted > 0 ? Math.min(100, (b.spent / b.budgeted) * 100) : 0;
              const over = b.spent > b.budgeted;
              return (
                <div key={b.category_id} className="budget-row">
                  <div className="budget-top">
                    <strong>{b.category_name}</strong>
                    <span>
                      <span className={over ? 'over' : ''}>
                        {money(b.spent)} of {money(b.budgeted)}
                      </span>{' '}
                      <button
                        className="btn btn-ghost btn-xs"
                        onClick={() => deleteBudget(b.category_id)}
                        title="Delete budget"
                      >
                        ✕
                      </button>
                    </span>
                  </div>
                  <div className="progress">
                    <div className={`progress-fill ${over ? 'over' : ''}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })
          )}
          <form className="inline-form" onSubmit={addBudget}>
            <select
              className="input"
              value={newBudgetCat}
              onChange={(e) => setNewBudgetCat(e.target.value)}
              required
            >
              <option value="">Category…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <input
              className="input"
              type="number"
              min="0.01"
              step="0.01"
              placeholder="Amount"
              value={newBudgetAmt}
              onChange={(e) => setNewBudgetAmt(e.target.value)}
              required
            />
            <button className="btn btn-secondary" type="submit">Add budget</button>
          </form>
        </div>
        <div className="card">
          <h2>Net worth by account</h2>
          {summary.net_by_account.length === 0 ? (
            <p className="muted">No accounts yet — add one on the Accounts page.</p>
          ) : (
            <table className="table">
              <thead><tr><th>Account</th><th className="num">Balance</th></tr></thead>
              <tbody>
                {summary.net_by_account.map((a) => (
                  <tr key={a.account_id}>
                    <td>{a.account_name}</td>
                    <td className={`num ${a.balance < 0 ? 'neg' : 'pos'}`}>{money(a.balance)}</td>
                  </tr>
                ))}
                <tr className="total-row">
                  <td><strong>Total</strong></td>
                  <td className="num"><strong>{money(netWorth)}</strong></td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
