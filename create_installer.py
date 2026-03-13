import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_NAME = "Finora"
VERSION_FILE = ROOT / "VERSION"
DIST_EXE = ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe"
INNO_SCRIPT = ROOT / "finora_installer.iss"
INNO_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
]


def run_command(cmd: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    print(f"[RUN] {printable}")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {printable}")


def read_version() -> str:
    if not VERSION_FILE.exists():
        raise RuntimeError("VERSION file not found.")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError("VERSION file is empty.")
    return version


def find_iscc() -> Path:
    for candidate in INNO_CANDIDATES:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Inno Setup compiler not found. Install Inno Setup 6 and retry."
    )


def clean_release_dirs() -> None:
    for folder in ("build", "dist", "dist_setup"):
        path = ROOT / folder
        if path.exists():
            print(f"[CLEAN] Removing {path}")
            shutil.rmtree(path)


def main() -> int:
    try:
        version = read_version()
        iscc = find_iscc()

        print("=" * 60)
        print(f"{APP_NAME} Release Builder")
        print(f"Version: {version}")
        print("=" * 60)

        clean_release_dirs()

        # Ensure translation binaries are always up to date for release.
        run_command([sys.executable, "-m", "babel.messages.frontend", "compile", "-d", "translations"])

        # Build deterministic executable from spec (includes icon + assets).
        run_command([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "Finora.spec"])

        if not DIST_EXE.exists():
            raise RuntimeError(f"Executable not generated: {DIST_EXE}")

        if not INNO_SCRIPT.exists():
            raise RuntimeError(f"Inno script not found: {INNO_SCRIPT}")

        # Inject release version at compile time.
        run_command([str(iscc), f"/DMyAppVersion={version}", str(INNO_SCRIPT)])

        setup_file = ROOT / "dist_setup" / f"Finora_Setup_v{version}.exe"
        if not setup_file.exists():
            raise RuntimeError(f"Installer not generated: {setup_file}")

        print("=" * 60)
        print("[SUCCESS] Build and installer generated.")
        print(f"Executable: {DIST_EXE}")
        print(f"Installer : {setup_file}")
        print("=" * 60)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
