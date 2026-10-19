"""XBRL financial normalizer: pull companyfacts and produce clean financial series."""

from __future__ import annotations

from datetime import date

from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.data.edgar import EdgarData, _has_annual_facts
from stock_analyzer.models import FinancialSeries

# Prioritized GAAP tag lists with fallbacks. Order matters: the first tag that resolves
# for a metric wins, so the most specific/common tag is listed first.
TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "InterestAndDividendIncomeOperating",  # banks: GS, SCHW, USB
        "RevenueInterestAndDividendIncomeOperating",
        "InterestIncomeOtherThanBanking",  # alternative bank tagging
    ],
    "cogs": [
        "CostOfGoodsSold",
        "CostOfRevenue",
        "CostOfSales",
    ],
    "sga": [
        "SellingGeneralAndAdministrativeExpense",
        "SellingGeneralAndAdministrativeExpenses",
        "GeneralAndAdministrativeExpense",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        "OperatingIncome",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "CapitalExpenditures",
        "PurchaseOfPropertyPlantAndEquipment",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "OperatingCashFlow",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ],
    "debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermDebtCurrent",
        "DebtCurrent",
        "DebtLongtermAndShorttermCombinedAmount",
    ],
    "equity": [
        "StockholdersEquity",
        "TotalStockholdersEquity",
    ],
    "depreciation_amortisation": [
        "DepreciationAndAmortization",
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "total_assets": ["Assets"],
    "current_liabilities": ["LiabilitiesCurrent"],
}

# Metrics with no direct tag are derived from these tags when nothing else resolves.
# ``cogs`` is derived as ``revenue - GrossProfit`` (GrossProfit is a positive figure).
DERIVED_TAGS = {
    "cogs": ["GrossProfit"],
}

# A duration fact must span at least this many days to count as annual. Quarterly facts
# filed inside a 10-K span ~90 days and must not be mistaken for annual figures (G16).
ANNUAL_MIN_DAYS = 300


def _companyfacts(client: EdgarClient, cik: str) -> dict:
    """Fetch the XBRL companyfacts document for a CIK (cached)."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    return client.get_json(url)


def _duration_days(fact: dict) -> int | None:
    """Return the fact's period length in days, or None for instantaneous facts."""
    start, end = fact.get("start"), fact.get("end")
    if not start or not end:
        return None
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return None


def _annual_facts(facts: list[dict]) -> list[dict]:
    """Keep only annual (10-K) duration facts, excluding quarterly periods (G16).

    Instantaneous facts (no ``start``) are retained: balance-sheet items such as cash,
    debt and equity are point-in-time and have no duration to test.
    """
    kept = []
    for f in facts:
        if f.get("form") != "10-K" or not f.get("end") or f.get("val") is None:
            continue
        days = _duration_days(f)
        if days is not None and days < ANNUAL_MIN_DAYS:
            continue
        kept.append(f)
    return kept


def _pick_latest_per_year(facts: list[dict]) -> dict[int, float]:
    """Pick the latest filing value per calendar year."""
    by_year: dict[int, tuple[str, float]] = {}
    for f in facts:
        end = f.get("end", "")
        try:
            year = int(end[:4])
        except (ValueError, TypeError):
            continue
        val = f["val"]
        if year not in by_year or f["end"] > by_year[year][0]:
            by_year[year] = (f["end"], val)
    return {year: val for year, (_, val) in by_year.items()}


def _facts_for_tag(facts: dict, tag: str) -> list[dict]:
    """Return the annual USD facts for a us-gaap tag, or an empty list."""
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return []
    return _annual_facts(node.get("units", {}).get("USD", []))


def _coverage(values: dict[int, float], years: list[int]) -> int:
    """Count how many of the anchor years a candidate series covers."""
    return sum(1 for y in years if y in values)


def _anchor_candidate(facts: dict, tags: list[str]) -> tuple[dict[int, float], str]:
    """Pick the revenue tag with the most recent coverage.

    The anchor defines the fiscal years every other metric aligns to, so a stale tag
    (e.g. AAPL's ``SalesRevenueNet``, which stops at FY2017) must not win over the
    current tag merely because it has more historical years. Ties break toward the
    earlier (more specific) tag in the priority list.
    """
    best: dict[int, float] = {}
    best_tag = ""
    best_latest = -1
    for tag in tags:
        tag_facts = _facts_for_tag(facts, tag)
        if not tag_facts:
            continue
        values = _pick_latest_per_year(tag_facts)
        if not values:
            continue
        latest = max(values)
        if latest > best_latest:
            best, best_tag, best_latest = values, tag, latest
    return best, best_tag


def _best_candidate(
    facts: dict, tags: list[str], years: list[int]
) -> tuple[dict[int, float], str]:
    """Pick the tag whose series covers the most anchor years.

    Companies migrate between GAAP tags over time (e.g. MSFT filed ``CostOfGoodsSold``
    only through FY2017 and ``GrossProfit`` thereafter), so the first non-empty tag is
    not necessarily the best one. Ties break toward the earlier (more specific) tag.
    """
    best: dict[int, float] = {}
    best_tag = ""
    best_score = -1
    for tag in tags:
        tag_facts = _facts_for_tag(facts, tag)
        if not tag_facts:
            continue
        values = _pick_latest_per_year(tag_facts)
        score = _coverage(values, years)
        if score > best_score:
            best, best_tag, best_score = values, tag, score
    return best, best_tag


def normalize_financials(client: EdgarClient, cik: str, edgar: EdgarData | None = None) -> FinancialSeries:
    """Build a FinancialSeries from XBRL companyfacts.

    Aligns on the fiscal years that have revenue (the anchor metric). A metric with no
    resolvable tag produces an empty list plus an entry in ``gaps`` — never a zero (G1,
    FR-022). All lists are the same length as ``years`` or empty.
    """
    series = FinancialSeries()
    facts = _companyfacts(client, cik)

    # A ticker can map to a holding shell with no XBRL history (e.g. XOM ->
    # ExxonMobil Holdings Corp); fall back to the name-matching operating company.
    if edgar is not None and not _has_annual_facts(facts):
        resolved = edgar.resolve_cik_ambiguity("", cik, facts)
        if resolved != cik:
            cik = resolved
            facts = _companyfacts(client, cik)

    # Revenue is the anchor: it defines the fiscal years every other metric aligns to.
    revenue, revenue_tag = _anchor_candidate(facts, TAGS["revenue"])
    revenue_years = sorted(revenue.keys())
    series.years = revenue_years

    year_values: dict[str, dict[int, float]] = {"revenue": revenue}
    chosen_tag: dict[str, str] = {"revenue": revenue_tag}

    for field_name, tags in TAGS.items():
        if field_name == "revenue":
            continue
        values, tag_used = _best_candidate(facts, tags, revenue_years)
        # Derive from a related tag when the direct tags cover fewer years (e.g.
        # cogs = revenue - GrossProfit).
        for derived_tag in DERIVED_TAGS.get(field_name, []):
            derived_facts = _facts_for_tag(facts, derived_tag)
            if not derived_facts:
                continue
            gross_profit = _pick_latest_per_year(derived_facts)
            derived = {
                year: revenue[year] - gp
                for year, gp in gross_profit.items()
                if year in revenue
            }
            if _coverage(derived, revenue_years) > _coverage(values, revenue_years):
                values, tag_used = derived, f"derived:{derived_tag}"
        year_values[field_name] = values
        chosen_tag[field_name] = tag_used

    for field_name in TAGS:
        values = year_values[field_name]
        # A metric is either fully populated for all revenue years or empty (no partial
        # zeros). Record the chosen tag for provenance either way.
        if all(year in values for year in revenue_years):
            col = [values[year] for year in revenue_years]
            series.sources[field_name] = [chosen_tag[field_name]] * len(revenue_years)
        else:
            col = []
            series.sources[field_name] = []
            missing_years = [str(y) for y in revenue_years if y not in values]
            series.gaps.append(
                f"{field_name}: no data for {', '.join(missing_years) if missing_years else 'any year'}"
            )
        getattr(series, field_name).extend(col)

    return series