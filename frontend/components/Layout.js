import Link from 'next/link';
import { useRouter } from 'next/router';
import { Upload, MessageSquare, BarChart, Settings, FolderOpen, Zap } from 'lucide-react';
import { useState, useEffect } from 'react';
import { loadSession, saveLLMProvider, loadLLMProvider } from '@/utils/session';

export default function Layout({ children }) {
  const router = useRouter();
  const [activeSession, setActiveSession] = useState(null);
  const [provider, setProvider] = useState('groq');

  useEffect(() => {
    const s = loadSession();
    if (s?.sessionId) setActiveSession(s);
    setProvider(loadLLMProvider());

    const onStorage = () => {
      const s2 = loadSession();
      setActiveSession(s2?.sessionId ? s2 : null);
      setProvider(loadLLMProvider());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  useEffect(() => {
    const s = loadSession();
    setActiveSession(s?.sessionId ? s : null);
  }, [router.pathname]);

  const handleProviderChange = (p) => {
    setProvider(p);
    saveLLMProvider(p);
    // Dispatch storage event so other tabs/components pick up the change
    window.dispatchEvent(new Event('storage'));
  };

  const sessionId = activeSession?.sessionId;

  const navItems = [
    { label: 'Upload', href: '/', icon: Upload },
    { label: 'Chat',   href: sessionId ? `/chat?session=${sessionId}`     : '/chat',     icon: MessageSquare },
    { label: 'Analysis', href: sessionId ? `/analysis?session=${sessionId}` : '/analysis', icon: BarChart },
  ];

  const PROVIDERS = [
    {
      id: 'groq',
      label: 'GROQ',
      sub: 'Groq · llama3-70b',
      color: 'text-violet-400',
      activeBorder: 'border-violet-500',
      activeBg: 'bg-violet-500/10',
      dot: 'bg-violet-400',
    },
    {
      id: 'gemini',
      label: 'GEMINI',
      sub: 'Google · 2.5 Flash',
      color: 'text-blue-400',
      activeBorder: 'border-blue-500',
      activeBg: 'bg-blue-500/10',
      dot: 'bg-blue-400',
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-canvas)] text-[var(--color-body)]">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[var(--color-hairline)] bg-[var(--color-canvas)] flex flex-col relative z-10">
        <div className="m-stripe absolute top-0 left-0 w-full"></div>
        <div className="p-8 border-b border-[var(--color-hairline)]">
          <h1 className="text-display-sm tracking-tighter">
            CODEMIND<span className="text-[var(--color-m-red)]">.</span>
          </h1>
        </div>

        <nav className="flex-1 overflow-y-auto p-6 space-y-4 mt-4">
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
                  <Icon size={20} className={isActive ? 'text-[var(--color-on-dark)]' : ''} />
                  <span className="text-label-uppercase">{item.label}</span>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* ── LLM Provider Toggle ─────────────────────────────────────── */}
        <div className="px-6 pb-4">
          <div className="border border-[var(--color-hairline)] bg-[var(--color-surface-card)] p-3 space-y-2">
            <div className="flex items-center gap-2 text-[var(--color-muted)]">
              <Zap size={13} />
              <span className="text-label-uppercase text-[10px]">LLM Provider</span>
            </div>

            <div className="space-y-1.5">
              {PROVIDERS.map((p) => {
                const isActive = provider === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => handleProviderChange(p.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 border transition-all cursor-pointer text-left ${
                      isActive
                        ? `${p.activeBorder} ${p.activeBg} ${p.color}`
                        : 'border-transparent hover:border-[var(--color-hairline)] text-[var(--color-muted)] hover:text-[var(--color-body)]'
                    }`}
                  >
                    {/* Status dot */}
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isActive ? p.dot : 'bg-[var(--color-muted)] opacity-40'}`} />
                    <div className="flex-1 min-w-0">
                      <p className={`text-label-uppercase text-xs font-bold leading-none`}>{p.label}</p>
                      <p className="text-[10px] text-[var(--color-muted)] mt-0.5 truncate">{p.sub}</p>
                    </div>
                    {isActive && (
                      <span className="text-[9px] font-bold tracking-widest uppercase opacity-70">ACTIVE</span>
                    )}
                  </button>
                );
              })}
            </div>

            <p className="text-[9px] text-[var(--color-muted)] leading-snug pt-1">
              Auto-fallback enabled. Embeddings always use Gemini.
            </p>
          </div>
        </div>

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
