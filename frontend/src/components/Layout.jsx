import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth.jsx';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">$</span>
          <span className="brand-name">Finance Tracker</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
          <NavLink to="/accounts">Accounts</NavLink>
          <NavLink to="/import">Import CSV</NavLink>
        </nav>
        <div className="sidebar-footer">
          <span className="user-email" title={user?.email}>{user?.name || user?.email}</span>
          <button className="btn btn-ghost" onClick={onLogout}>Log out</button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
