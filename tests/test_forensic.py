"""Tests for the forensic engine (Step 2)."""

from stock_analyzer.models import ForensicResult


def test_forensic_defaults_empty():
    f = ForensicResult()
    assert f.customer_concentration == []
    assert f.accounting_changes == []