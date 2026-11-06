"""Reads the owned-item list from the in-game Razor system messages.

The pure parts (text -> owned variables) take plain strings so they can be
tested without Tesseract or a game window. The OCR engine is passed in as a
callable; the default uses pytesseract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import threading

from core.razor_generator import DECLARATION_SECTIONS, price_variables
from core.search_catalog import default_search_spec


TESSERACT_ENV_VAR = "TESSERACT_CMD"
DEFAULT_TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

OcrEngine = Callable[[object], str]
LIVE_CAPTURE_INTERVAL_S = 0.4
TESSERACT_SCALE = 3
GREEN_MARGIN = 60
# Fixed system message area (x, y, width, height) matching the user's game window.
INVENTORY_REGION = (0, 300, 410, 720)
TIMESTAMP_HEADER = re.compile(r"^\W*\d{1,2}:\d{2}\W*(?:\|+\s*)?(.*)$")
RAZOR_TAG = re.compile(r"^\W*[Rr][ea]z\w{1,3}\W*", re.IGNORECASE)
RAZOR_DONE = re.compile(r"^label\W*dump\W*done", re.IGNORECASE)
RAZOR_CONTROL = re.compile(
    r"\bi[gq]n\w*|\badded\b|\bcleared\b|^label\W*dump|\bselect target\b|\bvariable\b|\bscript\b",
    re.IGNORECASE,
)
ITEM_NAME_END = re.compile(
    r"[(\[{]|\bused\b|\bfused\b|\bin\w*ease\b|\bplayer\w*|\bskill cap\b",
    re.IGNORECASE,
)


@dataclass
class InventoryMatch:
    owned: list[str] = field(default_factory=list)
    matched_lines: dict[str, str] = field(default_factory=dict)
    unmapped: list[str] = field(default_factory=list)
    ambiguous: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    rare_cloth: dict[int, str] = field(default_factory=dict)


def _label_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for section in DECLARATION_SECTIONS:
        for loop in section.loops:
            for placement in loop.placements:
                index.setdefault(placement.label.lower(), set()).add(placement.variable)
    for variable in price_variables():
        try:
            full_name = default_search_spec(variable).match
        except ValueError:
            continue
        index.setdefault(full_name.lower(), set()).add(variable)
    return index


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lower()


def _spaced_label_pattern(label: str) -> str:
    """Whole-word pattern that tolerates OCR inserting spaces inside a label.

    'Lumberjacking' also matches 'lumber jacking', which OCR often produces.
    """
    body = r"\s*".join(re.escape(char) for char in label.lower())
    return rf"(?<!\w){body}(?!\w)"


def razor_messages(text: str) -> list[str]:
    """Returns the body of each [Razor]: system message in OCR text.

    A timestamped line starts a message. Following lines without a timestamp
    belong to that message until the next timestamped line. Messages from other
    sources are dropped, so non-Razor system output in the same region is ignored.
    """
    bodies: list[list[str]] = []
    current: list[str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header = TIMESTAMP_HEADER.match(line)
        content = header.group(1) if header else line
        tag = RAZOR_TAG.match(content)

        if header or tag:
            current = None
            if tag:
                current = [content[tag.end():].strip()]
                bodies.append(current)
        elif current is not None and not _message_complete(current):
            current.append(line)
    return [" ".join(part for part in body if part) for body in bodies]


def _message_complete(body: list[str]) -> bool:
    """True when following untagged lines must not join this message.

    Control messages (script status) are single lines. Item messages end with the
    closing ')' of the script's '(used ...)' text.
    """
    text = " ".join(body)
    return bool(RAZOR_CONTROL.search(text)) or bool(re.search(r"[)\]|]\s*$", text))


def item_name(body: str) -> str | None:
    """Returns the item name from a Razor message body, or None for script output.

    The name is the text before the description, which the script prints in
    parentheses. OCR often reads '(' as '[', so both are cut.
    """
    if RAZOR_CONTROL.search(body):
        return None
    cloth = RARE_CLOTH_LINE.match(body)
    if cloth:
        return re.sub(r"\s+", " ", cloth.group(0)).strip()
    end = ITEM_NAME_END.search(body)
    name = re.sub(r"\s+", " ", body[: end.start()] if end else body).strip(" .,;:|-")
    name = re.sub(r"^(?:[^A-Za-z]+\s)+", "", name)
    return name if len(name) >= 3 else None


def _narrow_by_item_type(variables: list[str], normalized: str) -> list[str]:
    """Keeps only variables whose item type word ('core'/'distillation') is in the line."""
    kept = [
        v for v in variables
        if (v.endswith("CorePrice") and re.search(r"\bcore\b", normalized))
        or (v.endswith("DistillationPrice") and re.search(r"\bdistillation\b", normalized))
    ]
    return kept or variables


def _compact(name: str) -> str:
    return re.sub(r"[\s\-]+", "", name.lower())


RARE_CLOTH_LINE = re.compile(r"^\W*rare\s*cloth\s*[(\[{]([^)\]}]*)[)\]}]?", re.IGNORECASE)
RARE_CLOTH_HUE = re.compile(r"^\s*hue\s*(\d{3,5})\s*[:;]", re.IGNORECASE)


def rare_cloth_hue(line: str) -> int | None | bool:
    """Reads the hue number from a 'rare cloth (hue N: name)' line.

    Returns the hue, None if the line starts like rare cloth but has no readable
    hue number, or False if it is not a rare cloth line. The name is only
    informational; the hue number identifies the kind.
    """
    found = RARE_CLOTH_LINE.match(line)
    if not found:
        return False
    hue = RARE_CLOTH_HUE.match(found.group(1))
    return int(hue.group(1)) if hue else None


def match_inventory_text(text: str) -> InventoryMatch:
    """Maps OCR lines to price variables.

    Each line is matched against Razor placement labels (whole words, longest
    label wins). Lines that match no label are listed as unmapped. Lines whose
    best label belongs to more than one variable are listed as ambiguous and
    are not searched. Rare cloth lines are identified by the hue number in the
    parentheses and returned in rare_cloth. Nothing is defaulted silently.
    """
    index = _label_index()
    order = {name: position for position, name in enumerate(price_variables())}
    result = InventoryMatch()
    seen_lines: set[str] = set()
    owned: dict[str, str] = {}

    for raw_line in text.splitlines():
        normalized = _normalize(raw_line)
        if len(normalized) < 2 or normalized in seen_lines:
            continue
        seen_lines.add(normalized)

        cloth = rare_cloth_hue(normalized)
        if cloth is not False:
            if cloth is None:
                result.unmapped.append(raw_line.strip())
            else:
                result.rare_cloth.setdefault(cloth, raw_line.strip())
            continue

        hits = [
            label
            for label in index
            if re.search(_spaced_label_pattern(label), normalized)
        ]
        if not hits:
            result.unmapped.append(raw_line.strip())
            continue

        longest = max(len(label) for label in hits)
        best = [label for label in hits if len(label) == longest]
        variables = sorted({v for label in best for v in index[label]}, key=order.get)
        if len(variables) > 1:
            variables = _narrow_by_item_type(variables, normalized)
        if len(variables) > 1:
            result.ambiguous.append((raw_line.strip(), tuple(variables)))
            continue
        variable = variables[0]
        if variable not in owned:
            owned[variable] = raw_line.strip()

    result.owned = sorted(owned, key=order.get)
    result.matched_lines = {name: owned[name] for name in result.owned}
    return result


def parse_region(text: str) -> tuple[int, int, int, int]:
    """Parses 'x,y,width,height' into a screen bounding box."""
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4 or not all(part.lstrip("-").isdigit() for part in parts):
        raise ValueError("Region must be four integers: x,y,width,height")
    x, y, width, height = (int(part) for part in parts)
    if width <= 0 or height <= 0:
        raise ValueError("Region width and height must be positive.")
    return x, y, width, height


def load_image(path: Path):
    from PIL import Image

    if not path.is_file():
        raise FileNotFoundError(f"Inventory image does not exist: {path}")
    return Image.open(path)


def capture_region(region: tuple[int, int, int, int]):
    from PIL import ImageGrab

    x, y, width, height = region
    return ImageGrab.grab(bbox=(x, y, x + width, y + height))


def _configure_tesseract() -> None:
    import pytesseract

    configured = os.environ.get(TESSERACT_ENV_VAR)
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured
    elif DEFAULT_TESSERACT_PATH.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(DEFAULT_TESSERACT_PATH)


def green_text_mask(image):
    """Keeps only green game text (the [Razor] messages) as black on white.

    Green is detected as G exceeding both R and B by a margin. Yellow and other
    system message colors have R close to G, so they are removed.
    """
    from PIL import Image, ImageChops

    red, green, blue = image.convert("RGB").split()
    greenness = ImageChops.subtract(green, ImageChops.lighter(red, blue))
    return greenness.point(lambda value: 0 if value > GREEN_MARGIN else 255).convert("L")


def tesseract_engine(image) -> str:
    import pytesseract
    from PIL import Image

    _configure_tesseract()
    gray = green_text_mask(image)
    enlarged = gray.resize(
        (gray.width * TESSERACT_SCALE, gray.height * TESSERACT_SCALE), Image.LANCZOS
    )
    return pytesseract.image_to_string(enlarged)


def ocr_image(image, engine: OcrEngine | None = None) -> str:
    return (engine or tesseract_engine)(image)


class InventoryAccumulator:
    """Collects unique owned-item names across repeated captures.

    Only Razor-tagged system messages are used. Each frame is parsed on its own
    and names are de-duplicated across frames, so scrolled overlap is harmless.
    """

    def __init__(self) -> None:
        self._names: list[str] = []
        self._seen: set[str] = set()
        self._finished = False

    @property
    def finished(self) -> bool:
        """True once the script's 'Label dump done.' message has been seen."""
        return self._finished

    def add_text(self, text: str) -> list[str]:
        """Adds new item names from one frame and returns only the new ones."""
        new_names: list[str] = []
        for body in razor_messages(text):
            if RAZOR_DONE.search(body):
                self._finished = True
                continue
            name = item_name(body)
            if name is None:
                continue
            key = _normalize(name)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._names.append(name)
            new_names.append(name)
        return new_names

    def text(self) -> str:
        return "\n".join(self._names)

    def match(self) -> InventoryMatch:
        return match_inventory_text(self.text())


def watch_region(
    region: tuple[int, int, int, int],
    accumulator: InventoryAccumulator,
    stop_event: threading.Event,
    on_new_lines: Callable[[list[str]], None] | None = None,
    interval_s: float = LIVE_CAPTURE_INTERVAL_S,
    capture: Callable[[tuple[int, int, int, int]], object] = capture_region,
    engine: OcrEngine | None = None,
) -> int:
    """Captures and OCRs the region repeatedly until stop_event is set.

    Runs on a fixed local interval (no site requests). Returns the number of
    captures taken.
    """
    captures = 0
    while not stop_event.is_set():
        image = capture(region)
        new_lines = accumulator.add_text(ocr_image(image, engine))
        captures += 1
        if new_lines and on_new_lines:
            on_new_lines(new_lines)
        if accumulator.finished:
            break
        stop_event.wait(interval_s)
    return captures
