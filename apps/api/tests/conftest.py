import os
import tempfile
from pathlib import Path

# Must run before any apps.api import: the engine and storage read these at import time.
_TMP = Path(tempfile.mkdtemp(prefix="attest-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = str(_TMP / "uploads")
os.environ.pop("LLM_BASE_URL", None)
os.environ.pop("LLM_MODEL", None)

import pytest  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")
