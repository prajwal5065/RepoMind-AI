import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Shield, Code, FileText, Download, AlertTriangle, AlertCircle } from 'lucide-react';
import { getAnalysis, getDocs } from '@/utils/api';
import ReactMarkdown from 'react-markdown';

export default function Analysis() {
  const router = useRouter();
  const { session } = router.query;
  
  const [activeTab, setActiveTab] = useState('security');
  const [analysis, setAnalysis] = useState([]);
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session) return;
    
    const fetchData = async () => {
      try {
        setLoading(true);
        const [analysisData, docsData] = await Promise.all([
          getAnalysis(session).catch(() => []),
          getDocs(session).catch(() => null)
        ]);
        setAnalysis(analysisData || []);
        setDocs(docsData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [session]);

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
    return <div className="flex-1 flex items-center justify-center text-display-sm">LOADING ANALYSIS...</div>;
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="p-xl border-b border-[var(--color-hairline)] bg-[var(--color-canvas)]">
        <h1 className="text-display-lg tracking-tighter">REPOSITORY ANALYSIS</h1>
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

      {/* Tabs */}
      <div className="flex px-xl border-b border-[var(--color-hairline)] bg-[var(--color-canvas)]">
        {['security', 'static', 'docs'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-lg py-md text-label-uppercase transition-colors cursor-pointer relative ${activeTab === tab ? 'text-[var(--color-on-dark)]' : 'text-[var(--color-body)] hover:text-white'}`}
          >
            {tab === 'security' && <span className="flex items-center gap-2"><Shield size={16}/> Security Review</span>}
            {tab === 'static' && <span className="flex items-center gap-2"><Code size={16}/> Static Analysis</span>}
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
              <p className="text-body-md text-[var(--color-muted)]">No security issues found.</p>
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
               <p className="text-body-md text-[var(--color-muted)]">No static analysis findings.</p>
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
      </div>
    </div>
  );
}
