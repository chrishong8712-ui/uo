import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


PRICE_SAMPLE_SIZE = 10
WARNING_PRICE_RE = re.compile(r"^\s*warning\b", re.IGNORECASE)


@dataclass(frozen=True)
class VendorListing:
    price: Decimal
    listed_at: datetime


@dataclass(frozen=True)
class PriceEstimate:
    price: int
    eligible_count: int
    ignored_old_count: int
    used_count: int
    method: str


def parse_price(value: str) -> Decimal:
    normalized = value.strip().replace(",", "").replace("$", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        raise ValueError(f"Unrecognized price value: {value!r}")

    price = Decimal(normalized)
    if price < 0:
        raise ValueError(f"Price cannot be negative: {value!r}")
    return price


def is_warning_price(value: str) -> bool:
    return WARNING_PRICE_RE.match(value) is not None


def parse_listed_at(value: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now().astimezone()
    normalized = value.strip().casefold()
    if normalized in {"just now", "today", "less than a minute ago"}:
        return now
    if normalized == "yesterday":
        return now - timedelta(days=1)

    relative = re.search(
        r"\b(?P<count>\d+|a|an)\s+"
        r"(?P<unit>minute|hour|day|week|month|year)s?\s+ago\b",
        normalized,
    )
    if relative:
        count = relative.group("count")
        amount = 1 if count in {"a", "an"} else int(count)
        unit = relative.group("unit")
        days_per_unit = {
            "minute": 1 / 1440,
            "hour": 1 / 24,
            "day": 1,
            "week": 7,
            "month": 30,
            "year": 365,
        }
        return now - timedelta(days=amount * days_per_unit[unit])

    parsed = None
    for date_format in (
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            parsed = datetime.strptime(value.strip(), date_format)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"Unrecognized listing date: {value!r}") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now.tzinfo)
    if parsed > now:
        raise ValueError(f"Listing date is in the future: {value!r}")
    return parsed


def estimate_price(
    listings: list[VendorListing],
    max_age: timedelta = timedelta(days=60),
    now: datetime | None = None,
) -> PriceEstimate:
    if not listings:
        raise ValueError("Cannot calculate a price from an empty listing list.")

    current_time = now or datetime.now().astimezone()
    sample = listings[:PRICE_SAMPLE_SIZE]
    recent = [
        listing
        for listing in sample
        if current_time - listing.listed_at < max_age
    ]
    ignored_old_count = len(sample) - len(recent)
    if not recent:
        raise ValueError("No listings are newer than the two-month cutoff.")

    if len(recent) <= 5:
        latest = max(recent, key=lambda listing: listing.listed_at)
        return PriceEstimate(
            int(latest.price), len(recent), ignored_old_count, 1, "latest listing"
        )

    prices = sorted(listing.price for listing in recent)
    middle = len(prices) // 2
    median = (
        prices[middle]
        if len(prices) % 2
        else (prices[middle - 1] + prices[middle]) / 2
    )
    included = recent
    method = "average of all recent listings"
    if prices[-1] >= prices[0] * 2 and prices[-1] > prices[0]:
        lower_bound = median / 2
        upper_bound = median * 2
        included = [
            listing
            for listing in recent
            if lower_bound <= listing.price <= upper_bound
        ]
        if not included:
            raise ValueError("No comparable listings remain around the median.")
        method = "average around median; excluded price outliers"

    average = sum(
        (listing.price for listing in included), Decimal(0)
    ) / len(included)
    return PriceEstimate(
        int(average), len(recent), ignored_old_count, len(included), method
    )
