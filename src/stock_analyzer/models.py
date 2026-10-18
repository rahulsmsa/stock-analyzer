"""Typed dataclasses for every report field."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PriceData:
    ticker: str
    price: float
    shares_outstanding: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    fcf_yield: Optional[float] = None


@dataclass
class FinancialSeries:
    """3–5 year annual series of normalized financials."""

    years: list[int] = field(default_factory=list)
    revenue: list[float] = field(default_factory=list)
    cogs: list[float] = field(default_factory=list)
    sga: list[float] = field(default_factory=list)
    operating_income: list[float] = field(default_factory=list)
    capex: list[float] = field(default_factory=list)
    operating_cash_flow: list[float] = field(default_factory=list)
    cash: list[float] = field(default_factory=list)
    debt: list[float] = field(default_factory=list)
    equity: list[float] = field(default_factory=list)


@dataclass
class QuantResult:
    """Step 4 outputs."""

    gross_margin: list[float] = field(default_factory=list)
    operating_margin: list[float] = field(default_factory=list)
    fcf_conversion: list[float] = field(default_factory=list)
    operating_leverage_score: str = "Negative"
    roic: Optional[float] = None
    wacc: Optional[float] = None
    roic_wacc_spread: Optional[float] = None


@dataclass
class NarrativeAudit:
    """Step 1 outputs."""

    promises_year1: list[str] = field(default_factory=list)
    promises_kept_year3: list[str] = field(default_factory=list)
    narrative_shifts: list[str] = field(default_factory=list)
    dropped_kpis: list[str] = field(default_factory=list)
    documents_used: list[str] = field(default_factory=list)


@dataclass
class ForensicResult:
    """Step 2 outputs."""

    customer_concentration: list[str] = field(default_factory=list)
    supplier_concentration: list[str] = field(default_factory=list)
    purchase_obligations: list[str] = field(default_factory=list)
    off_balance_sheet: list[str] = field(default_factory=list)
    accounting_changes: list[str] = field(default_factory=list)


@dataclass
class MoatResult:
    """Step 3 outputs."""

    pillar_scores: dict[str, int] = field(default_factory=dict)
    rating: str = "None"
    primary_source: str = ""
    bull_case: str = ""
    bear_case: str = ""
    existential_threat: str = ""


@dataclass
class Report:
    """Complete report assembled from all steps."""

    ticker: str
    price: PriceData
    quant: QuantResult
    narrative: NarrativeAudit
    forensic: ForensicResult
    moat: MoatResult
    llm_skipped: bool = False