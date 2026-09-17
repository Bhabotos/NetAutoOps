import { LogOut, Menu, User as UserIcon } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../auth/useAuth";

export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-noc-border bg-noc-surface px-4">
      <button
        className="text-noc-text-muted md:hidden"
        onClick={onMenuClick}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="hidden md:block" />
      <div className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-noc-text hover:bg-noc-surface-raised"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-noc-surface-raised">
            <UserIcon className="h-4 w-4" aria-hidden="true" />
          </span>
          <span className="hidden sm:inline">{user?.username}</span>
          <span className="hidden rounded-full border border-noc-border px-2 py-0.5 text-xs capitalize text-noc-text-muted sm:inline">
            {user?.role}
          </span>
        </button>
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
            <div className="absolute right-0 z-20 mt-2 w-44 rounded-md border border-noc-border bg-noc-surface-raised py-1 shadow-xl">
              <div className="border-b border-noc-border px-3 py-2 text-xs text-noc-text-muted">
                Signed in as
                <div className="truncate text-sm text-noc-text">{user?.email}</div>
              </div>
              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-status-down hover:bg-noc-surface"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Log out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
