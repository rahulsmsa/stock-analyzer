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
class PeerData:
    """One peer's market snapshot for the section-1 comparison table (F1)."""

    ticker: str
    price: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    fcf_yield: float | None = None


@dataclass
class ValuationHistory:
    """Target price versus its own 5-year monthly-close range (F2a)."""

    price: float | None = None
    low_5y: float | None = None
    high_5y: float | None = None
    average_5y: float | None = None
    percentile: float | None = None  # 0.0-1.0 position of price within the 5y range
    months: int = 0


@dataclass
class SensitivityRow:
    """One price-shock row of the deterministic sensitivity table (F2b)."""

    price_change: float  # e.g. -0.20 for -20%
    price: float | None = None
    fcf_yield: float | None = None
    ev_ebitda: float | None = None


@dataclass
class RecommendationTrend:
    """One monthly grade-count snapshot of Street opinion (feature 003)."""

    period: str = ""  # e.g. "0m" (current), "-1m"
    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0


@dataclass
class RatingAction:
    """One upgrade/downgrade event from the Street feed (feature 003)."""

    firm: str
    to_grade: str
    from_grade: str
    action: str
    target_action: str = ""
    current_target: float | None = None
    prior_target: float | None = None
    date: date | None = None


@dataclass
class StreetSnapshot:
    """Consensus analyst data for one ticker, with as-of timestamps (feature 003)."""

    ticker: str
    recommendation_label: str | None = None
    recommendation_mean: float | None = None
    analyst_count: int = 0
    target_low: float | None = None
    target_mean: float | None = None
    target_median: float | None = None
    target_high: float | None = None
    trend: list[RecommendationTrend] = field(default_factory=list)
    actions: list[RatingAction] = field(default_factory=list)
    as_of: date | None = None
    retrieved_at: datetime | None = None


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
    net_income: list[float] = field(default_factory=list)
    total_assets: list[float] = field(default_factory=list)
    current_liabilities: list[float] = field(default_factory=list)
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
    roic_method: str = ""
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
    pillar_rationales: dict[str, str] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
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
    peers: list[PeerData] = field(default_factory=list)
    valuation_history: ValuationHistory | None = None
    sensitivity: list[SensitivityRow] = field(default_factory=list)
    street: StreetSnapshot | None = None
    street_upside: float | None = None
    technicals: TechnicalsSnapshot | None = None
    factors: FactorSnapshot | None = None
    dividends: DividendSnapshot | None = None
    classification: StrategyClassification | None = None
    scorecard: list[ScorecardRow] = field(default_factory=list)


PILLAR_NAMES = (
    "Fundamental & Forensic",
    "Technical & Trend",
    "Factor Exposure",
    "Macro & Thematic",
    "Dividend & Yield",
)


@dataclass
class TechnicalsSnapshot:
    """Technical indicators derived from daily OHLCV (feature 004)."""

    ticker: str
    as_of: date | None = None
    price: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    price_vs_sma50: float | None = None
    price_vs_sma200: float | None = None
    rsi14: float | None = None
    rel_volume: float | None = None
    stage: str | None = None
    support: float | None = None
    resistance: float | None = None
    history_days: int = 0


@dataclass
class DividendSnapshot:
    """Dividend history and payout quality (feature 004)."""

    ticker: str
    as_of: date | None = None
    is_payer: bool = False
    first_dividend_year: int | None = None
    last_dividend_date: str | None = None
    dps_latest: float | None = None
    yield_pct: float | None = None
    cagr_5y: float | None = None
    payout_fcf: float | None = None
    payout_earnings: float | None = None
    payout_pct_label: str | None = None
    years_paid: int = 0
    annual_dividends: dict[int, float] = field(default_factory=dict)


@dataclass
class FactorSnapshot:
    """Factor screen scores and quality metrics (feature 004).

    ``value/quality/momentum/low_vol`` are 1-10 scores (FR-006).
    """

    ticker: str
    value_score: int | None = None
    quality_score: int | None = None
    momentum_score: int | None = None
    low_vol_score: int | None = None
    piotroski: int | None = None
    altman_z: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    interest_coverage: float | None = None
    rs_vs_benchmark_3m: float | None = None
    rs_vs_benchmark_12m: float | None = None
    benchmark: str = "SPY"
    max_drawdown_1y: float | None = None
    fcf_yield: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ScorecardRow:
    """One pillar status row for the Section 1b scorecard table."""

    pillar: str
    status: str  # Positive / Neutral / Negative / Insufficient Data
    key_metric: str  # supporting figure or n/a


@dataclass
class StrategyClassification:
    """Final strategy fit appended to the Section 6 verdict (feature 004)."""

    label: str  # Compounder / GARP / Momentum / Income / Value / Avoid / Mixed
    rationale: str
    triggers: list[str] = field(default_factory=list)