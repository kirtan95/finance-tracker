import { useEffect, useState } from 'react';
import { api, money, todayDate } from '../api.js';
import { useAuth } from '../auth.jsx';

const emptyForm = {
  account_id: '',
  category_id: '',
  amount: '',
  type: 'expense',
  description: '',
  date: todayDate(),
};

function TxnForm({ initial, accounts, categories, onSave, onCancel, saving }) {
  const [form, setForm] = useState(initial || emptyForm);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = (e) => {
    e.preventDefault();
    onSave({
      account_id: Number(form.account_id),
      category_id: form.category_id ? Number(form.category_id) : null,
      amount: Number(form.amount),
      type: form.type,
      description: form.description,
      date: form.date,
    });
  };

  return (
    <form className="form-grid" onSubmit={submit}>
      <label>Account
        <select value={form.account_id} onChange={set('account_id')} required>
          <option value="">Select…</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </label>
      <label>Type
        <select value={form.type} onChange={set('type')}>
          <option value="expense">Expense</option>
          <option value="income">Income</option>
        </select>
      </label>
      <label>Amount
        <input type="number" min="0.01" step="0.01" value={form.amount} onChange={set('amount')} required />
      </label>
      <label>Date
        <input type="date" value={form.date} onChange={set('date')} required />
      </label>
      <label>Category
        <select value={form.category_id} onChange={set('category_id')}>
          <option value="">Uncategorized</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <label className="span-2">Description
        <input value={form.description} onChange={set('description')} placeholder="e.g. Whole Foods" maxLength={500} />
      </label>
      <div className="span-2 form-actions">
        <button className="btn btn-primary" type="submit" disabled={saving}>
          {saving ? 'Saving…' : initial ? 'Save changes' : 'Add transaction'}
        </button>
        {onCancel && <button className="btn btn-ghost" type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

export default function Transactions() {
  const { token } = useAuth();
  const [txns, setTxns] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [filters, setFilters] = useState({ account_id: '', category_id: '', type: '', start_date: '', end_date: '' });

  const load = async () => {
    try {
      const params = new URLSearchParams({ limit: '200' });
      for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
      const [t, a, c] = await Promise.all([
        api(`/api/transactions?${params}`, { token }),
        api('/api/accounts', { token }),
        api('/api/categories', { token }),
      ]);
      setTxns(t);
      setAccounts(a);
      setCategories(c);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps
  const applyFilters = (e) => { e.preventDefault(); load(); };

  const addTxn = async (body) => {
    setSaving(true);
    try {
      await api('/api/transactions', { method: 'POST', token, body });
      await load();
      document.getElementById('txn-add-form').reset?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const saveEdit = async (body) => {
    setSaving(true);
    try {
      await api(`/api/transactions/${editing.id}`, { method: 'PATCH', token, body });
      setEditing(null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this transaction?')) return;
    try {
      await api(`/api/transactions/${id}`, { method: 'DELETE', token });
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="page">
      <div className="page-header"><h1>Transactions</h1></div>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>Add transaction</h2>
        <div id="txn-add-form">
          <TxnForm key={txns.length} accounts={accounts} categories={categories} onSave={addTxn} saving={saving} />
        </div>
      </div>

      <div className="card">
        <h2>History</h2>
        <form className="filters" onSubmit={applyFilters}>
          <select className="input" value={filters.account_id} onChange={setF('account_id')}>
            <option value="">All accounts</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select className="input" value={filters.category_id} onChange={setF('category_id')}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className="input" value={filters.type} onChange={setF('type')}>
            <option value="">Income + expenses</option>
            <option value="income">Income</option>
            <option value="expense">Expenses</option>
          </select>
          <input className="input" type="date" value={filters.start_date} onChange={setF('start_date')} />
          <input className="input" type="date" value={filters.end_date} onChange={setF('end_date')} />
          <button className="btn btn-secondary" type="submit">Filter</button>
        </form>

        {txns.length === 0 ? (
          <p className="muted">No transactions found.</p>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr><th>Date</th><th>Description</th><th>Category</th><th>Account</th><th className="num">Amount</th><th></th></tr>
              </thead>
              <tbody>
                {txns.map((t) => (
                  <tr key={t.id}>
                    <td className="nowrap">{t.date}</td>
                    <td>{t.description || <span className="muted">—</span>}</td>
                    <td>{t.category_name || <span className="muted">Uncategorized</span>}</td>
                    <td>{t.account_name}</td>
                    <td className={`num ${t.type === 'income' ? 'pos' : 'neg'}`}>
                      {t.type === 'income' ? '+' : '−'}{money(t.amount)}
                    </td>
                    <td className="nowrap actions">
                      <button className="btn btn-ghost btn-xs" onClick={() => setEditing(t)}>Edit</button>
                      <button className="btn btn-ghost btn-xs danger" onClick={() => remove(t.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit transaction</h2>
            <TxnForm
              initial={{
                account_id: String(editing.account_id),
                category_id: editing.category_id ? String(editing.category_id) : '',
                amount: String(editing.amount),
                type: editing.type,
                description: editing.description,
                date: editing.date,
              }}
              accounts={accounts}
              categories={categories}
              onSave={saveEdit}
              onCancel={() => setEditing(null)}
              saving={saving}
            />
          </div>
        </div>
      )}
    </div>
  );
}
