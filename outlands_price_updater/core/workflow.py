"""UI-free update workflow: plans owned items, collects prices, writes the script."""

from dataclasses import dataclass, field
from pathlib import Path

from core.checkpoint import checkpoint_path_for, load_checkpoint, save_checkpoint
from core.collector import CollectHooks, collect_prices
from core.inventory_ocr import match_inventory_text, InventoryMatch
from core.razor_generator import generate_script, price_variables
from core.rare_cloth import rare_cloth_variable
from core.search_catalog import load_search_specs
from core.site_search import SearchReadError, SiteAccessStopped


DEFAULT_OUTPUT_NAME = "price_script.razor"


@dataclass(frozen=True)
class OwnedPlan:
    match: InventoryMatch
    not_owned: list[str]
    cloth_hues: list[int]
    searched_variables: list[str]


@dataclass(frozen=True)
class UpdateRequest:
    variable_names: list[str]
    not_owned: list[str]
    cloth_hues: list[int]
    output: Path
    override_path: Path | None = None
    resume: bool = False


@dataclass
class UpdateResult:
    output: Path
    searched_count: int
    not_owned: list[str] = field(default_factory=list)


def write_new_script(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(text)


def validate_output(output: Path) -> None:
    if output.exists():
        raise FileExistsError(
            f"Output file already exists; it was not overwritten: {output}"
        )
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output.parent}")


def plan_owned_search(text: str) -> OwnedPlan:
    """Maps OCR text to searchable variables. Pure; no I/O."""
    match = match_inventory_text(text)
    all_names = price_variables()
    not_owned = [name for name in all_names if name not in match.owned]
    cloth_hues = list(match.rare_cloth)
    cloth_variables = [rare_cloth_variable(hue) for hue in cloth_hues]
    return OwnedPlan(
        match=match,
        not_owned=not_owned,
        cloth_hues=cloth_hues,
        searched_variables=match.owned + cloth_variables,
    )


def run_update(request: UpdateRequest, hooks: CollectHooks) -> UpdateResult | None:
    """Runs collection and writes the script. Returns None if the user cancels."""
    log = hooks.log
    validate_output(request.output)
    variable_names = request.variable_names
    search_specs = load_search_specs(
        price_variables(request.cloth_hues),
        request.override_path
        if request.override_path and request.override_path.exists()
        else None,
    )

    checkpoint = checkpoint_path_for(request.output)
    collected: dict[str, int] = {}
    if checkpoint.exists():
        if not request.resume:
            raise FileExistsError(
                f"A progress file from an earlier run exists: {checkpoint}\n"
                "Run again with --resume to continue it, or delete it to start over."
            )
        collected = load_checkpoint(checkpoint, variable_names)
        log(
            f"Resuming: {len(collected)} of {len(variable_names)} prices "
            "loaded from the earlier run."
        )
    elif request.resume:
        raise FileNotFoundError(f"No progress file to resume: {checkpoint}")

    log(f"Looking up {len(variable_names)} price variables.")
    log(f"Output will be created without overwriting: {request.output}")

    try:
        prices = collect_prices(
            variable_names,
            search_specs,
            collected,
            lambda current: save_checkpoint(checkpoint, current),
            hooks,
        )
    except (SiteAccessStopped, SearchReadError):
        if checkpoint.exists():
            log(
                f"Progress was saved to {checkpoint}. "
                "Run again with --resume to continue from where it stopped."
            )
        raise
    if prices is None:
        return None

    if request.not_owned:
        prices = {**{name: 0 for name in request.not_owned}, **prices}
    script = generate_script(prices, request.cloth_hues)
    write_new_script(request.output, script)
    checkpoint.unlink(missing_ok=True)
    return UpdateResult(
        output=request.output,
        searched_count=len(variable_names),
        not_owned=request.not_owned,
    )
