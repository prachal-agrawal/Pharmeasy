import React, { useState, useEffect } from "react";
import { Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { ShoppingCart, Search, User, LogOut, Package, Shield } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const { count } = useCart();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const urlSearch = searchParams.get("search") ?? "";
  const [search, setSearch] = useState(urlSearch);
  const [menuOpen, setMenuOpen] = useState(false);

  // Keep the input in sync when ?search= changes (e.g. Home loads, browser back, or submit)
  useEffect(() => {
    setSearch(urlSearch);
  }, [urlSearch]);

  const handleSearch = (e) => {
    e.preventDefault();
    const q = search.trim();
    if (q) {
      navigate({ pathname: "/", search: `?search=${encodeURIComponent(q)}` });
    } else {
      navigate("/");
    }
  };

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="bg-white border-b border-gray-100 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-3">
        {/* Logo */}
        <Link to="/" className="text-xl font-extrabold text-brand tracking-tight shrink-0">
          Bharat<span className="text-amber">Medical</span>
        </Link>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-md relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search medicines, brands..."
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-full bg-gray-50 outline-none focus:border-brand focus:bg-white transition-all"
          />
        </form>

        {/* Nav links */}
        <div className="hidden sm:flex items-center gap-1">
          <NavLink to="/" active={isActive("/")}>
            Catalog
          </NavLink>
          <NavLink to="/orders" active={isActive("/orders")}>
            Orders
          </NavLink>
        </div>

        {/* Cart */}
        <Link to="/cart" className="relative p-2 hover:bg-brand-light rounded-md transition-colors">
          <ShoppingCart className="w-5 h-5 text-brand" />
          {count > 0 && (
            <span className="absolute -top-1 -right-1 bg-amber text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
              {count > 9 ? "9+" : count}
            </span>
          )}
        </Link>

        {/* User menu */}
        {user ? (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 bg-brand-light text-brand px-3 py-1.5 rounded-md text-sm font-semibold hover:bg-brand hover:text-white transition-colors"
            >
              <User className="w-3.5 h-3.5" />
              {user.name.split(" ")[0]}
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-10 bg-white border border-gray-100 rounded-xl shadow-lg py-1 w-44 z-50">
                <Link
                  to="/orders"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors"
                >
                  <Package className="w-4 h-4" /> My Orders
                </Link>
                {user.role === "admin" && (
                  <Link
                    to="/admin"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors text-info"
                  >
                    <Shield className="w-4 h-4" /> Admin Panel
                  </Link>
                )}
                <hr className="my-1 border-gray-100" />
                <button
                  onClick={() => {
                    logout();
                    setMenuOpen(false);
                    navigate("/");
                  }}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors w-full text-left text-danger"
                >
                  <LogOut className="w-4 h-4" /> Logout
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link to="/login" className="btn-primary text-sm py-1.5 px-4">
            Login
          </Link>
        )}
      </div>
    </nav>
  );
}

function NavLink({ to, active, children }) {
  return (
    <Link
      to={to}
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active ? "bg-brand-light text-brand" : "text-gray-500 hover:bg-gray-100"
      }`}
    >
      {children}
    </Link>
  );
}
