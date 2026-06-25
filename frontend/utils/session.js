
const SESSION_KEY  = 'repomind_session';
const PROVIDER_KEY = 'repomind_llm_provider';

// ── LLM Provider ─────────────────────────────────────────────────────────────
export function saveLLMProvider(provider) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(PROVIDER_KEY, provider);
}

export function loadLLMProvider() {
  if (typeof window === 'undefined') return 'groq';
  return localStorage.getItem(PROVIDER_KEY) || 'groq';
}

export function saveSession(sessionId, meta = {}) {
  if (typeof window === 'undefined') return;
  const data = {
    sessionId,
    savedAt: Date.now(),
    ...meta, // { label, type: 'zip'|'git', url?, fileName? }
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

export function loadSession() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearSession() {
  if (typeof window === 'undefined') return;
  const existing = loadSession();
  if (existing?.sessionId) {
    localStorage.removeItem(`repomind_messages_${existing.sessionId}`);
  }
  localStorage.removeItem(SESSION_KEY);
}

// ── Chat message history ─────────────────────────────────────────────────────
export function saveMessages(sessionId, messages) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(`repomind_messages_${sessionId}`, JSON.stringify(messages));
}

export function loadMessages(sessionId) {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(`repomind_messages_${sessionId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}
