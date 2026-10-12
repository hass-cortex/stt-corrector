"""The correction library installs and works as a package outside Home Assistant."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent

_CONSUMER = """
from stt_correction import build_corrector

corrector = build_corrector("zh-TW", replacements={"客聽": "客廳"}, phrases=["臥室燈"])
print(corrector.correct("打开客听和卧式灯。").corrected)
"""


@pytest.mark.integration
def test_installed_package_corrects_a_sentence(tmp_path: Path) -> None:
    """A fresh venv without Home Assistant installs the repo and corrects text."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed")
    venv = tmp_path / "venv"
    python = venv / "bin" / "python"
    subprocess.run(
        [uv, "venv", "-q", "--python", sys.executable, str(venv)], check=True
    )
    subprocess.run(
        [uv, "pip", "install", "-q", "--python", str(python), str(_REPO)], check=True
    )

    # -I and a cwd outside the repo: only the installed package is importable.
    result = subprocess.run(
        [str(python), "-I", "-c", _CONSUMER],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "打開客廳和臥室燈"
