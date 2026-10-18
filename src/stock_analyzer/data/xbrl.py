"""XBRL financial normalizer: pull companyfacts and produce clean financial series."""

from __future__ import annotations

from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.models import FinancialSeries

# Prioritized GAAP tag lists with fallbacks.
TAGS = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractsWithCustomers",
    ],
    "cogs": [
        "CostOfGoodsSold",
        "CostOfRevenue",
        "CostOfSales",
    ],
    "sga": [
        "SellingGeneralAndAdministrativeExpense",
        "SellingGeneralAndAdministrativeExpenses",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        "OperatingIncome",
    ],
    "capex": [
        "CapitalExpenditures",
        "PurchaseOfPropertyPlantAndEquipment",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "OperatingCashFlow",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
    ],
    "debt": [
        "LongTermDebt",
        "LongTermDebtCurrent",
        "DebtCurrent",
    ],
    "equity": [
        "StockholdersEquity",
        "TotalStockholdersEquity",
    ],
}


def _find_fact(client: EdgarClient, cik: str, tag: str) -> list[dict] | None:
    """Fetch companyconcept facts for a tag, return annual units USD."""
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    try:
        data = client.get_json(url)
    except Exception:
        return None
    units = data.get("units", {})
    usd = units.get("USD", [])
    # Filter to annual (10-K) filings only, keep latest per year
    annual = [f for f in usd if f.get("form") == "10-K" and f.get("end") and f.get("val") is not None]
    return annual


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


def normalize_financials(client: EdgarClient, cik: str) -> FinancialSeries:
    """Build a FinancialSeries from XBRL companyfacts."""
    series = FinancialSeries()
    year_values: dict[str, dict[int, float]] = {}

    for field_name, tags in TAGS.items():
        values: dict[int, float] = {}
        for tag in tags:
            facts = _find_fact(client, cik, tag)
            if facts:
                values = _pick_latest_per_year(facts)
                if values:
                    break
        year_values[field_name] = values

    # Union of all years across fields
    all_years: set[int] = set()
    for values in year_values.values():
        all_years.update(values.keys())

    for year in sorted(all_years):
        series.years.append(year)
        for field_name in TAGS:
            val = year_values[field_name].get(year)
            getattr(series, field_name).append(val if val is not None else 0.0)

    return series