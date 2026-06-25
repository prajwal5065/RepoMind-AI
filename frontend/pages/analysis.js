import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Shield, Code, FileText, Download, AlertTriangle, AlertCircle, PlusCircle } from 'lucide-react';
import { getAnalysis, getDocs } from '@/utils/api';
import { loadSession, clearSession } from '@/utils/session';
import ReactMarkdown from 'react-markdown';

export default function Analysis() {
  const router = useRouter();
  const { session: sessionFromQuery } = router.query;

  const [session, setSession] = useState(null);
  const [activeTab, setActiveTab] = useState('security');
  const [analysis, setAnalysis] = useState([]);
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingStep, setLoadingStep] = useState(0);   // 0-4
  const [loadingPct, setLoadingPct] = useState(0);    // 0-100

  const LOADING_STEPS = [
    { label: 'Scanning repository files',   pct: 10 },
    { label: 'Running security checks',     pct: 35 },
    { label: 'Running static analysis',     pct: 60 },
    { label: 'AI explaining findings',      pct: 85 },
    { label: 'Generating documentation',   pct: 95 },
  ];

  // ── Resolve session (URL or localStorage) ─────────────────────────────────
  useEffect(() => {
    if (!router.isReady) return;

    let resolvedSession = sessionFromQuery;
    if (!resolvedSession) {
      const saved = loadSession();
      if (saved?.sessionId) {
        resolvedSession = saved.sessionId;
        router.replace(`/analysis?session=${resolvedSession}`, undefined, { shallow: true });
      }
    }

    if (resolvedSession) {
      setSession(resolvedSession);
    } else {
      setLoading(false);
      setError('No session found. Please upload or clone a repository first.');
    }
  }, [router.isReady, sessionFromQuery]);

  // ── Fetch analysis data once session is resolved ───────────────────────────
  useEffect(() => {
    if (!session) return;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        setLoadingStep(0);
        setLoadingPct(5);

        // Simulate step progression while the long API call runs
        const stepTimings = [800, 2000, 3500, 5500];
        let cancelled = false;
        stepTimings.forEach((delay, i) => {
          setTimeout(() => {
            if (!cancelled) {
              setLoadingStep(i + 1);
              setLoadingPct(LOADING_STEPS[i + 1]?.pct || 85);
            }
          }, delay);
        });

        const [analysisData, docsData] = await Promise.all([
          getAnalysis(session),
          getDocs(session).catch(() => null)
        ]);

        cancelled = true;
        setLoadingStep(5);
        setLoadingPct(100);
        // Small pause so the 100% flashes before content appears
        await new Promise(r => setTimeout(r, 400));

        setAnalysis(analysisData || []);
        setDocs(docsData);
      } catch (err) {
        console.error(err);
        const detail = err?.response?.data?.detail;
        if (detail) {
          setError(detail);
        } else {
          setError('Analysis failed. Check backend logs.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const handleStartNew = () => {
    clearSession();
    router.push('/');
  };

  const securityFindings = analysis.filter(f => ['bandit', 'semgrep'].includes(f.tool));
  const staticFindings = analysis.filter(f => ['pylint', 'flake8', 'mypy'].includes(f.tool));
  
  const groupedStatic = staticFindings.reduce((acc, finding) => {
    if (!acc[finding.file]) acc[finding.file] = [];
    acc[finding.file].push(finding);
    return acc;
  }, {});

  const exportDocs = () => {
    window.open(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/docs/${session}/export`, '_blank');
  };

  const SeverityBadge = ({ severity }) => {
    const colors = {
      HIGH: 'bg-[var(--color-m-red)] text-white',
      ERROR: 'bg-[var(--color-m-red)] text-white',
      MEDIUM: 'bg-[var(--color-warning)] text-black',
      WARNING: 'bg-[var(--color-warning)] text-black',
      LOW: 'bg-[var(--color-surface-elevated)] text-[var(--color-body)]'
    };
    return (
      <span className={`px-2 py-1 text-xs font-bold tracking-widest uppercase ${colors[severity] || colors.LOW}`}>
        {severity}
      </span>
    );
  };

  if (loading) {
    const currentLabel = LOADING_STEPS[Math.min(loadingStep, LOADING_STEPS.length - 1)]?.label || 'Preparing...';
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-xl p-xl">
        <div className="w-full max-w-md space-y-xl">
          {/* Header */}
          <div className="text-center space-y-sm">
            <h2 className="text-display-sm tracking-tighter">ANALYZING REPOSITORY</h2>
            <p className="text-body-sm text-[var(--color-muted)]">
              Running security &amp; quality checks. This may take a minute.
            </p>
          </div>

          {/* Big percentage */}
          <div className="text-center">
            <span
              className="text-[80px] font-black tabular-nums leading-none tracking-tighter"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {loadingPct}
              <span className="text-[40px] text-[var(--color-muted)]">%</span>
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-[3px] w-full bg-[var(--color-surface-elevated)] overflow-hidden">
            <div
              className="h-full bg-white transition-all duration-700 ease-out"
              style={{ width: `${loadingPct}%` }}
            />
          </div>

          {/* Step list */}
          <div className="space-y-sm">
            {LOADING_STEPS.map((step, idx) => {
              const isDone    = idx < loadingStep;
              const isActive  = idx === loadingStep;
              const isPending = idx > loadingStep;
              return (
                <div
                  key={step.label}
                  className={`flex items-center gap-md transition-all duration-300 ${
                    isDone    ? 'text-[var(--color-body)]' :
                    isActive  ? 'text-white' :
                                'text-[var(--color-muted)] opacity-50'
                  }`}
                >
                  {/* Step icon */}
                  <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                    {isDone ? (
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--color-success)]"><path d="M20 6 9 17l-5-5"/></svg>
                    ) : isActive ? (
                      <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-current" />
                    )}
                  </div>
                  <span className={`text-label-uppercase text-sm ${ isActive ? 'font-bold' : '' }`}>
                    {step.label}
                  </span>
                  {isDone && (
                    <span className="ml-auto text-[var(--color-success)] text-xs font-mono">✓</span>
                  )}
                  {isActive && (
                    <span className="ml-auto text-[var(--color-muted)] text-xs animate-pulse">{step.pct}%</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Current step label */}
          <p className="text-center text-body-sm text-[var(--color-muted)] animate-pulse">
            {currentLabel}...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-lg p-xl">
        <AlertCircle size={48} className="text-[var(--color-m-red)]" />
        <p className="text-display-sm text-[var(--color-m-red)] text-center">{error}</p>
        <button
          onClick={handleStartNew}
          className="btn-primary flex items-center gap-2"
        >
          <PlusCircle size={16} /> Start New Analysis
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="p-xl border-b border-[var(--color-hairline)] bg-[var(--color-canvas)] flex justify-between items-start">
        <div>
          <h1 className="text-display-lg tracking-tighter">REPOSITORY ANALYSIS</h1>
          {session && (
            <p className="text-body-sm text-[var(--color-muted)] mt-1">Session: {session}</p>
          )}
          {docs && (
            <div className="mt-lg flex gap-md">
              <div className="card-surface flex-1 border border-[var(--color-hairline)]">
                <span className="text-label-uppercase text-[var(--color-muted)]">Tech Stack</span>
                <p className="text-title-sm mt-sm text-white">{docs.tech_stack || 'Unknown'}</p>
              </div>
              <div className="card-surface flex-1 border border-[var(--color-hairline)]">
                <span className="text-label-uppercase text-[var(--color-muted)]">Entry Points</span>
                <p className="text-title-sm mt-sm text-white">{docs.entry_points?.join(', ') || 'None'}</p>
              </div>
            </div>
          )}
        </div>
        {/* Start New Analysis button */}
        <button
          onClick={handleStartNew}
          className="flex items-center gap-2 px-md py-sm border border-[var(--color-hairline)] text-label-uppercase hover:bg-white/5 hover:border-white transition-colors cursor-pointer flex-shrink-0"
        >
          <PlusCircle size={16} />
          Start New Analysis
        </button>
      </div>

      {/* Tabs */}
      <div className="flex px-xl border-b border-[var(--color-hairline)] bg-[var(--color-canvas)]">
        {['security', 'static', 'docs'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-lg py-md text-label-uppercase transition-colors cursor-pointer relative ${activeTab === tab ? 'text-[var(--color-on-dark)]' : 'text-[var(--color-body)] hover:text-white'}`}
          >
            {tab === 'security' && <span className="flex items-center gap-2"><Shield size={16}/> Security Review
              {securityFindings.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-[var(--color-m-red)] text-white text-[10px] font-bold">{securityFindings.length}</span>
              )}
            </span>}
            {tab === 'static' && <span className="flex items-center gap-2"><Code size={16}/> Static Analysis
              {staticFindings.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-[var(--color-surface-elevated)] text-[var(--color-body)] text-[10px] font-bold">{staticFindings.length}</span>
              )}
            </span>}
            {tab === 'docs' && <span className="flex items-center gap-2"><FileText size={16}/> Documentation</span>}
            
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 w-full h-[2px] bg-white"></div>
            )}
          </button>
        ))}
        <div className="flex-1"></div>
        {activeTab === 'docs' && (
          <button onClick={exportDocs} className="flex items-center gap-2 px-lg py-md text-label-uppercase cursor-pointer hover:text-white text-[var(--color-m-blue-light)]">
            <Download size={16} /> Export Markdown
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-xl">
        {activeTab === 'security' && (
          <div className="space-y-xl max-w-5xl mx-auto">
            <h2 className="text-display-sm">SECURITY FINDINGS</h2>
            {securityFindings.length === 0 ? (
              <div className="border border-[var(--color-hairline)] p-xl text-center">
                <Shield size={40} className="mx-auto text-[var(--color-success)] mb-md" />
                <p className="text-title-md text-[var(--color-success)]">No security issues found.</p>
                <p className="text-body-sm text-[var(--color-muted)] mt-sm">Your repository passed all security checks.</p>
              </div>
            ) : (
              securityFindings.map((finding, idx) => (
                <div key={idx} className="card-surface border border-[var(--color-hairline)] relative overflow-hidden">
                  {finding.severity === 'HIGH' && <div className="absolute left-0 top-0 w-1 h-full bg-[var(--color-m-red)]"></div>}
                  <div className="flex justify-between items-start mb-md">
                    <div>
                      <h3 className="text-title-lg flex items-center gap-sm">
                        {finding.severity === 'HIGH' ? <AlertTriangle className="text-[var(--color-m-red)]" /> : <AlertCircle />}
                        {finding.tool.toUpperCase()} FINDING
                      </h3>
                      <p className="text-body-sm text-[var(--color-muted)] mt-1">{finding.file} : Line {finding.line}</p>
                    </div>
                    <SeverityBadge severity={finding.severity} />
                  </div>
                  
                  <div className="p-md bg-[var(--color-canvas)] border border-[var(--color-hairline)] mb-md">
                    <p className="text-body-md font-mono">{finding.message}</p>
                  </div>

                  {finding.explanation && (
                    <div className="mt-md space-y-md border-t border-[var(--color-hairline)] pt-md">
                      <div>
                        <span className="text-label-uppercase text-[var(--color-m-blue-light)]">Explanation</span>
                        <p className="text-body-md mt-sm">{finding.explanation}</p>
                      </div>
                      {finding.fix_suggestion && (
                        <div className="mt-md">
                          <span className="text-label-uppercase text-[var(--color-success)]">Suggested Fix</span>
                          <pre className="bg-[var(--color-canvas)] p-md mt-sm border border-[var(--color-hairline)] text-sm overflow-x-auto text-body-strong whitespace-pre-wrap">
                            <code>{finding.fix_suggestion}</code>
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'static' && (
          <div className="space-y-xl max-w-5xl mx-auto">
             <h2 className="text-display-sm">CODE QUALITY</h2>
             {Object.keys(groupedStatic).length === 0 ? (
               <div className="border border-[var(--color-hairline)] p-xl text-center">
                 <Code size={40} className="mx-auto text-[var(--color-success)] mb-md" />
                 <p className="text-title-md text-[var(--color-success)]">No static analysis findings.</p>
                 <p className="text-body-sm text-[var(--color-muted)] mt-sm">Your code passes all linting and style checks.</p>
               </div>
             ) : (
               Object.entries(groupedStatic).map(([file, findings]) => (
                 <div key={file} className="mb-xl">
                   <h3 className="text-title-md mb-md p-md bg-[var(--color-surface-elevated)]">{file}</h3>
                   <div className="space-y-sm">
                     {findings.map((f, idx) => (
                       <div key={idx} className="flex items-start gap-md p-md bg-[var(--color-surface-card)] border-l-2 border-[var(--color-hairline)]">
                         <div className="w-24 flex-shrink-0">
                           <SeverityBadge severity={f.severity} />
                         </div>
                         <div className="w-16 flex-shrink-0 text-[var(--color-muted)] font-mono text-sm">
                           L{f.line}
                         </div>
                         <div className="flex-1">
                           <span className="text-label-uppercase text-[var(--color-muted)] mr-sm">[{f.tool}]</span>
                           <span className="text-body-sm text-white">{f.message}</span>
                           {f.explanation && (
                             <p className="text-body-sm text-[var(--color-muted)] mt-1 italic">{f.explanation}</p>
                           )}
                         </div>
                       </div>
                     ))}
                   </div>
                 </div>
               ))
             )}
          </div>
        )}

        {activeTab === 'docs' && docs && (
          <div className="max-w-4xl mx-auto prose prose-invert prose-p:text-body-md prose-headings:text-title-lg prose-h1:text-display-md">
             <h1>ARCHITECTURE OVERVIEW</h1>
             <ReactMarkdown>{docs.architecture_summary}</ReactMarkdown>
             
             <div className="my-xl m-stripe"></div>
             
             <h2>MODULES</h2>
             {docs.modules?.map((mod, idx) => (
               <div key={idx} className="mb-lg p-lg border border-[var(--color-hairline)] bg-[var(--color-surface-card)]">
                 <h3 className="text-[var(--color-m-blue-light)]">{mod.module_path}</h3>
                 <p className="mb-md">{mod.purpose}</p>
                 {mod.public_functions?.length > 0 && (
                   <div>
                     <strong className="text-label-uppercase">Public API:</strong>
                     <ul className="mt-sm space-y-1">
                       {mod.public_functions.map((fn, i) => (
                         <li key={i}><code className="text-[var(--color-body-strong)]">{fn.name || 'func'}</code> - {fn.description}</li>
                       ))}
                     </ul>
                   </div>
                 )}
               </div>
             ))}
          </div>
        )}

        {activeTab === 'docs' && !docs && (
          <div className="max-w-4xl mx-auto text-center py-xl">
            <FileText size={40} className="mx-auto text-[var(--color-muted)] mb-md" />
            <p className="text-title-md text-[var(--color-muted)]">Documentation not available for this session.</p>
          </div>
        )}
      </div>
    </div>
  );
}
