"""Generate the multiresolution Windows icon used by PyInstaller and Inno Setup."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "favicon.ico"
SOURCE = ROOT / "icons" / "finora-icone-fundo-azul.png"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Branding source not found: {SOURCE}")
    master = Image.open(SOURCE).convert("RGBA")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    master.save(OUTPUT, format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    print(f"Generated {OUTPUT} with sizes: {', '.join(map(str, ICON_SIZES))}")


if __name__ == "__main__":
    main()
