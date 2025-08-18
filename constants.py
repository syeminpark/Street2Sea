from enum import Enum, auto
from dataclasses import dataclass

class PerspectiveMode(Enum):
    BUILDING    = "building"
    SURROUNDING = "360°"

class TEJapanDirectory(Enum):
    DIRECTORY= "TEJapan_15S_FloodData"

class TEJapanFileType(Enum):
    DEPTH = "FLDDPH"
    FRACTION = "FLDFRC"

class WebDirectory(Enum):
    PORT = "8000"
    HOST="localhost"
    CAMERA_METADATA_ROUTE= "/api/coords"

    from dataclasses import dataclass

@dataclass(frozen=True)
class Fonts:
    base_pt: int = 20
    title_mult: float = 1.6
    subtitle_mult: float = 0.8

    @property
    def title_pt(self) -> int:
        return round(self.base_pt * self.title_mult)

    @property
    def subtitle_pt(self) -> int:
        return round(self.base_pt * self.subtitle_mult)

FONTS = Fonts()


@dataclass(frozen=True)
class FontStacks:
    # Latin-first, then Japanese; Qt will fall back per missing glyph.
    ui = (
        "Inter",            # bundled (recommended) or system-installed
        "Noto Sans JP",     # bundled (recommended) or system-installed
        "Yu Gothic UI",     # Windows JP
        "Hiragino Sans",    # macOS JP (aka Hiragino Kaku Gothic)
        "Meiryo",           # Windows JP (older)
        "Segoe UI", "Arial", "sans-serif"
    )
    mono = (
        "JetBrains Mono", "Cascadia Mono", "Consolas",
        "SF Mono", "Menlo", "Liberation Mono", "monospace"
    )

FONT_STACKS = FontStacks()

def to_css_stack(stack: tuple) -> str:
    # produce a QSS-safe, comma-separated family list
    return ", ".join(f'"{s}"' if " " in s else s for s in stack)

@dataclass(frozen=True)
class Palette:
    bg: str = "#0f1115"
    surface: str = "#161a22"
    surface_alt: str = "#1b2230"
    border: str = "#2a2f3a"
    text: str = "#e7ebf0"
    text_muted: str = "#a8b3c4"
    accent: str = "#2ecc71"
    accent_hover: str = "#39d98a"
    accent_pressed: str = "#27ae60"

PALETTE = Palette()