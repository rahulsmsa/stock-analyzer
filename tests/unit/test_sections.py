"""Tests for the 10-K section parser."""

from stock_analyzer.data.sections import extract_item_1a, extract_item_7

_LONG_TEXT = "This is a long section with substantive content. " * 25


def test_extract_item_1a():
    html = (
        "<html><body><h1>Item 1A. Risk Factors</h1><p>"
        + _LONG_TEXT
        + "</p><h1>Item 1B.</h1><p>x</p></body></html>"
    )
    text = extract_item_1a(html)
    assert text is not None
    assert "competition" in text or "substantive" in text


def test_extract_item_7():
    html = (
        "<html><body><h1>Item 7. Management's Discussion and Analysis</h1><p>"
        + _LONG_TEXT
        + "</p><h1>Item 8.</h1><p>x</p></body></html>"
    )
    text = extract_item_7(html)
    assert text is not None
    assert "substantive" in text


def test_extract_missing():
    html = "<html><body><h1>Item 1.</h1><p>Business overview.</p></body></html>"
    assert extract_item_1a(html) is None
    assert extract_item_7(html) is None


def test_extract_below_floor_returns_none():
    html = "<html><body><h1>Item 1A. Risk Factors</h1><p>Short.</p><h1>Item 1B.</h1></body></html>"
    assert extract_item_1a(html) is None