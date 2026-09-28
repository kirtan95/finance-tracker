import { useEffect, useState } from 'react';
import { apiUpload } from '../api.js';
import { api } from '../api.js';
import { useAuth } from '../auth.jsx';

export default function Import() {
  const { token } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [file, setFile] = useState(null);
  const [mapping, setMapping] = useState({
    account_id: '',
    date_column: 'Date',
    description_column: 'Description',
    amount_column: 'Amount',
    type_column: '',
    category_column: '',
    date_format: '%Y-%m-%d',
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api('/api/accounts', { token }).then(setAccounts).catch(() => {});
  }, [token]);

  const set = (k) => (e) => setMapping({ ...mapping, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);
    if (!file) {
      setError('Choose a CSV file first.');
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('account_id', mapping.account_id);
      fd.append('date_column', mapping.date_column);
      fd.append('description_column', mapping.description_column);
      fd.append('amount_column', mapping.amount_column);
      if (mapping.type_column) fd.append('type_column', mapping.type_column);
      if (mapping.category_column) fd.append('category_column', mapping.category_column);
      fd.append('date_format', mapping.date_format);
      const res = await apiUpload('/api/import/csv', fd, token);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header"><h1>Import CSV</h1></div>
      <p className="muted">
        Upload a bank or credit-card statement. Tell us which columns hold the date,
        description and amount — negative amounts (or <code>(1,234.56)</code> style) count as expenses.
        Re-importing the same file is safe: already-imported rows are skipped.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <form className="form-grid" onSubmit={submit}>
          <label className="span-2">CSV file
            <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files[0])} required />
          </label>
          <label>Import into account
            <select value={mapping.account_id} onChange={set('account_id')} required>
              <option value="">Select…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </label>
          <label>Date format
            <input value={mapping.date_format} onChange={set('date_format')} required placeholder="%Y-%m-%d" />
          </label>
          <label>Date column
            <input value={mapping.date_column} onChange={set('date_column')} required />
          </label>
          <label>Description column
            <input value={mapping.description_column} onChange={set('description_column')} required />
          </label>
          <label>Amount column
            <input value={mapping.amount_column} onChange={set('amount_column')} required />
          </label>
          <label>Type column <span className="muted small">(optional)</span>
            <input value={mapping.type_column} onChange={set('type_column')} placeholder="e.g. Type" />
          </label>
          <label>Category column <span className="muted small">(optional)</span>
            <input value={mapping.category_column} onChange={set('category_column')} placeholder="e.g. Category" />
          </label>
          <div className="span-2 form-actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? 'Importing…' : 'Import CSV'}
            </button>
          </div>
        </form>
      </div>

      {result && (
        <div className="card">
          <h2>Import result</h2>
          <div className="stats-grid">
            <div className="card stat good"><div className="stat-label">Imported</div><div className="stat-value">{result.imported}</div></div>
            <div className="card stat"><div className="stat-label">Skipped (duplicates)</div><div className="stat-value">{result.skipped_duplicates}</div></div>
          </div>
          {result.errors.length > 0 && (
            <>
              <h3>Row errors</h3>
              <ul className="error-list">
                {result.errors.map((errMsg, i) => <li key={i}>{errMsg}</li>)}
              </ul>
            </>
          )}
        </div>
      )}

      <div className="card">
        <h2>Expected CSV format</h2>
        <pre className="code-block">{`Date,Description,Amount,Category
2026-09-01,Whole Foods Market,-84.32,Groceries
2026-09-03,ACME Corp Payroll,2500.00,Salary`}</pre>
        <p className="muted small">
          Column names can be anything — just map them above. Categories that don't exist yet are created automatically.
        </p>
      </div>
    </div>
  );
}
