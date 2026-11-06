"""Sequential price collection with explicit pacing and callback-based I/O."""

from dataclasses import dataclass
from typing import Callable
import time

from core.price_logic import estimate_price
from core.search_catalog import SearchSpec
from core.site_search import (
    PORTAL_URL,
    SearchReadError,
    SiteAccessStopped,
    check_challenge,
    default_profile_dir,
    is_login_page,
    make_response_watcher,
    open_search_page,
    read_item_prices,
)


SEARCH_DELAY_MS = 2000


@dataclass
class CollectHooks:
    """UI-specific callbacks. The GUI and CLI supply their own implementations."""

    log: Callable[[str], None] = print
    ask_retry: Callable[[str], bool] | None = None
    wait_for_login: Callable[[], None] = lambda: None
    confirm_start: Callable[[int], bool] = lambda remaining: True


def run_collection(
    page,
    variable_names: list[str],
    search_specs: dict[str, SearchSpec],
    blocked_responses: list[str],
    prices_by_variable: dict[str, int] | None = None,
    save_progress=None,
    ask_retry=None,
    reopen_page=None,
    log: Callable[[str], None] = print,
) -> dict[str, int]:
    prices_by_variable = {} if prices_by_variable is None else prices_by_variable
    total = len(variable_names)
    for index, variable in enumerate(variable_names, start=1):
        if variable in prices_by_variable:
            log(
                f"[{index:02d}/{total}] {variable}: "
                f"already collected ({prices_by_variable[variable]}), skipped"
            )
            continue
        spec = search_specs[variable]
        while True:
            log(f"[{index:02d}/{total}] {variable}: {spec.search}")
            started = time.perf_counter()
            try:
                listings, ignored_warning_prices = read_item_prices(
                    page, spec, blocked_responses
                )
                try:
                    estimate = estimate_price(listings)
                except ValueError as error:
                    raise SearchReadError(
                        f"Could not estimate a usable price for {spec.search!r}: {error}"
                    ) from error
                break
            except SearchReadError as error:
                log(f"      FAILED: {error}")
                if ask_retry is None or not ask_retry(variable):
                    raise
                page.wait_for_timeout(SEARCH_DELAY_MS)
                if reopen_page is not None:
                    reopen_page()
        elapsed = time.perf_counter() - started
        prices_by_variable[variable] = estimate.price
        if save_progress is not None:
            save_progress(prices_by_variable)
        sample = ", ".join(str(listing.price) for listing in listings)
        log(
            f"      {len(listings)} price listings; "
            f"{ignored_warning_prices} warning/range prices ignored; "
            f"{estimate.eligible_count} recent; "
            f"{estimate.ignored_old_count} older than 2 months ignored; "
            f"{estimate.used_count} used; {estimate.method}: {estimate.price}; "
            f"prices: {sample}; search/load: {elapsed:.1f}s"
        )
        if index < total:
            page.wait_for_timeout(SEARCH_DELAY_MS)
            check_challenge(page, blocked_responses)
    return prices_by_variable


def collect_prices(
    variable_names: list[str],
    search_specs: dict[str, SearchSpec],
    prices: dict[str, int] | None,
    save_progress,
    hooks: CollectHooks,
) -> dict[str, int] | None:
    """Opens a visible browser the user logs into, then searches sequentially.

    Returns None if the user declines to start. Raises SiteAccessStopped or
    SearchReadError on site problems; no retries happen after a site block.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ValueError(
            "Playwright is not installed. Run 'py -m pip install -r requirements.txt'."
        ) from error

    profile_dir = default_profile_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)
    blocked_responses: list[str] = []

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                viewport={"width": 1365, "height": 900},
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(PORTAL_URL, wait_until="domcontentloaded")
                context.on("response", make_response_watcher(blocked_responses))
                hooks.wait_for_login()
                check_challenge(page, blocked_responses)
                if is_login_page(page):
                    raise SiteAccessStopped(
                        "The browser is still on the login page; sign in manually first."
                    )
                open_search_page(page, blocked_responses)
                remaining = len(variable_names) - len(prices or {})
                if not hooks.confirm_start(remaining):
                    return None
                return run_collection(
                    page,
                    variable_names,
                    search_specs,
                    blocked_responses,
                    prices,
                    save_progress,
                    hooks.ask_retry,
                    lambda: open_search_page(page, blocked_responses),
                    log=hooks.log,
                )
            finally:
                context.close()
    except PlaywrightError as error:
        raise SearchReadError(f"Browser automation failed: {error}") from error
