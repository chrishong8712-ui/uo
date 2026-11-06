"""Builds the complete Razor price script from code-defined data.

The layout (container coordinates and item labels) mirrors the Razor script
structure that the in-game macro expects. Prices are always supplied by the
caller; a missing or unexpected price raises instead of falling back silently.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from core.rare_cloth import RARE_CLOTH_ALIAS, rare_cloth_variable


class ScriptGenerationError(ValueError):
    pass


@dataclass(frozen=True)
class Placement:
    label: str
    x: int
    y: int
    variable: str


@dataclass(frozen=True)
class Loop:
    alias: str
    placements: tuple[Placement, ...]


@dataclass(frozen=True)
class Section:
    title: str
    container: str
    container_prompt: str
    loops: tuple[Loop, ...]
    show_processing_title: bool = True


HEADER_LINES = (
    "//Script created by mustang1x1",
    "//In order to prevent overlapping items, separate containers for cores/scrolls/extracts etc. are recommended",
    "//Item placement is designed for small paragon chests, items in other containers might overlap which each other",
    "",
    "//If you want to add other items to this script ",
    "//keep in mind that some items like tmaps, skillscrolls, etc. have the same ID and hue",
    "",
    "overhead 'Loading prices, please wait...' 2263",
    "",
    "//=========================================",
    "//Change this parameter value to 0 if you don't want to set target containers every time",
    "setvar! setContainerVariables '1'",
    "",
    "//=========================================",
    "//Set your prices here:",
    "",
)

SEPARATOR = "//========================================="
FOOTER_LINE = "overhead 'Script Finished' 2263"

TREASURE_MAPS = Section(
    title="Treasure Maps",
    container="mapsContainer",
    container_prompt="Set container for Treasure Maps",
    loops=(
        Loop(
            "map",
            (
                Placement("plainly drawn", 30, 60, "T1Price"),
                Placement("expertly drawn", 45, 60, "T2Price"),
                Placement("adeptly drawn", 60, 60, "T3Price"),
                Placement("cleverly drawn", 75, 60, "T4Price"),
                Placement("deviously drawn", 90, 60, "T5Price"),
                Placement("ingeniously drawn", 105, 60, "T6Price"),
                Placement("legendarily drawn", 120, 60, "T8Price"),
            ),
        ),
    ),
)

RESOURCE_MAPS = Section(
    title="Resource Maps",
    container="resourceMapsContainer",
    container_prompt="Set container for Resource Maps",
    loops=(
        Loop(
            "ore map",
            (
                Placement("dull copper", 20, 60, "DullCopperOreMapPrice"),
                Placement("shadow iron", 35, 60, "ShadowIronOreMapPrice"),
                Placement("copper", 50, 60, "CopperOreMapPrice"),
                Placement("bronze", 65, 60, "BronzeOreMapPrice"),
                Placement("gold", 80, 60, "GoldOreMapPrice"),
                Placement("agapite", 95, 60, "AgapiteOreMapPrice"),
                Placement("verite", 110, 60, "VeriteOreMapPrice"),
                Placement("valorite", 125, 60, "ValoriteOreMapPrice"),
                Placement("avarite", 140, 60, "AvariteOreMapPrice"),
            ),
        ),
        Loop(
            "lumber map",
            (
                Placement("dullwood", 20, 85, "DullwoodLumberMapPrice"),
                Placement("shadowwood", 35, 85, "ShadowwoodLumberMapPrice"),
                Placement("copperwood", 50, 85, "CopperwoodLumberMapPrice"),
                Placement("bronzewood", 65, 85, "BronzewoodLumberMapPrice"),
                Placement("goldenwood", 80, 85, "GoldenwoodLumberMapPrice"),
                Placement("rosewood", 95, 85, "RosewoodLumberMapPrice"),
                Placement("verewood", 110, 85, "VerewoodLumberMapPrice"),
                Placement("valewood", 125, 85, "ValewoodLumberMapPrice"),
                Placement("avarwood", 140, 85, "AvarwoodLumberMapPrice"),
            ),
        ),
        Loop(
            "fishing map",
            (
                Placement("dullscale", 20, 110, "DullscaleFishingMapPrice"),
                Placement("shadowscale", 35, 110, "ShadowscaleFishingMapPrice"),
                Placement("copperscale", 50, 110, "CopperscaleFishingMapPrice"),
                Placement("bronzescale", 65, 110, "BronzescaleFishingMapPrice"),
                Placement("goldenscale", 80, 110, "GoldenscaleFishingMapPrice"),
                Placement("rosescale", 95, 110, "RosescaleFishingMapPrice"),
                Placement("verescale", 110, 110, "VerescaleFishingMapPrice"),
                Placement("valescale", 125, 110, "ValescaleFishingMapPrice"),
                Placement("avarscale", 140, 110, "AvarscaleFishingMapPrice"),
            ),
        ),
        Loop(
            "skinning map",
            (
                Placement("dullhide", 20, 135, "DullhideSkinningMapPrice"),
                Placement("shadowhide", 35, 135, "ShadowhideSkinningMapPrice"),
                Placement("copperhide", 50, 135, "CopperhideSkinningMapPrice"),
                Placement("bronzehide", 65, 135, "BronzehideSkinningMapPrice"),
                Placement("goldenhide", 80, 135, "GoldenhideSkinningMapPrice"),
                Placement("rosehide", 95, 135, "RosehideSkinningMapPrice"),
                Placement("verehide", 110, 135, "VerehideSkinningMapPrice"),
                Placement("valehide", 125, 135, "ValehideSkinningMapPrice"),
                Placement("avarhide", 140, 135, "AvarhideSkinningMapPrice"),
            ),
        ),
    ),
)

CORES = Section(
    title="Cores",
    container="aspectCoreContainer",
    container_prompt="Set container for Aspect Cores",
    loops=(
        Loop(
            "aspect core",
            (
                Placement("Air", 30, 60, "AirCorePrice"),
                Placement("Artisan", 45, 60, "ArtisanCorePrice"),
                Placement("Blood", 60, 60, "BloodCorePrice"),
                Placement("Command", 75, 60, "CommandCorePrice"),
                Placement("Death", 90, 60, "DeathCorePrice"),
                Placement("Discipline", 105, 60, "DisciplineCorePrice"),
                Placement("Earth", 120, 60, "EarthCorePrice"),
                Placement("Eldritch", 135, 60, "EldritchCorePrice"),
                Placement("Fire", 30, 80, "FireCorePrice"),
                Placement("Fortune", 45, 80, "FortuneCorePrice"),
                Placement("Holy", 60, 80, "HolyCorePrice"),
                Placement("Lyric", 75, 80, "LyricCorePrice"),
                Placement("Poison", 90, 80, "PoisonCorePrice"),
                Placement("Shadow", 105, 80, "ShadowCorePrice"),
                Placement("Void", 120, 80, "VoidCorePrice"),
                Placement("Water", 135, 80, "WaterCorePrice"),
                Placement("Gadget", 30, 100, "GadgetCorePrice"),
                Placement("Harvest", 45, 100, "HarvestCorePrice"),
                Placement("War", 60, 100, "WarCorePrice"),
                Placement("Arcane", 75, 100, "ArcaneCorePrice"),
                Placement("Frost", 90, 100, "FrostCorePrice"),
                Placement("Lightning", 105, 100, "LightningCorePrice"),
                Placement("Madness", 120, 100, "MadnessCorePrice"),
                Placement("Agorawave", 30, 120, "AgorawaveCorePrice"),
                Placement("Temporal", 45, 120, "TemporalCorePrice"),
            ),
        ),
        Loop(
            "chroma core",
            (Placement("chromatic", 135, 100, "ChromaticCorePrice"),),
        ),
    ),
)

DISTILLATIONS = Section(
    title="Distillations",
    container="aspectDistillationContainer",
    container_prompt="Set container for Aspect Distillations",
    show_processing_title=False,
    loops=(
        Loop(
            "flask",
            (
                Placement("Air", 25, 50, "AirDistillationPrice"),
                Placement("Artisan", 40, 50, "ArtisanDistillationPrice"),
                Placement("Blood", 55, 50, "BloodDistillationPrice"),
                Placement("Command", 70, 50, "CommandDistillationPrice"),
                Placement("Death", 85, 50, "DeathDistillationPrice"),
                Placement("Discipline", 100, 50, "DisciplineDistillationPrice"),
                Placement("Earth", 115, 50, "EarthDistillationPrice"),
                Placement("Eldritch", 130, 50, "EldritchDistillationPrice"),
                Placement("Fire", 30, 75, "FireDistillationPrice"),
                Placement("Fortune", 45, 75, "FortuneDistillationPrice"),
                Placement("Holy", 60, 75, "HolyDistillationPrice"),
                Placement("Lyric", 75, 75, "LyricDistillationPrice"),
                Placement("Poison", 90, 75, "PoisonDistillationPrice"),
                Placement("Shadow", 105, 75, "ShadowDistillationPrice"),
                Placement("Void", 120, 75, "VoidDistillationPrice"),
                Placement("Water", 135, 75, "WaterDistillationPrice"),
                Placement("Gadget", 30, 100, "GadgetDistillationPrice"),
                Placement("Harvest", 45, 100, "HarvestDistillationPrice"),
                Placement("War", 60, 100, "WarDistillationPrice"),
                Placement("Arcane", 75, 100, "ArcaneDistillationPrice"),
                Placement("Frost", 90, 100, "FrostDistillationPrice"),
                Placement("Lightning", 105, 100, "LightningDistillationPrice"),
                Placement("Madness", 120, 100, "MadnessDistillationPrice"),
                Placement("Agorawave", 25, 125, "AgorawaveDistillationPrice"),
                Placement("Temporal", 40, 125, "TemporalDistillationPrice"),
            ),
        ),
        Loop(
            "chroma distil",
            (Placement("chromatic", 135, 100, "ChromaticDistillationPrice"),),
        ),
    ),
)

PHYLACTERIES = Section(
    title="Phylacteries",
    container="phylacteryContainer",
    container_prompt="Set container for Phylacteries",
    loops=(
        Loop(
            "phylactery",
            (
                Placement("Agorawave", 20, 50, "AgorawavePhylacteryPrice"),
                Placement("Air", 35, 50, "AirPhylacteryPrice"),
                Placement("Arcane", 50, 50, "ArcanePhylacteryPrice"),
                Placement("Artisan", 65, 50, "ArtisanPhylacteryPrice"),
                Placement("Blood", 80, 50, "BloodPhylacteryPrice"),
                Placement("Command", 95, 50, "CommandPhylacteryPrice"),
                Placement("Death", 110, 50, "DeathPhylacteryPrice"),
                Placement("Discipline", 125, 50, "DisciplinePhylacteryPrice"),
                Placement("Earth", 20, 70, "EarthPhylacteryPrice"),
                Placement("Eldritch", 35, 70, "EldritchPhylacteryPrice"),
                Placement("Fire", 50, 70, "FirePhylacteryPrice"),
                Placement("Fortune", 65, 70, "FortunePhylacteryPrice"),
                Placement("Frost", 80, 70, "FrostPhylacteryPrice"),
                Placement("Gadget", 95, 70, "GadgetPhylacteryPrice"),
                Placement("Harvest", 110, 70, "HarvestPhylacteryPrice"),
                Placement("Holy", 125, 70, "HolyPhylacteryPrice"),
                Placement("Lightning", 20, 90, "LightningPhylacteryPrice"),
                Placement("Lyric", 35, 90, "LyricPhylacteryPrice"),
                Placement("Madness", 50, 90, "MadnessPhylacteryPrice"),
                Placement("Poison", 65, 90, "PoisonPhylacteryPrice"),
                Placement("Shadow", 80, 90, "ShadowPhylacteryPrice"),
                Placement("Temporal", 95, 90, "TemporalPhylacteryPrice"),
                Placement("Void", 110, 90, "VoidPhylacteryPrice"),
                Placement("Water", 125, 90, "WaterPhylacteryPrice"),
                Placement("War", 20, 110, "WarPhylacteryPrice"),
            ),
        ),
    ),
)

RARE_ITEMS_SECTION = Section(
    title="Rare Items",
    container="rareItemsContainer",
    container_prompt="Set container for Rare Items",
    loops=(
        Loop("void orb", (Placement("skill mastery orb", 20, 50, "SkillOrbPrice"),)),
        Loop("Book of Truth", (Placement("mastercrafting diagram", 35, 50, "MastercraftingDiagramPrice"),)),
        Loop("research materials", (Placement("research materials", 50, 50, "ResearchMaterialsPrice"),)),
        Loop("blank scroll%s%", (Placement("arcane scroll", 65, 50, "ArcaneScrollPrice"),)),
    ),
)


def rare_cloth_section(hues: Sequence[int]) -> Section:
    """Section for the rare cloth kinds the user owns, one placement per hue."""
    positions = _random_positions(random.Random(f"{LAYOUT_SEED}:rareClothContainer"), len(hues))
    return Section(
        title="Rare Cloth",
        container="rareClothContainer",
        container_prompt="Set container for Rare Cloth",
        loops=(
            Loop(
                RARE_CLOTH_ALIAS,
                tuple(
                    Placement(f"hue {hue}", x, y, rare_cloth_variable(hue))
                    for hue, (x, y) in zip(hues, positions)
                ),
            ),
        ),
    )

SKILL_SCROLLS = Section(
    title="Skill Scrolls",
    container="skillScrollsContainer",
    container_prompt="Set container for Skill Scrolls",
    loops=(
        Loop(
            "scroll of calling",
            (
                Placement("alchemy", 15, 50, "AlchemyPrice"),
                Placement("animal lore", 25, 50, "AnimalLorePrice"),
                Placement("animal taming", 35, 50, "AnimalTamingPrice"),
                Placement("arms lore", 45, 50, "ArmsLorePrice"),
                Placement("begging", 55, 50, "BeggingPrice"),
                Placement("blacksmithy", 65, 50, "BlacksmithyPrice"),
                Placement("camping", 75, 50, "CampingPrice"),
                Placement("carpentry", 85, 50, "CarpentryPrice"),
                Placement("cartography", 95, 50, "CartographyPrice"),
                Placement("chivalry", 105, 50, "ChivalryPrice"),
                Placement("cooking", 115, 50, "CookingPrice"),
                Placement("detect hidden", 125, 50, "DetectHiddenPrice"),
                Placement("discordance", 135, 50, "DiscordancePrice"),
                Placement("fishing", 20, 70, "FishingPrice"),
                Placement("forensic eval", 30, 70, "ForensicEvalPrice"),
                Placement("herding", 40, 70, "HerdingPrice"),
                Placement("inscription", 50, 70, "InscriptionPrice"),
                Placement("item id", 60, 70, "ItemIdPrice"),
                Placement("lockpicking", 70, 70, "LockpickingPrice"),
                Placement("lumberjacking", 80, 70, "LumberjackingPrice"),
                Placement("musicianship", 90, 70, "MusicanshipPrice"),
                Placement("mining", 100, 70, "MiningPrice"),
                Placement("necromancy", 110, 70, "NecromancyPrice"),
                Placement("peacemaking", 120, 70, "PeacemakingPrice"),
                Placement("poisoning", 130, 70, "PoisoningPrice"),
                Placement("provocation", 15, 90, "ProvocationPrice"),
                Placement("remove trap", 25, 90, "RemoveTrapPrice"),
                Placement("spirit speak", 35, 90, "SpiritSpeakPrice"),
                Placement("stealth", 45, 90, "StealthPrice"),
                Placement("tailoring", 55, 90, "TailoringPrice"),
                Placement("taste id", 65, 90, "TasteIdPrice"),
                Placement("tinkering", 75, 90, "TinkeringPrice"),
                Placement("tracking", 85, 90, "TrackingPrice"),
                Placement("veterinary", 95, 90, "VeterinaryPrice"),
            ),
        ),
    ),
)

LAYOUT_SEED = 20240601
COORD_MIN = 0
COORD_MAX = 60
MIN_SPACING = 5


def _random_positions(rng: random.Random, count: int) -> list[tuple[int, int]]:
    """Random integer positions where any two are at least MIN_SPACING apart (Chebyshev).

    Overlap between neighbours is avoided only down to MIN_SPACING; the first N
    positions do not depend on N, so a container with more items extends the list.
    """
    positions: list[tuple[int, int]] = []
    attempts = 0
    while len(positions) < count:
        attempts += 1
        if attempts > 100_000:
            raise ScriptGenerationError(f"Could not place {count} items with spacing {MIN_SPACING}.")
        x = rng.randint(COORD_MIN, COORD_MAX)
        y = rng.randint(COORD_MIN, COORD_MAX)
        if all(max(abs(x - px), abs(y - py)) >= MIN_SPACING for px, py in positions):
            positions.append((x, y))
    return positions


def _randomized(section: Section) -> Section:
    """Replaces the design-grid x/y of every placement with seeded random positions."""
    placements_count = sum(len(loop.placements) for loop in section.loops)
    positions = _random_positions(random.Random(f"{LAYOUT_SEED}:{section.container}"), placements_count)
    index = 0
    loops = []
    for loop in section.loops:
        placed = []
        for placement in loop.placements:
            x, y = positions[index]
            index += 1
            placed.append(replace(placement, x=x, y=y))
        loops.append(Loop(loop.alias, tuple(placed)))
    return replace(section, loops=tuple(loops))


# The x/y values in the section tables above are only a design grid; these
# assignments replace them with the seeded random layout before ordering.
TREASURE_MAPS = _randomized(TREASURE_MAPS)
RESOURCE_MAPS = _randomized(RESOURCE_MAPS)
CORES = _randomized(CORES)
DISTILLATIONS = _randomized(DISTILLATIONS)
PHYLACTERIES = _randomized(PHYLACTERIES)
SKILL_SCROLLS = _randomized(SKILL_SCROLLS)
RARE_ITEMS_SECTION = _randomized(RARE_ITEMS_SECTION)

# Declaration order in the generated file (matches the reference layout).
DECLARATION_SECTIONS = (TREASURE_MAPS, RESOURCE_MAPS, CORES, DISTILLATIONS, PHYLACTERIES, SKILL_SCROLLS, RARE_ITEMS_SECTION)
# Processing order in the generated file.
PROCESSING_SECTIONS = (CORES, DISTILLATIONS, PHYLACTERIES, SKILL_SCROLLS, RARE_ITEMS_SECTION, TREASURE_MAPS, RESOURCE_MAPS)


def _with_rare_cloth(sections: tuple[Section, ...], cloth: Section | None) -> tuple[Section, ...]:
    if cloth is None:
        return sections
    index = sections.index(SKILL_SCROLLS)
    return sections[:index] + (cloth,) + sections[index:]


def price_variables(rare_cloth_hues: Sequence[int] = ()) -> list[str]:
    """Every variable the caller must price, in declaration order."""
    cloth = rare_cloth_section(rare_cloth_hues) if rare_cloth_hues else None
    return [
        placement.variable
        for section in _with_rare_cloth(DECLARATION_SECTIONS, cloth)
        for loop in section.loops
        for placement in loop.placements
    ]


def generate_script(prices: Mapping[str, int], rare_cloth_hues: Sequence[int] = ()) -> str:
    if len(set(rare_cloth_hues)) != len(rare_cloth_hues):
        raise ScriptGenerationError("Duplicate rare cloth hues.")
    cloth = rare_cloth_section(rare_cloth_hues) if rare_cloth_hues else None
    declaration_sections = _with_rare_cloth(DECLARATION_SECTIONS, cloth)
    processing_sections = _with_rare_cloth(PROCESSING_SECTIONS, cloth)
    expected = price_variables(rare_cloth_hues)
    expected_set = set(expected)
    missing = sorted(expected_set - prices.keys())
    extra = sorted(prices.keys() - expected_set)
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("unexpected: " + ", ".join(extra))
        raise ScriptGenerationError("Price values do not match the layout (" + "; ".join(details) + ").")
    for name in expected:
        value = prices[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ScriptGenerationError(f"Invalid price for {name}: {value!r}")

    lines: list[str] = list(HEADER_LINES)
    for section in declaration_sections:
        lines.append(f"//{section.title}")
        for loop in section.loops:
            for placement in loop.placements:
                lines.append(f"setvar! {placement.variable} '{prices[placement.variable]}'")
        lines.append("")
    lines.append(SEPARATOR)
    lines.append("")

    for section in processing_sections:
        if section.show_processing_title:
            lines.append(f"//{section.title}")
        lines += [
            "if setContainerVariables == '1'",
            f"overhead '{section.container_prompt}' 2263",
            f"setvar {section.container}",
            "endif",
            "",
        ]
        for loop in section.loops:
            lines.append(f"while findtype '{loop.alias}' backpack as item")
            lines.append("    getlabel item label")
            for index, placement in enumerate(loop.placements):
                keyword = "if" if index == 0 else "elseif"
                lines.append(f"    {keyword} '{placement.label}' in label")
                lines.append("        lift item 1")
                lines.append(f"        drop {section.container} {placement.x} {placement.y} 0")
                lines.append("        pause 500")
                lines.append(f"        promptresponse {placement.variable}")
            lines.append("    endif")
            lines.append("endwhile")
            lines.append("")

    lines.append(FOOTER_LINE)
    return "\n".join(lines) + "\n"
