"""Rare cloth (type 'folded cloth') is identified by the hue number in 'rare cloth (hue N: name)'.

Only the kinds the user owns are handled, so no kind list is kept here.
"""

from __future__ import annotations

import re

RARE_CLOTH_ALIAS = "folded cloth"
RARE_CLOTH_VARIABLE = re.compile(r"RareCloth(\d+)Price")


def rare_cloth_variable(hue: int) -> str:
    return f"RareCloth{hue}Price"


def hue_from_variable(variable: str) -> int | None:
    found = RARE_CLOTH_VARIABLE.fullmatch(variable)
    return int(found.group(1)) if found else None
