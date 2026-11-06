import json
from dataclasses import dataclass
from pathlib import Path
import re

from core.rare_cloth import hue_from_variable
from core.rare_items import rare_item_for_variable


@dataclass(frozen=True)
class SearchSpec:
    search: str
    match: str
    exact_match: bool = False


@dataclass(frozen=True)
class ResourceMapSpec:
    variable_stem: str
    item_type: str
    search: str
    label_match: str


RESOURCE_MAP_FAMILIES = {
    "OreMap": (
        "ore map",
        (
            ("DullCopper", "dull copper ore map", "dull copper"),
            ("ShadowIron", "shadow iron ore map", "shadow iron"),
            ("Copper", "copper ore map", "copper"),
            ("Bronze", "bronze ore map", "bronze"),
            ("Gold", "gold ore map", "gold"),
            ("Agapite", "agapite ore map", "agapite"),
            ("Verite", "verite ore map", "verite"),
            ("Valorite", "valorite ore map", "valorite"),
            ("Avarite", "avarite ore map", "avarite"),
        ),
    ),
    "LumberMap": (
        "lumber map",
        (
            ("Dullwood", "dullwood lumber map", "dullwood"),
            ("Shadowwood", "shadowwood lumber map", "shadowwood"),
            ("Copperwood", "copperwood lumber map", "copperwood"),
            ("Bronzewood", "bronzewood lumber map", "bronzewood"),
            ("Goldenwood", "goldenwood lumber map", "goldenwood"),
            ("Rosewood", "rosewood lumber map", "rosewood"),
            ("Verewood", "verewood lumber map", "verewood"),
            ("Valewood", "valewood lumber map", "valewood"),
            ("Avarwood", "avarwood lumber map", "avarwood"),
        ),
    ),
    "FishingMap": (
        "fishing map",
        (
            ("Dullscale", "dullscale fishing map", "dullscale"),
            ("Shadowscale", "shadowscale fishing map", "shadowscale"),
            ("Copperscale", "copperscale fishing map", "copperscale"),
            ("Bronzescale", "bronzescale fishing map", "bronzescale"),
            ("Goldenscale", "goldenscale fishing map", "goldenscale"),
            ("Rosescale", "rosescale fishing map", "rosescale"),
            ("Verescale", "verescale fishing map", "verescale"),
            ("Valescale", "valescale fishing map", "valescale"),
            ("Avarscale", "avarscale fishing map", "avarscale"),
        ),
    ),
    "SkinningMap": (
        "skinning map",
        (
            ("Dullhide", "dullhide skinning map", "dullhide"),
            ("Shadowhide", "shadowhide skinning map", "shadowhide"),
            ("Copperhide", "copperhide skinning map", "copperhide"),
            ("Bronzehide", "bronzehide skinning map", "bronzehide"),
            ("Goldenhide", "goldenhide skinning map", "goldenhide"),
            ("Rosehide", "rosehide skinning map", "rosehide"),
            ("Verehide", "verehide skinning map", "verehide"),
            ("Valehide", "valehide skinning map", "valehide"),
            ("Avarhide", "avarhide skinning map", "avarhide"),
        ),
    ),
}

RESOURCE_MAPS = tuple(
    ResourceMapSpec(
        variable_stem=f"{material}{family_stem}",
        item_type=item_type,
        search=search,
        label_match=label_match,
    )
    for family_stem, (item_type, entries) in RESOURCE_MAP_FAMILIES.items()
    for material, search, label_match in entries
)
RESOURCE_MAPS_BY_VARIABLE = {
    f"{spec.variable_stem}Price": spec for spec in RESOURCE_MAPS
}

TREASURE_MAPS = {
    "T1": (
        "level 1 treasure map",
        "plainly drawn treasure map (level 1)",
        "plainly drawn",
    ),
    "T2": (
        "level 2 treasure map",
        "expertly drawn treasure map (level 2)",
        "expertly drawn",
    ),
    "T3": (
        "level 3 treasure map",
        "adeptly drawn treasure map (level 3)",
        "adeptly drawn",
    ),
    "T4": (
        "level 4 treasure map",
        "cleverly drawn treasure map (level 4)",
        "cleverly drawn",
    ),
    "T5": (
        "level 5 treasure map",
        "deviously drawn treasure map (level 5)",
        "deviously drawn",
    ),
    "T6": (
        "level 6 treasure map",
        "ingeniously drawn treasure map (level 6)",
        "ingeniously drawn",
    ),
    "T8": (
        "level 8 treasure map",
        "legendarily drawn treasure map (level 8)",
        "legendarily drawn",
    ),
}


ASPECTS = (
    "Agorawave",
    "Air",
    "Arcane",
    "Artisan",
    "Blood",
    "Command",
    "Chromatic",
    "Death",
    "Discipline",
    "Earth",
    "Eldritch",
    "Fire",
    "Fortune",
    "Frost",
    "Gadget",
    "Harvest",
    "Holy",
    "Lightning",
    "Lyric",
    "Madness",
    "Poison",
    "Shadow",
    "Temporal",
    "Void",
    "Water",
    "War",
)

SKILLS = {
    "Alchemy": "alchemy",
    "AnimalLore": "animal lore",
    "AnimalTaming": "animal taming",
    "ArmsLore": "arms lore",
    "Begging": "begging",
    "Blacksmithy": "blacksmithy",
    "Camping": "camping",
    "Carpentry": "carpentry",
    "Cartography": "cartography",
    "Chivalry": "chivalry",
    "Cooking": "cooking",
    "DetectHidden": "detect hidden",
    "Discordance": "discordance",
    "Fishing": "fishing",
    "ForensicEval": "forensic evaluation",
    "Herding": "herding",
    "Inscription": "inscription",
    "ItemId": "item identification",
    "Lockpicking": "lockpicking",
    "Lumberjacking": "lumberjacking",
    "Musicanship": "musicianship",
    "Mining": "mining",
    "Necromancy": "necromancy",
    "Peacemaking": "peacemaking",
    "Poisoning": "poisoning",
    "Provocation": "provocation",
    "RemoveTrap": "remove trap",
    "SpiritSpeak": "spirit speak",
    "Stealth": "stealth",
    "Tailoring": "tailoring",
    "TasteId": "taste identification",
    "Tinkering": "tinkering",
    "Tracking": "tracking",
    "Veterinary": "veterinary",
}

SPECIALS = {
    "MastercraftingDiagramPrice": SearchSpec(
        "mastercrafting diagram", "mastercrafting diagram"
    ),
    "ResearchMaterialsPrice": SearchSpec(
        "research materials", "research materials"
    ),
}

IGNORED_VARIABLES: set[str] = set()


def default_search_spec(variable_name: str) -> SearchSpec:
    if not variable_name.endswith("Price"):
        raise ValueError(f"Not a price variable: {variable_name}")
    stem = variable_name[:-len("Price")]

    rare_item = rare_item_for_variable(variable_name)
    if rare_item is not None:
        return SearchSpec(rare_item.search, rare_item.match)
    if variable_name in SPECIALS:
        return SPECIALS[variable_name]
    if variable_name in RESOURCE_MAPS_BY_VARIABLE:
        item = RESOURCE_MAPS_BY_VARIABLE[variable_name].search
        return SearchSpec(
            item,
            item,
            exact_match=variable_name == "CopperOreMapPrice",
        )
    cloth_hue = hue_from_variable(variable_name)
    if cloth_hue is not None:
        return SearchSpec(f"rare cloth {cloth_hue}", f"rare cloth (hue {cloth_hue}:")
    if stem == "ChromaticCore":
        return SearchSpec("chromatic core", "chromatic core")
    if stem == "ChromaticDistillation":
        return SearchSpec("chromatic distillation", "chromatic distillation")
    if stem.endswith("Core") and stem[:-len("Core")] in ASPECTS:
        aspect = stem[:-len("Core")].lower()
        item = f"{aspect} aspect core"
        return SearchSpec(item, item)
    if stem.endswith("Distillation") and stem[:-len("Distillation")] in ASPECTS:
        aspect = stem[:-len("Distillation")].lower()
        item = f"{aspect} aspect distillation"
        return SearchSpec(item, item)
    if stem.endswith("Phylactery"):
        aspect_name = stem[:-len("Phylactery")]
        if aspect_name in ASPECTS and aspect_name != "Chromatic":
            aspect = aspect_name.lower()
            item = f"{aspect} phylactery"
            return SearchSpec(item, item)
    if stem in SKILLS:
        item = f"{SKILLS[stem]} skill mastery scroll"
        return SearchSpec(item, item)

    map_match = re.fullmatch(r"T([1-8])", stem)
    if map_match:
        if stem not in TREASURE_MAPS:
            raise ValueError(f"No verified Vendor Search mapping exists for {variable_name}.")
        search, match, _ = TREASURE_MAPS[stem]
        return SearchSpec(search, match)

    raise ValueError(f"No default Vendor Search mapping exists for {variable_name}.")


def load_search_specs(
    variable_names: list[str], overrides_path: Path | None = None
) -> dict[str, SearchSpec]:
    overrides: dict[str, SearchSpec] = {}
    if overrides_path is not None and overrides_path.exists():
        try:
            raw_overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read search overrides: {error}") from error
        if not isinstance(raw_overrides, dict):
            raise ValueError("Search overrides must be a JSON object.")

        unknown = sorted(set(raw_overrides) - set(variable_names))
        if unknown:
            raise ValueError(
                "Search overrides contain variables not in the script: "
                + ", ".join(unknown)
            )
        ignored_overrides = sorted(set(raw_overrides) & IGNORED_VARIABLES)
        if ignored_overrides:
            raise ValueError(
                "Search overrides cannot enable ignored variables: "
                + ", ".join(ignored_overrides)
            )

        for name, value in raw_overrides.items():
            if not isinstance(value, dict):
                raise ValueError(f"Override for {name} must be an object.")
            search = value.get("search")
            match = value.get("match")
            if not isinstance(search, str) or not search.strip():
                raise ValueError(f"Override for {name} needs a non-empty 'search'.")
            if not isinstance(match, str) or not match.strip():
                raise ValueError(f"Override for {name} needs a non-empty 'match'.")
            overrides[name] = SearchSpec(search.strip(), match.strip())

    specs = {}
    for name in variable_names:
        if name in IGNORED_VARIABLES:
            continue
        specs[name] = (
            overrides[name] if name in overrides else default_search_spec(name)
        )
    return specs
