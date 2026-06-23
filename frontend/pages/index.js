import { useState, useCallback } from 'react';
import { useRouter } from 'next/router';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, GitBranch, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import { uploadRepo, parseRepo, indexRepo, cloneRepo } from '@/utils/api';

// Lightweight client-side URL validator (mirrors backend rules)
const GITHUB_LIKE = /^https:\/\/(github\.com|gitlab\.com|bitbucket\.org)\/([\w\-.]+\/[\w\-.]+?)(?:\.git)?\/?$/i;
const GENERIC_HTTPS = /^https:\/\/[\w\-.]+\.[\w]{2,}\/.+/i;

function validateGitUrl(url) {
  if (!url) return 'Please enter a repository URL.';
  if (!url.startsWith('https://')) return 'Only HTTPS URLs are supported.';
  if (GITHUB_LIKE.test(url) || GENERIC_HTTPS.test(url)) return null; // valid
  return 'Enter a valid Git URL, e.g. https://github.com/user/repo';
}

const STEPS_ZIP  = ['Uploading', 'Parsing', 'Indexing', 'Ready'];
const STEPS_GIT  = ['Cloning', 'Parsing', 'Indexing', 'Ready'];

export default function Home() {
  const router = useRouter();

  // 'zip' | 'git'
  const [mode, setMode]         = useState('zip');
  const [file, setFile]         = useState(null);
  const [gitUrl, setGitUrl]     = useState('');
  const [urlError, setUrlError] = useState('');
  const [status, setStatus]     = useState('idle');   // idle | step0..3 | error
  const [currentStep, setStep]  = useState(-1);
  const [errorMsg, setErrorMsg] = useState('');

  /* ── dropzone ─────────────────────────────────────────────── */
  const onDrop = useCallback((accepted) => {
    if (accepted.length) {
      setFile(accepted[0]);
      setStatus('idle');
      setErrorMsg('');
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/zip': ['.zip'] },
    maxFiles: 1,
    disabled: status !== 'idle' && status !== 'error',
  });

  /* ── URL field change ────────────────────────────────────── */
  const handleUrlChange = (e) => {
    const v = e.target.value;
    setGitUrl(v);
    setUrlError(v ? validateGitUrl(v) : '');
  };

  /* ── shared pipeline (parse → index → redirect) ─────────── */
  const runPipeline = async (sessionId) => {
    setStep(1);
    await parseRepo(sessionId);
    setStep(2);
    await indexRepo(sessionId);
    setStep(3);
    setStatus('done');
    setTimeout(() => router.push(`/chat?session=${sessionId}`), 900);
  };

  /* ── ZIP flow ────────────────────────────────────────────── */
  const handleZipProcess = async () => {
    if (!file) return;
    setStatus('running');
    setErrorMsg('');
    try {
      const sessionId = `sess_${Date.now()}`;
      setStep(0);
      await uploadRepo(file, sessionId);
      await runPipeline(sessionId);
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.response?.data?.detail || err.message || 'An unexpected error occurred.');
      setStep(-1);
    }
  };

  /* ── Git clone flow ──────────────────────────────────────── */
  const handleGitProcess = async () => {
    const err = validateGitUrl(gitUrl);
    if (err) { setUrlError(err); return; }
    setStatus('running');
    setErrorMsg('');
    try {
      setStep(0);
      const data = await cloneRepo(gitUrl);
      await runPipeline(data.session_id);
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.response?.data?.detail || err.message || 'An unexpected error occurred.');
      setStep(-1);
    }
  };

  const isRunning = status === 'running' || status === 'done';
  const steps     = mode === 'zip' ? STEPS_ZIP : STEPS_GIT;
  const canSubmit = mode === 'zip' ? !!file : (!urlError && !!gitUrl);

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-[var(--spacing-xl)] min-h-full">
      <div className="max-w-2xl w-full space-y-[var(--spacing-xl)]">

        {/* ── Hero ─────────────────────────────────────────── */}
        <div className="text-center space-y-[var(--spacing-sm)]">
          <h1 className="text-display-lg tracking-tighter">ANALYZE YOUR REPOSITORY.</h1>
          <p className="text-title-md text-[var(--color-body)]">
            Upload a ZIP archive or paste a public Git URL to get started with CodeMind AI.
          </p>
        </div>

        {!isRunning ? (
          <div className="space-y-[var(--spacing-lg)]">

            {/* ── Mode Tabs ─────────────────────────────────── */}
            <div className="flex border-b border-[var(--color-hairline)]">
              {[
                { id: 'zip', label: 'Upload ZIP', icon: UploadCloud },
                { id: 'git', label: 'Clone from URL', icon: GitBranch },
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => { setMode(id); setErrorMsg(''); setUrlError(''); }}
                  className={`flex items-center gap-2 px-[var(--spacing-lg)] py-[var(--spacing-md)] text-label-uppercase transition-colors relative cursor-pointer
                    ${mode === id
                      ? 'text-white'
                      : 'text-[var(--color-muted)] hover:text-[var(--color-body)]'}`}
                >
                  <Icon size={16} />
                  {label}
                  {mode === id && (
                    <span className="absolute bottom-0 left-0 w-full h-[2px] bg-white" />
                  )}
                </button>
              ))}
            </div>

            {/* ── ZIP panel ─────────────────────────────────── */}
            {mode === 'zip' && (
              <div
                {...getRootProps()}
                className={`border border-dashed p-[var(--spacing-xxl)] cursor-pointer transition-colors bg-[var(--color-surface-card)]
                  ${isDragActive ? 'border-white' : 'border-[var(--color-hairline)] hover:border-[var(--color-body)]'}`}
              >
                <input {...getInputProps()} />
                <div className="flex flex-col items-center gap-[var(--spacing-md)] text-center">
                  <UploadCloud size={48} className="text-[var(--color-muted)]" />
                  {file ? (
                    <p className="text-title-sm text-white">{file.name}</p>
                  ) : (
                    <>
                      <p className="text-title-sm">Drag &amp; drop your .zip file here</p>
                      <p className="text-body-sm text-[var(--color-muted)]">or click to browse &nbsp;·&nbsp; Only .zip files (max 50 MB)</p>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* ── Git URL panel ──────────────────────────────── */}
            {mode === 'git' && (
              <div className="space-y-[var(--spacing-md)]">
                <div className="relative">
                  <GitBranch
                    size={18}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--color-muted)]"
                  />
                  <input
                    type="url"
                    value={gitUrl}
                    onChange={handleUrlChange}
                    placeholder="https://github.com/user/repository"
                    className={`text-input pl-10 ${urlError ? 'border-[var(--color-m-red)]' : ''}`}
                    spellCheck={false}
                  />
                </div>

                {urlError && (
                  <p className="flex items-center gap-2 text-body-sm text-[var(--color-m-red)]">
                    <AlertCircle size={14} /> {urlError}
                  </p>
                )}

                <div className="p-[var(--spacing-md)] bg-[var(--color-surface-card)] border border-[var(--color-hairline)] space-y-[var(--spacing-xs)]">
                  <p className="text-label-uppercase text-[var(--color-muted)]">Supported hosts</p>
                  {['github.com', 'gitlab.com', 'bitbucket.org', 'Any public HTTPS Git URL'].map(h => (
                    <p key={h} className="text-body-sm text-[var(--color-body-strong)]">· {h}</p>
                  ))}
                  <p className="text-body-sm text-[var(--color-muted)] pt-[var(--spacing-xs)]">
                    Only <strong>public</strong> repositories are supported. Max 200 MB.
                  </p>
                </div>
              </div>
            )}

            {/* ── Error banner ───────────────────────────────── */}
            {errorMsg && (
              <div className="flex items-start gap-[var(--spacing-sm)] bg-red-950/30 border border-[var(--color-m-red)] text-[var(--color-m-red)] p-[var(--spacing-md)] text-body-sm">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* ── CTA ────────────────────────────────────────── */}
            <button
              onClick={mode === 'zip' ? handleZipProcess : handleGitProcess}
              disabled={!canSubmit}
              className={`btn-primary w-full ${!canSubmit ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              {mode === 'zip' ? 'START ANALYSIS' : 'CLONE & ANALYZE'}
            </button>

          </div>
        ) : (
          /* ── Progress panel ──────────────────────────────── */
          <div className="card-surface border border-[var(--color-hairline)] space-y-[var(--spacing-xl)]">
            <h3 className="text-title-lg">PROCESSING PIPELINE</h3>
            <div className="space-y-[var(--spacing-md)]">
              {steps.map((label, idx) => {
                const isPast   = idx < currentStep;
                const isActive = idx === currentStep;
                return (
                  <div
                    key={label}
                    className={`flex items-center gap-[var(--spacing-md)] transition-colors ${
                      isActive ? 'text-white' : isPast ? 'text-[var(--color-body)]' : 'text-[var(--color-muted)]'
                    }`}
                  >
                    <div className="w-8 flex justify-center">
                      {isPast
                        ? <CheckCircle size={24} className="text-[var(--color-success)]" />
                        : isActive
                          ? <Loader2 size={24} className="animate-spin" />
                          : <div className="w-2 h-2 rounded-full bg-current" />}
                    </div>
                    <span className="text-label-uppercase">{label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
