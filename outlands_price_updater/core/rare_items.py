"""Rare items: single Vendor Search entries that are not scroll or map families.

Each entry keeps the Vendor Search term (what is typed and matched on the site)
separate from the Razor item type (what the in-game macro looks up). Do not
merge these: for example, the Skill Mastery Scroll is a scroll-category item
whose Razor type is "scroll of calling", while the Skill Mastery Orb is a
separate rare item whose Razor type is "void orb".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RareItem:
    variable: str
    search: str
    match: str
    razor_type: str


RARE_ITEMS: dict[str, RareItem] = {
    item.variable: item
    for item in (
        RareItem(
            variable="SkillOrbPrice",
            search="skill mastery orb",
            match="skill mastery orb",
            razor_type="void orb",
        ),
        RareItem(
            variable="MastercraftingDiagramPrice",
            search="mastercrafting diagram",
            match="mastercrafting diagram",
            razor_type="Book of Truth",
        ),
        RareItem(
            variable="ResearchMaterialsPrice",
            search="research materials",
            match="research materials",
            razor_type="research materials",
        ),
        RareItem(
            variable="ArcaneScrollPrice",
            search="an arcane scroll",
            match="an arcane scroll",
            razor_type="blank scroll%s%",
        ),
    )
}


def rare_item_for_variable(variable: str) -> RareItem | None:
    return RARE_ITEMS.get(variable)
