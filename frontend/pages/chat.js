import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/router';
import { MessageSquare, FileText, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import Editor from '@monaco-editor/react';
import { chatStreamUrl } from '@/utils/api';
import { loadSession, saveMessages, loadMessages, loadLLMProvider } from '@/utils/session';

export default function Chat() {
  const router = useRouter();
  const { session: sessionFromQuery } = router.query;

  // Resolve session: prefer URL query param, fall back to localStorage
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState('groq');
  
  const [activeFile, setActiveFile] = useState(null);
  const [fileContent, setFileContent] = useState('// Select a source file to view its contents');

  const messagesEndRef = useRef(null);

  // Sync provider from localStorage (updates when Layout toggle changes)
  useEffect(() => {
    setProvider(loadLLMProvider());
    const onStorage = () => setProvider(loadLLMProvider());
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);
  
  const suggestions = [
    "Explain this project",
    "How does auth work?",
    "What is the DB schema?"
  ];

  // ── Restore session and message history on mount ──────────────────────────
  useEffect(() => {
    if (!router.isReady) return;

    let resolvedSession = sessionFromQuery;
    if (!resolvedSession) {
      const saved = loadSession();
      if (saved?.sessionId) {
        resolvedSession = saved.sessionId;
        // Update URL without reloading so the back button still works
        router.replace(`/chat?session=${resolvedSession}`, undefined, { shallow: true });
      }
    }

    if (resolvedSession) {
      setSession(resolvedSession);
      const history = loadMessages(resolvedSession);
      if (history.length > 0) setMessages(history);
    }
  }, [router.isReady, sessionFromQuery]);

  // ── Persist messages whenever they change ─────────────────────────────────
  useEffect(() => {
    if (session && messages.length > 0) {
      saveMessages(session, messages);
    }
  }, [session, messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (text = input) => {
    if (!text.trim() || !session) return;
    
    const newMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, newMsg]);
    setInput('');
    setLoading(true);

    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const response = await fetch(chatStreamUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session, message: text, provider })
      });

      // Handle non-200 errors before touching the stream
      if (!response.ok) {
        let errDetail = `Server error (${response.status})`;
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || errDetail;
        } catch (_) { /* non-JSON body */ }
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1].content = `*Error: ${errDetail}*`;
          return updated;
        });
        return;
      }

      if (!response.body) throw new Error('No readable stream returned from server.');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (value) {
          assistantText += decoder.decode(value, { stream: true });
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1].content = assistantText;
            return updated;
          });
        }
      }
    } catch (err) {
      console.error('Stream error:', err);
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1].content =
          '*Error: Could not connect to the server. Make sure the backend is running.*';
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  const isQuotaError = (text) => {
    const t = text.toLowerCase();
    return t.includes('quota') || t.includes('exhausted') || t.includes('api quota limit') || t.includes('rate limit');
  };

  const isApiError = (text) => {
    return text.startsWith('*Error:') || text.startsWith('Error:');
  };

  const renderMessage = (msg) => {
    if (msg.role === 'user') return msg.content;
    
    // Quota / rate-limit banner
    if (isQuotaError(msg.content)) {
      return (
        <div className="border border-[var(--color-warning)] bg-amber-950/30 p-md space-y-sm">
          <div className="flex items-center gap-sm text-[var(--color-warning)]">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
            <span className="text-label-uppercase font-bold">API Quota Exceeded</span>
          </div>
          <p className="text-body-sm text-amber-200">
            {msg.content.replace(/^\*?Error:\s*/i, '').replace(/\*$/,'')}
          </p>
          <div className="text-body-sm text-[var(--color-muted)] space-y-1">
            <p>To resolve this:</p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Wait for your quota to reset or add billing credits</li>
              <li>Switch to the other provider in the left sidebar settings</li>
            </ul>
          </div>
        </div>
      );
    }

    // Generic error banner
    if (isApiError(msg.content)) {
      const cleanMsg = msg.content.replace(/^\*?Error:\s*/i, '').replace(/\*$/,'');
      return (
        <div className="border border-[var(--color-m-red)] bg-red-950/30 p-md flex items-start gap-sm">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--color-m-red)] mt-0.5 flex-shrink-0"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>
          <p className="text-body-sm text-red-300">{cleanMsg}</p>
        </div>
      );
    }
    
    const parts = msg.content.split('**Sources Cited:**');
    const mainText = parts[0];
    const citationsRaw = parts[1] ? parts[1].trim() : '';
    
    const citations = [];
    if (citationsRaw) {
      const regex = /- `(.*?)`/g;
      let match;
      while ((match = regex.exec(citationsRaw)) !== null) {
        citations.push(match[1]);
      }
    }

    return (
      <div className="space-y-md">
        <div className="prose prose-invert prose-p:text-body-md prose-headings:text-title-md max-w-none">
          <ReactMarkdown>{mainText}</ReactMarkdown>
        </div>
        
        {citations.length > 0 && (
          <div className="mt-md pt-md border-t border-[var(--color-hairline)] space-y-sm">
            <span className="text-label-uppercase text-[var(--color-muted)]">Sources Cited:</span>
            <div className="flex flex-wrap gap-sm">
              {citations.map((cite, idx) => (
                <button
                  key={idx}
                  onClick={() => openSource(cite)}
                  className="flex items-center gap-2 px-sm py-1 bg-[var(--color-surface-elevated)] border border-[var(--color-hairline)] hover:border-white transition-colors cursor-pointer text-caption text-white rounded-none"
                >
                  <FileText size={14} />
                  {cite}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const openSource = async (filePath) => {
    setActiveFile(filePath);
    setFileContent(`// Loading ${filePath}...`);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/file/${session}?path=${encodeURIComponent(filePath)}`);
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content);
      } else {
        setFileContent(`// Could not load file: ${filePath}`);
      }
    } catch {
      setFileContent(`// Error loading file: ${filePath}`);
    }
  };

  const getLanguage = (path) => {
    if (!path) return 'javascript';
    if (path.endsWith('.py')) return 'python';
    if (path.endsWith('.js') || path.endsWith('.jsx')) return 'javascript';
    if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'typescript';
    if (path.endsWith('.css')) return 'css';
    if (path.endsWith('.html')) return 'html';
    return 'plaintext';
  };

  if (!session) {
    return (
      <div className="flex-1 flex items-center justify-center text-[var(--color-muted)] text-body-md">
        No active session. <a href="/" className="ml-2 underline text-white">Upload a repository first.</a>
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-full overflow-hidden">
      <div className={`flex flex-col h-full ${activeFile ? 'w-1/2 border-r border-[var(--color-hairline)]' : 'w-full max-w-4xl mx-auto'}`}>
        <div className="p-xl border-b border-[var(--color-hairline)]">
          <h2 className="text-display-sm">REPOSITORY CHAT</h2>
          <p className="text-body-sm text-[var(--color-muted)]">Session: {session || 'Unknown'}</p>
        </div>

        <div className="flex-1 overflow-y-auto p-xl space-y-xl">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-lg">
              <MessageSquare size={48} className="text-[var(--color-muted)]" />
              <h3 className="text-title-lg text-[var(--color-body)]">Ask anything about the codebase</h3>
              <div className="flex flex-wrap justify-center gap-md">
                {suggestions.map((sug, idx) => (
                  <button 
                    key={idx}
                    onClick={() => handleSend(sug)}
                    className="px-md py-sm border border-[var(--color-hairline)] bg-[var(--color-surface-card)] hover:bg-[var(--color-surface-elevated)] transition-colors text-label-uppercase text-[var(--color-body)]"
                  >
                    {sug}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-lg ${
                  msg.role === 'user' 
                    ? 'bg-[var(--color-surface-card)] border-l-4 border-[var(--color-m-red)]' 
                    : 'bg-[var(--color-canvas)] border border-[var(--color-hairline)]'
                }`}>
                  <div className="text-label-uppercase text-[var(--color-muted)] mb-sm">
                    {msg.role === 'user' ? 'You' : 'CodeMind AI'}
                  </div>
                  <div className="text-body-md">
                    {renderMessage(msg)}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-lg border-t border-[var(--color-hairline)] bg-[var(--color-canvas)]">
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex gap-md"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about the code..."
              className="text-input flex-1"
              disabled={loading}
            />
            <button 
              type="submit"
              disabled={loading || !input.trim()}
              className={`btn-primary px-4 w-12 flex justify-center items-center ${loading ? 'opacity-50' : ''}`}
            >
              <ChevronRight size={24} />
            </button>
          </form>
        </div>
      </div>

      {activeFile && (
        <div className="w-1/2 h-full flex flex-col bg-[var(--color-canvas)]">
          <div className="p-md border-b border-[var(--color-hairline)] flex justify-between items-center bg-[var(--color-surface-card)]">
            <div className="flex items-center gap-sm">
              <FileText size={18} className="text-[var(--color-muted)]" />
              <span className="text-label-uppercase">{activeFile}</span>
            </div>
            <button 
              onClick={() => setActiveFile(null)}
              className="text-label-uppercase text-[var(--color-muted)] hover:text-white cursor-pointer"
            >
              CLOSE
            </button>
          </div>
          <div className="flex-1 relative">
            <Editor
              height="100%"
              language={getLanguage(activeFile)}
              theme="vs-dark"
              value={fileContent}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                fontSize: 14,
                fontFamily: 'Inter, monospace',
                scrollBeyondLastLine: false,
                wordWrap: 'on'
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
