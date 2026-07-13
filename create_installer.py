import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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
SIGNTOOL_ROOT = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"


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


def find_signtool() -> Path:
    candidates = sorted(SIGNTOOL_ROOT.glob("*\\x64\\signtool.exe"), reverse=True)
    if candidates:
        return candidates[0]
    raise RuntimeError("SignTool not found. Install the Windows SDK and retry.")


def sign_file(file_path: Path) -> bool:
    certificate_sha1 = os.environ.get("FINORA_SIGNING_CERT_SHA1", "").strip()
    require_signing = os.environ.get("FINORA_REQUIRE_SIGNING", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if not certificate_sha1:
        if require_signing:
            raise RuntimeError("FINORA_SIGNING_CERT_SHA1 is required for this release build.")
        print(f"[WARNING] Unsigned development build: {file_path.name}")
        return False

    signtool = find_signtool()
    timestamp_url = os.environ.get("FINORA_TIMESTAMP_URL", DEFAULT_TIMESTAMP_URL).strip()
    run_command(
        [
            str(signtool), "sign", "/sha1", certificate_sha1,
            "/fd", "SHA256", "/tr", timestamp_url, "/td", "SHA256",
            "/d", "Finora", "/du", "https://github.com/informigados/finora",
            str(file_path),
        ]
    )
    run_command([str(signtool), "verify", "/pa", "/all", "/v", str(file_path)])
    return True


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as release_file:
        for chunk in iter(lambda: release_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_release_metadata(version: str, installer_path: Path, signed: bool) -> None:
    installer_hash = calculate_sha256(installer_path)
    checksum_path = installer_path.parent / "SHA256SUMS.txt"
    checksum_path.write_text(
        f"{installer_hash}  {installer_path.name}\n",
        encoding="utf-8",
    )

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    metadata = {
        "application": APP_NAME,
        "version": version,
        "commit": commit or None,
        "installer": installer_path.name,
        "sha256": installer_hash,
        "authenticode_signed": signed,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    (installer_path.parent / "release-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    release_manifest = {
        "channels": {
            "stable": {
                "version": version,
                "asset_url": (
                    "https://github.com/informigados/finora/releases/download/"
                    f"v{version}/{installer_path.name}"
                ),
                "sha256": installer_hash,
                "publisher": "INformigados",
                "notes": f"Finora {version} - canal estável para Windows.",
                "requires_migration": True,
            }
        }
    }
    (installer_path.parent / "manifest.json").write_text(
        json.dumps(release_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
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

        # Rebuild the Windows icon from the checked-in Finora branding source.
        run_command([sys.executable, "scripts/generate_windows_icon.py"])

        # Ensure translation binaries are always up to date for release.
        run_command([sys.executable, "-m", "babel.messages.frontend", "compile", "-d", "translations"])

        # Build deterministic executable from spec (includes icon + assets).
        run_command([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "Finora.spec"])

        if not DIST_EXE.exists():
            raise RuntimeError(f"Executable not generated: {DIST_EXE}")

        executable_signed = sign_file(DIST_EXE)

        if not INNO_SCRIPT.exists():
            raise RuntimeError(f"Inno script not found: {INNO_SCRIPT}")

        # Inject release version at compile time.
        run_command([str(iscc), f"/DMyAppVersion={version}", str(INNO_SCRIPT)])

        setup_file = ROOT / "dist_setup" / f"Finora_Setup_v{version}.exe"
        if not setup_file.exists():
            raise RuntimeError(f"Installer not generated: {setup_file}")

        installer_signed = sign_file(setup_file)
        write_release_metadata(version, setup_file, executable_signed and installer_signed)

        print("=" * 60)
        print("[SUCCESS] Build and installer generated.")
        print(f"Executable: {DIST_EXE}")
        print(f"Installer : {setup_file}")
        print(f"Checksums : {setup_file.parent / 'SHA256SUMS.txt'}")
        print(f"Manifest  : {setup_file.parent / 'manifest.json'}")
        print("=" * 60)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
