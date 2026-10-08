"""
Unit tests for ReverseSourcingEngine (Blue Ocean unlisted products).
"""
import pytest
from engine.reverse_sourcing import ReverseSourcingEngine

def test_reverse_sourcing_init():
    engine = ReverseSourcingEngine(min_profit_kes=500.0, min_margin_pct=25.0, target_markup=2.2)
    assert engine.target_markup == 2.2
    assert engine.min_profit_kes == 500.0
