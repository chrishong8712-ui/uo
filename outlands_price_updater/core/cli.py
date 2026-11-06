"""Console entry point. Prompts and printing live here; logic is in core.workflow."""

import argparse
from pathlib import Path
import sys
import threading

from core.collector import CollectHooks
from core.inventory_ocr import (
    INVENTORY_REGION,
    InventoryAccumulator,
    load_image,
    ocr_image,
    parse_region,
    watch_region,
)
from core.razor_generator import ScriptGenerationError, price_variables
from core.site_search import SearchReadError, SiteAccessStopped
from core.workflow import (
    DEFAULT_OUTPUT_NAME,
    UpdateRequest,
    plan_owned_search,
    run_update,
    validate_output,
)


def _watch_inventory_region(region: tuple[int, int, int, int]) -> str:
    """Captures the message area live until the user presses Enter.

    Captures run on a fixed local interval in a background thread; new unique
    lines are printed as they appear. No requests are sent to the site.
    """
    accumulator = InventoryAccumulator()
    stop_event = threading.Event()
    failure: list[BaseException] = []

    def report(lines: list[str]) -> None:
        for line in lines:
            print(f"  + {line}")

    def worker() -> None:
        try:
            watch_region(region, accumulator, stop_event, on_new_lines=report)
            if accumulator.finished and not stop_event.is_set():
                print("  'Label dump done.' detected - capture stopped. Press Enter to continue.")
        except BaseException as error:
            failure.append(error)
            stop_event.set()

    print(
        "Live OCR started on the capture area. Run the UO Razor inventory script in-game. "
        "Press Enter here when all system messages have been read."
    )
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    input()
    stop_event.set()
    thread.join()
    if failure:
        raise failure[0]
    return accumulator.text()


def _read_owned_text(args: argparse.Namespace) -> str:
    try:
        if args.inventory_image:
            image = load_image(Path(args.inventory_image).expanduser().resolve())
            return ocr_image(image)
        region = parse_region(args.inventory_region) if args.inventory_region else INVENTORY_REGION
        return _watch_inventory_region(region)
    except ImportError as error:
        raise ValueError(
            "pytesseract is not installed. Run 'py -m pip install -r requirements.txt'."
        ) from error


def select_owned_variables(args: argparse.Namespace) -> tuple[list[str], list[str], list[int]] | None:
    """Reads owned items via OCR and asks the user to confirm.

    Returns (variables to search, variables recorded as 0, rare cloth hues),
    or None if the user declines.
    """
    text = _read_owned_text(args)
    plan = plan_owned_search(text)
    match = plan.match

    print("\nOCR text read from the system message area:")
    print(text.strip() or "(no text recognized)")
    print(f"\nOwned items to search ({len(match.owned)}):")
    for name in match.owned:
        print(f"  {name}  <- '{match.matched_lines[name]}'")
    if plan.cloth_hues:
        print(f"\nRare cloth to search, identified by hue number ({len(plan.cloth_hues)}):")
        for hue in plan.cloth_hues:
            print(f"  hue {hue}  <- '{match.rare_cloth[hue]}'")
    if match.unmapped:
        print(f"\nNot mapped to any script variable, not searched ({len(match.unmapped)}):")
        for line in match.unmapped:
            print(f"  {line}")
    if match.ambiguous:
        print(f"\nAmbiguous labels, not searched ({len(match.ambiguous)}):")
        for line, variables in match.ambiguous:
            print(f"  '{line}' could be: {', '.join(variables)}")
    print(f"\nNot owned, recorded as 0 and not searched ({len(plan.not_owned)}):")
    print("  " + ", ".join(plan.not_owned))

    if not plan.searched_variables:
        raise ValueError("OCR did not map any owned items; nothing to search.")
    total = len(plan.searched_variables)
    confirmation = input(
        f"\nSearch the {total} owned items above? Type YES to continue: "
    ).strip()
    if confirmation != "YES":
        return None
    return plan.searched_variables, plan.not_owned, plan.cloth_hues


def prompt_retry(variable: str) -> bool:
    answer = input(
        f"{variable} failed. Press Enter to retry this item, "
        "or type Q to stop (progress is saved): "
    )
    return answer.strip().lower() != "q"


def console_hooks() -> CollectHooks:
    def wait_for_login() -> None:
        input(
            "\nComplete any login steps in the browser window. "
            "When the portal is open and logged in, return here and press Enter."
        )

    def confirm_start(remaining: int) -> bool:
        confirmation = input(
            f"Ready to search {remaining} items sequentially. "
            "Type START to begin (anything else cancels): "
        ).strip()
        return confirmation == "START"

    return CollectHooks(
        log=print,
        ask_retry=prompt_retry,
        wait_for_login=wait_for_login,
        confirm_start=confirm_start,
    )


def run(args: argparse.Namespace) -> int:
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path.cwd() / DEFAULT_OUTPUT_NAME
    )
    override_path = (
        Path(args.overrides).expanduser().resolve()
        if args.overrides
        else Path.cwd() / "search_overrides.json"
    )
    if args.overrides and not override_path.is_file():
        raise FileNotFoundError(f"Search override file does not exist: {override_path}")
    validate_output(output)

    variable_names = price_variables()
    not_owned: list[str] = []
    cloth_hues: list[int] = []
    if not (
        args.search_all or args.inventory_image or args.inventory_region or args.inventory_live
    ):
        print("\nSelect the search mode:")
        print("  1) All items")
        print("  2) Owned items only (live OCR of the Razor inventory script messages)")
        choice = input("Enter 1 or 2: ").strip()
        if choice == "2":
            args.inventory_live = True
        elif choice != "1":
            print("Cancelled; no output file was created.")
            return 0
    if args.inventory_image or args.inventory_region or args.inventory_live:
        selection = select_owned_variables(args)
        if selection is None:
            print("Cancelled; no output file was created.")
            return 0
        variable_names, not_owned, cloth_hues = selection

    print(
        "A visible Chromium window will open. Log in yourself there; "
        "the app never asks for or reads your password."
    )
    request = UpdateRequest(
        variable_names=variable_names,
        not_owned=not_owned,
        cloth_hues=cloth_hues,
        output=output,
        override_path=override_path,
        resume=args.resume,
    )
    result = run_update(request, console_hooks())
    if result is None:
        print("Cancelled; no output file was created.")
        return 0

    print(
        f"\nSearched {result.searched_count} owned price variables. "
        f"Created Razor script: {result.output}"
    )
    if result.not_owned:
        print(f"Not owned (set to 0, not searched): {', '.join(result.not_owned)}")
    print(
        "Vendor Search reports a 15-minute delay before newly listed items "
        "appear; the results may not include more recent listings."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read Outlands Vendor Search prices and update Razor script variables."
    )
    parser.add_argument(
        "--output",
        help="Output path (must not already exist). Defaults to price_script.razor in the current folder.",
    )
    parser.add_argument(
        "--overrides",
        help="Optional JSON file for custom variable-to-search mappings.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue an earlier interrupted run using its saved progress file.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--all",
        dest="search_all",
        action="store_true",
        help="Search every item without the mode prompt.",
    )
    source.add_argument(
        "--inventory-image",
        help="OCR an image file of the Razor system messages to choose owned items.",
    )
    source.add_argument(
        "--inventory-live",
        action="store_true",
        help=(
            f"Live OCR of the fixed system message area {INVENTORY_REGION} while the "
            "Razor inventory script runs; press Enter to stop and use the lines read so far."
        ),
    )
    source.add_argument(
        "--inventory-region",
        help=(
            "Live OCR of a custom screen area (x,y,width,height) instead of the fixed one; "
            "press Enter to stop and use the lines read so far."
        ),
    )
    args = parser.parse_args()

    try:
        return run(args)
    except (
        OSError,
        ValueError,
        ScriptGenerationError,
        SiteAccessStopped,
        SearchReadError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        print("No updated script was created.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
