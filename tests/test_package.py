"""The correction library installs and works as a package outside Home Assistant."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent

_CONSUMER = """
from stt_correction import build_corrector, plan_fix

corrector = build_corrector("zh-TW", replacements={"客聽": "客廳"}, phrases=["臥室燈"])
print(corrector.correct("打开客听和卧式灯。").corrected)


def corrector_for(fix):
    rules = {fix.wrong: fix.right} if fix and fix.kind == "replacement" else {}
    built = build_corrector("zh-TW", replacements=rules, phrases=["立扇"])
    return lambda text: built.correct(text).corrected


plan = plan_fix("打開力戰", "打開立扇", corrector_for, lambda fix: lambda text: True, [], ["立扇"])
print(plan.status, plan.fix and plan.fix.right)
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

    corrected, planned = result.stdout.strip().splitlines()
    assert corrected == "打開客廳和臥室燈"
    # A mishearing is planned into a fix with the installed library alone.
    assert planned.startswith("fix ")
