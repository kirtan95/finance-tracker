import { useEffect, useState } from 'react';
import { api, money } from '../api.js';
import { useAuth } from '../auth.jsx';

const TYPES = ['checking', 'savings', 'credit', 'cash', 'investment'];

export default function Accounts() {
  const { token } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', account_type: 'checking', starting_balance: '' });

  const load = async () => {
    try {
      setAccounts(await api('/api/accounts', { token }));
    } catch (e) {
      setError(e.message);
    }
  };
  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const startEdit = (a) => {
    setEditing(a);
    setForm({ name: a.name, account_type: a.account_type, starting_balance: '' });
  };
  const cancel = () => {
    setEditing(null);
    setForm({ name: '', account_type: 'checking', starting_balance: '' });
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (editing) {
        await api(`/api/accounts/${editing.id}`, {
          method: 'PATCH',
          token,
          body: { name: form.name, account_type: form.account_type },
        });
      } else {
        await api('/api/accounts', {
          method: 'POST',
          token,
          body: {
            name: form.name,
            account_type: form.account_type,
            starting_balance: Number(form.starting_balance) || 0,
          },
        });
      }
      cancel();
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this account and all its transactions?')) return;
    try {
      await api(`/api/accounts/${id}`, { method: 'DELETE', token });
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="page">
      <div className="page-header"><h1>Accounts</h1></div>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>{editing ? 'Edit account' : 'Add account'}</h2>
        <form className="form-grid" onSubmit={submit}>
          <label>Name
            <input value={form.name} onChange={set('name')} required maxLength={120} placeholder="e.g. Chase Checking" />
          </label>
          <label>Type
            <select value={form.account_type} onChange={set('account_type')}>
              {TYPES.map((t) => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
            </select>
          </label>
          {!editing && (
            <label>Starting balance
              <input type="number" step="0.01" value={form.starting_balance} onChange={set('starting_balance')} placeholder="0.00" />
            </label>
          )}
          <div className="form-actions">
            <button className="btn btn-primary" type="submit">{editing ? 'Save changes' : 'Add account'}</button>
            {editing && <button className="btn btn-ghost" type="button" onClick={cancel}>Cancel</button>}
          </div>
        </form>
        <p className="muted small">
          Balances update automatically: current balance = starting balance + income − expenses.
        </p>
      </div>

      <div className="accounts-grid">
        {accounts.map((a) => (
          <div key={a.id} className="card account-card">
            <div className="account-top">
              <div>
                <h3>{a.name}</h3>
                <span className="pill">{a.account_type}</span>
              </div>
              <div className={`account-balance ${a.current_balance < 0 ? 'neg' : ''}`}>
                {money(a.current_balance)}
              </div>
            </div>
            <div className="muted small">Started at {money(a.starting_balance)}</div>
            <div className="account-actions">
              <button className="btn btn-ghost btn-xs" onClick={() => startEdit(a)}>Edit</button>
              <button className="btn btn-ghost btn-xs danger" onClick={() => remove(a.id)}>Delete</button>
            </div>
          </div>
        ))}
      </div>
      {accounts.length === 0 && <p className="muted">No accounts yet — add your first one above.</p>}
    </div>
  );
}
