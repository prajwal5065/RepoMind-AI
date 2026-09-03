import os
import pytest


@pytest.fixture
def anyio_backend():
    # anyio is already pulled in transitively (httpx/starlette depend on
    # it), so this lets `async def test_...` functions run under
    # @pytest.mark.anyio without adding a new pytest-asyncio dependency.
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def test_env():
    """
    Ensure the app's required env vars are present for the whole test
    session, so tests that exercise real client-construction code paths
    (embedder, LLM clients) don't fail purely because GEMINI_API_KEY /
    GROQ_API_KEY aren't set in the CI environment.
    """
    os.environ.setdefault("API_KEY", "test-secret-key-1234")
    os.environ.setdefault("GEMINI_API_KEY", "fake")
    os.environ.setdefault("GROQ_API_KEY", "fake")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

    # If config.settings was already instantiated during an earlier import,
    # patch it directly too — setdefault() on os.environ only affects
    # future reads.
    try:
        import config
        config.settings.API_KEY = os.environ["API_KEY"]
        config.settings.GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
        config.settings.GROQ_API_KEY = os.environ["GROQ_API_KEY"]
        config.settings.DEBUG = True
        config.settings.ALLOWED_ORIGINS = os.environ["ALLOWED_ORIGINS"]
    except Exception:
        # Safe to ignore if config hasn't been imported yet
        pass

    yield
