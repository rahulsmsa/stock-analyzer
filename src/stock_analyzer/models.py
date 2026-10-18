"""Typed dataclasses for every report field."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Company:
    """Resolved identity for the requested ticker."""

    ticker: str
    cik: str
    name: str
    industry: str = ""


@dataclass
class Filing:
    """One accepted submission."""

    accession: str
    form: str
    filed_date: date
    period: date
    primary_document: str
    url: str


@dataclass
class SectionText:
    """Extracted narrative text for one item of one filing."""

    item: str
    accession: str
    text: str
    char_count: int
    extraction_ok: bool


@dataclass
class XbrlFact:
    """One reported value for one concept in one period."""

    concept: str
    value: float
    unit: str
    period_end: date
    fiscal_year: int
    fiscal_period: str
    form: str
    accession: str
    period_start: date | None = None
    frame: str | None = None


@dataclass
class PriceData:
    ticker: str
    price: float
    shares_outstanding: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    fcf_yield: float | None = None
    as_of: date | None = None
    beta: float | None = None
    ebitda: float | None = None


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
    depreciation_amortisation: list[float] = field(default_factory=list)
    sources: dict[str, list[str]] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)


@dataclass
class QuantResult:
    """Step 4 outputs."""

    gross_margin: list[float] = field(default_factory=list)
    operating_margin: list[float] = field(default_factory=list)
    fcf_conversion: list[float] = field(default_factory=list)
    operating_leverage_score: str = "Negative"
    roic: float | None = None
    wacc: float | None = None
    roic_wacc_spread: float | None = None
    wacc_inputs: dict[str, float] = field(default_factory=dict)
    wacc_input_sources: dict[str, str] = field(default_factory=dict)


@dataclass
class NarrativeAudit:
    """Step 1 outputs."""

    promises_year1: list[str] = field(default_factory=list)
    promises_kept_year3: list[str] = field(default_factory=list)
    narrative_shifts: list[str] = field(default_factory=list)
    dropped_kpis: list[str] = field(default_factory=list)
    documents_used: list[str] = field(default_factory=list)
    prose: str = ""
    synthesis_skipped: bool = False
    skip_reason: str = ""


@dataclass
class ForensicResult:
    """Step 2 outputs."""

    customer_concentration: list[str] = field(default_factory=list)
    supplier_concentration: list[str] = field(default_factory=list)
    purchase_obligations: list[str] = field(default_factory=list)
    off_balance_sheet: list[str] = field(default_factory=list)
    accounting_changes: list[str] = field(default_factory=list)
    evidence: dict[str, list[str]] = field(default_factory=dict)
    examined: bool = False
    skip_reason: str = ""


@dataclass
class MoatResult:
    """Step 3 outputs."""

    pillar_scores: dict[str, int] = field(default_factory=dict)
    rating: str = "None"
    primary_source: str = ""
    bull_case: str = ""
    bear_case: str = ""
    existential_threat: str = ""
    evidence: dict[str, list[str]] = field(default_factory=dict)
    synthesis_skipped: bool = False


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
    company: Company | None = None
    generated_at: datetime | None = None
    filings_used: list[Filing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)