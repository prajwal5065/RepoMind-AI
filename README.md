# CodeMind AI

CodeMind AI is an intelligent codebase analysis and exploration tool designed to help developers quickly understand, analyze, and securely audit new repositories. It provides a conversational interface powered by Google Gemini and advanced RAG (Retrieval-Augmented Generation) techniques, alongside static and security analysis.

## Features

- **Automated Repository Scanning**: Extract, chunk, and embed code from `.zip` archives.
- **RAG-Powered Chat**: Ask questions about your codebase and receive accurate, source-cited answers with an interactive Monaco editor integration.
- **Static Analysis**: Automated code quality checks using `pylint`, `flake8`, and `mypy`.
- **Security Review**: Vulnerability scanning via `bandit` and `semgrep`, with LLM-generated explanations and fix suggestions.
- **Documentation Generation**: Automated architecture overviews and module-level summaries in Markdown format.
- **BMW M Design System**: The frontend uses a bespoke, premium BMW M-inspired design language characterized by pure black canvas, full-bleed photography aesthetics, and technical typography.

## Architecture

- **Backend**: FastAPI (Python 3.11), ChromaDB for vector storage, Google Gemini API for LLM generation.
- **Frontend**: Next.js (Pages Router) and Tailwind CSS with custom BMW M tokens, Framer Motion for micro-animations.
- **Infrastructure**: Docker & Docker Compose for orchestration.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Environment Variables

1. Copy `.env.example` to `.env` in the root directory.
2. Set your Google Gemini API Key:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

### Running with Docker

The easiest way to run CodeMind AI is using Docker Compose:

```bash
docker-compose up --build
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/docs`

### Local Development

**Backend:**
```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Usage Workflow

1. Navigate to `http://localhost:3000`.
2. Upload a `.zip` file of a repository.
3. Wait for the processing pipeline (Parsing and Indexing) to finish.
4. You will be redirected to the Chat interface, where you can ask questions or open files.
5. Visit the Analysis Dashboard to review Security, Static Analysis, and Architecture docs.

## License

MIT License
