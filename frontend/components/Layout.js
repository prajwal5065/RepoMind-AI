import Link from 'next/link';
import { useRouter } from 'next/router';
import { Upload, MessageSquare, BarChart, Settings } from 'lucide-react';

export default function Layout({ children }) {
  const router = useRouter();

  const navItems = [
    { label: 'Upload', href: '/', icon: Upload },
    { label: 'Chat', href: '/chat', icon: MessageSquare },
    { label: 'Analysis', href: '/analysis', icon: BarChart },
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
            const isActive = router.pathname === item.href;
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className="block group">
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
