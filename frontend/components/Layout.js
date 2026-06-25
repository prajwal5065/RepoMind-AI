import Link from 'next/link';
import { useRouter } from 'next/router';
import { Upload, MessageSquare, BarChart, Settings, FolderOpen } from 'lucide-react';
import { useState, useEffect } from 'react';
import { loadSession } from '@/utils/session';

export default function Layout({ children }) {
  const router = useRouter();
  const [activeSession, setActiveSession] = useState(null);

  useEffect(() => {
    const s = loadSession();
    if (s?.sessionId) setActiveSession(s);

    // Listen for storage changes (e.g. new session saved in another tab)
    const onStorage = () => {
      const s2 = loadSession();
      setActiveSession(s2?.sessionId ? s2 : null);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Re-check session after route changes so sidebar stays in sync
  useEffect(() => {
    const s = loadSession();
    setActiveSession(s?.sessionId ? s : null);
  }, [router.pathname]);

  const sessionId = activeSession?.sessionId;

  const navItems = [
    { label: 'Upload', href: '/', icon: Upload },
    { label: 'Chat', href: sessionId ? `/chat?session=${sessionId}` : '/chat', icon: MessageSquare },
    { label: 'Analysis', href: sessionId ? `/analysis?session=${sessionId}` : '/analysis', icon: BarChart },
  ];

  return (
    <div className="flex min-h-screen bg-[var(--color-canvas)] text-[var(--color-body)]">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[var(--color-hairline)] bg-[var(--color-canvas)] flex flex-col relative z-10">
        <div className="m-stripe absolute top-0 left-0 w-full"></div>
        <div className="p-8 border-b border-[var(--color-hairline)]">
          <h1 className="text-display-sm tracking-tighter">
            CODEMIND<span className="text-[var(--color-m-red)]">.</span>
          </h1>
        </div>
        
        <nav className="flex-1 p-6 space-y-4 mt-4">
          {navItems.map((item) => {
            const isActive = router.pathname === item.href.split('?')[0];
            const Icon = item.icon;
            return (
              <Link key={item.label} href={item.href} className="block group">
                <div className={`flex items-center gap-4 px-4 py-3 cursor-pointer transition-colors rounded-none ${
                  isActive 
                    ? 'text-[var(--color-on-dark)] bg-white/5 border-l-2 border-[var(--color-m-red)]' 
                    : 'text-[var(--color-body)] border-l-2 border-transparent hover:text-[var(--color-body-strong)] hover:bg-white/5'
                }`}>
                  <Icon size={20} className={isActive ? "text-[var(--color-on-dark)]" : ""} />
                  <span className="text-label-uppercase">{item.label}</span>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Active session indicator */}
        {activeSession && (
          <div className="px-6 pb-4">
            <div className="px-4 py-3 border border-[var(--color-hairline)] bg-[var(--color-surface-card)]">
              <div className="flex items-center gap-2 text-[var(--color-muted)]">
                <FolderOpen size={14} />
                <span className="text-label-uppercase text-[10px]">Active Repo</span>
              </div>
              <p className="text-body-sm text-white mt-1 truncate" title={activeSession.label || activeSession.sessionId}>
                {activeSession.label || activeSession.sessionId}
              </p>
            </div>
          </div>
        )}

        <div className="p-6 border-t border-[var(--color-hairline)]">
           <div className="flex items-center gap-4 text-[var(--color-muted)] hover:text-[var(--color-on-dark)] cursor-pointer transition-colors px-4 py-3">
             <Settings size={20} />
             <span className="text-label-uppercase">Settings</span>
           </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 relative overflow-hidden flex flex-col">
        {children}
      </main>
    </div>
  );
}
