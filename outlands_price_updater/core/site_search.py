"""Browser-side Vendor Search access (Playwright). No console I/O here.

Callers own the browser lifecycle; this module only drives pages it is given.
"""

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.price_logic import (
    PRICE_SAMPLE_SIZE,
    VendorListing,
    is_warning_price,
    parse_listed_at,
    parse_price,
)
from core.search_catalog import SearchSpec


PORTAL_URL = "https://portal.uooutlands.com/vendor-search"
PORTAL_HOST = "portal.uooutlands.com"
AUTOCOMPLETE_SETTLE_DELAY_MS = 2000
AUTOCOMPLETE_TIMEOUT_MS = 15000
RESULT_TIMEOUT_MS = 30000
BLOCK_MARKERS = (
    "access denied",
    "verify you are human",
    "unusual traffic",
    "too many requests",
    "request was blocked",
    "temporarily blocked",
    "captcha",
)


class SiteAccessStopped(RuntimeError):
    pass


class SearchReadError(RuntimeError):
    pass


def default_profile_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data)
    else:
        root = Path.home() / "AppData" / "Local"
    return root / "OutlandsPriceUpdater" / "browser-profile"


def make_response_watcher(blocked_responses: list[str]):
    """Returns a Playwright response handler that records 429/401/403/5xx replies."""

    def on_response(response) -> None:
        host = urlparse(response.url).hostname
        status = response.status
        if status == 429 or (
            host == PORTAL_HOST and (status in (401, 403) or 500 <= status < 600)
        ):
            blocked_responses.append(
                f"Outlands Portal returned HTTP {status}; "
                "the run stopped without retrying."
            )

    return on_response


def check_challenge(page, blocked_responses: list[str]) -> None:
    if blocked_responses:
        raise SiteAccessStopped(blocked_responses[0])

    parsed_url = urlparse(page.url)
    body = page.locator("body").inner_text(timeout=5000).casefold()
    challenge_iframes = page.locator(
        'iframe[src*="captcha"], iframe[src*="challenge"], '
        'iframe[src*="recaptcha"], iframe[src*="hcaptcha"]'
    ).count()
    if challenge_iframes:
        raise SiteAccessStopped("A CAPTCHA or access challenge was detected.")
    for marker in BLOCK_MARKERS:
        if marker in body:
            raise SiteAccessStopped(
                f"The page displayed an access or rate-limit challenge ({marker})."
            )
    if parsed_url.hostname != PORTAL_HOST:
        raise SiteAccessStopped(
            f"Navigation left the Outlands Portal domain: {page.url}"
        )


def is_login_page(page) -> bool:
    return urlparse(page.url).path.rstrip("/") == "/login"


def open_search_page(page, blocked_responses: list[str]) -> None:
    from playwright.sync_api import Error as PlaywrightError

    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    try:
        page.locator('input[placeholder="Search"][role="combobox"]').wait_for(
            state="visible", timeout=20000
        )
    except PlaywrightError as error:
        check_challenge(page, blocked_responses)
        raise SearchReadError(
            "The Vendor Search input did not appear after login."
        ) from error
    check_challenge(page, blocked_responses)


def _suggestion_title(option) -> str:
    text = option.inner_text().strip()
    return text.splitlines()[0].strip() if text else ""


def _matches_suggestion(title: str, spec: SearchSpec) -> bool:
    normalized_title = title.casefold()
    normalized_match = spec.match.casefold()
    if spec.exact_match:
        return normalized_title == normalized_match
    return normalized_match in normalized_title


def _select_item(page, spec: SearchSpec, blocked_responses: list[str]) -> str:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    check_challenge(page, blocked_responses)
    search_box = page.locator('input[placeholder="Search"][role="combobox"]')
    if search_box.count() != 1:
        raise SearchReadError("Could not identify the Vendor Search input.")

    search_box.fill(spec.search)
    page.wait_for_timeout(AUTOCOMPLETE_SETTLE_DELAY_MS)
    check_challenge(page, blocked_responses)
    options = page.locator('mat-option[role="option"]:visible')
    try:
        page.wait_for_function(
            """({expected, exact}) => [...document.querySelectorAll('mat-option[role="option"]')]
                .some(option => {
                    const style = getComputedStyle(option);
                    const visible = style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && option.getClientRects().length > 0;
                    const title = option.innerText.trim().split(/\\r?\\n/)[0].trim().toLowerCase();
                    return visible && (exact ? title === expected : title.includes(expected));
                })""",
            arg={
                "expected": spec.match.casefold(),
                "exact": spec.exact_match,
            },
            timeout=AUTOCOMPLETE_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError as error:
        check_challenge(page, blocked_responses)
        raise SearchReadError(
            f"No matching autocomplete suggestion appeared for "
            f"{spec.search!r}."
        ) from error

    check_challenge(page, blocked_responses)
    suggestions = [
        _suggestion_title(options.nth(index))
        for index in range(options.count())
    ]
    matching_titles = [
        index
        for index, title in enumerate(suggestions)
        if _matches_suggestion(title, spec)
    ]
    if len(matching_titles) != 1:
        visible = "; ".join(suggestions) if suggestions else "(none)"
        raise SearchReadError(
            f"Expected exactly one autocomplete item "
            f"{'equal to' if spec.exact_match else 'containing'} {spec.match!r} "
            f"for {spec.search!r}; found {len(matching_titles)}. "
            f"Suggestions: {visible}"
        )

    selected_title = suggestions[matching_titles[0]]
    selected_option = options.nth(matching_titles[0])
    try:
        if options.count() != len(suggestions) or not _matches_suggestion(
            _suggestion_title(selected_option), spec
        ):
            raise SearchReadError(
                f"The autocomplete list changed before selecting "
                f"{selected_title!r}."
            )
        page.mouse.move(0, 0)
        page.locator(".mat-mdc-tooltip-surface:visible").first.wait_for(
            state="hidden", timeout=3000
        )
        selected_option.click(timeout=AUTOCOMPLETE_TIMEOUT_MS)
    except PlaywrightTimeoutError as error:
        check_challenge(page, blocked_responses)
        raise SearchReadError(
            f"The visible autocomplete option {selected_title!r} could not "
            f"be selected: {error}"
        ) from error
    check_challenge(page, blocked_responses)
    expected_search_term = f'"{selected_title}"'
    try:
        page.wait_for_function(
            """expected => new URL(location.href).searchParams.get('searchTerm') === expected""",
            arg=expected_search_term,
            timeout=10000,
        )
    except PlaywrightTimeoutError as error:
        check_challenge(page, blocked_responses)
        raise SearchReadError(
            f"Selecting {selected_title!r} did not start a Vendor Search."
        ) from error
    return selected_title


def _read_sorted_prices(
    page, spec: SearchSpec, selected_title: str, blocked_responses: list[str]
) -> tuple[list[VendorListing], int]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    try:
        page.wait_for_function(
            """({title, match}) => {
                const table = document.querySelector('table[role="table"]');
                const rows = table?.querySelectorAll('tbody tr[role="row"]') ?? [];
                const body = (document.body?.innerText ?? '').toLowerCase();
                const params = new URL(location.href).searchParams;
                const term = params.get('searchTerm') ?? '';
                const actualTitle = term.replace(/^\"|\"$/g, '').toLowerCase();
                const firstName = rows[0]?.querySelector('td')?.innerText.trim().toLowerCase() ?? '';
                return actualTitle === title.toLowerCase()
                    && ((rows.length > 0 && firstName.includes(match.toLowerCase()))
                        || /total results:\\s*0|no results|no listings|no data/.test(body));
            }""",
            arg={"title": selected_title, "match": spec.match},
            timeout=RESULT_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError as error:
        check_challenge(page, blocked_responses)
        raise SearchReadError(
            f"Vendor Search results did not finish loading for {spec.search!r}."
        ) from error

    check_challenge(page, blocked_responses)
    query = parse_qs(urlparse(page.url).query)
    if query.get("sortActive") != ["Price"] or query.get("sortDirection") != ["asc"]:
        raise SearchReadError(
            "Vendor Search is not sorted by Price ascending; refusing to use "
            "an incomplete result page."
        )

    table = page.locator('table[role="table"]')
    headers = [
        value.strip().casefold()
        for value in table.locator('thead th[role="columnheader"]').all_inner_texts()
    ]
    if "price" not in headers:
        raise SearchReadError("The Vendor Search results have no Price column.")
    price_column = headers.index("price")
    if "listed" not in headers:
        raise SearchReadError(
            "The Vendor Search results have no Listed column; refusing to "
            "estimate prices without checking listing age."
        )
    listed_column = headers.index("listed")
    rows = table.locator('tbody tr[role="row"]')
    row_count = rows.count()
    if row_count == 0:
        raise SearchReadError(f"No vendor listings were found for {spec.search!r}.")

    listings = []
    ignored_warning_prices = 0
    expected_name = spec.match.casefold()
    for index in range(row_count):
        cells = rows.nth(index).locator("td").all_inner_texts()
        if len(cells) <= max(price_column, listed_column):
            raise SearchReadError(
                f"Could not read the Price or Listed cell in result row {index + 1} "
                f"for {spec.search!r}."
            )
        item_name = cells[0].strip().casefold()
        if expected_name not in item_name:
            raise SearchReadError(
                f"Unexpected item {cells[0].strip()!r} appeared in results "
                f"for {spec.search!r}; no prices were accepted."
            )
        if is_warning_price(cells[price_column]):
            ignored_warning_prices += 1
            continue
        try:
            listed_at = parse_listed_at(cells[listed_column])
            price = parse_price(cells[price_column])
        except ValueError as error:
            raise SearchReadError(
                f"Could not parse the Price or Listed cell in result row "
                f"{index + 1} for {spec.search!r}: {error}"
            ) from error
        listings.append(VendorListing(price, listed_at))
        if len(listings) == PRICE_SAMPLE_SIZE:
            break

    prices = [listing.price for listing in listings]
    if any(left > right for left, right in zip(prices, prices[1:])):
        raise SearchReadError(
            f"Results for {spec.search!r} were not in ascending price order."
        )
    return listings, ignored_warning_prices


def read_item_prices(
    page, spec: SearchSpec, blocked_responses: list[str]
) -> tuple[list[VendorListing], int]:
    selected_title = _select_item(page, spec, blocked_responses)
    return _read_sorted_prices(page, spec, selected_title, blocked_responses)
