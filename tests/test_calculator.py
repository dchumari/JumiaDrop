"""
Unit tests for ProfitCalculator and competition scoring.
"""
from engine.calculator import ProfitCalculator

def test_profit_calculation():
    calc = ProfitCalculator(default_packaging=30.0, default_boda=150.0)
    # Jumia Price KES 3,000, Jiji Price KES 1,500, Category Home & Kitchen (14%)
    res = calc.calculate_deal_finances(
        jumia_price=3000.0,
        jiji_price=1500.0,
        category="Home & Kitchen"
    )

    # 14% commission on 3000 = 420
    assert res["jumia_commission"] == 420.0
    # 16% VAT on 420 = 67.20
    assert res["vat_amount"] == 67.20
    # Packaging 30, Boda 150
    # Total deductions = 420 + 67.20 + 30 + 150 = 667.20
    assert res["total_deductions"] == 667.20
    # Total cost = 1500 + 667.20 = 2167.20
    assert res["total_cost"] == 2167.20
    # Net profit = 3000 - 2167.20 = 832.80
    assert res["net_profit"] == 832.80
    # Margin % = (832.80 / 3000) * 100 = 27.76%
    assert res["margin_pct"] == 27.76

def test_competition_scoring():
    calc = ProfitCalculator()
    # 0 reviews = 100
    score_uncontested = calc.compute_competition_score(reviews_count=0)
    assert score_uncontested == 100.0

    # High reviews = low score
    score_saturated = calc.compute_competition_score(reviews_count=200)
    assert score_saturated <= 25.0

    # Jumia express penalty
    score_regular = calc.compute_competition_score(reviews_count=20, is_express=False)
    score_express = calc.compute_competition_score(reviews_count=20, is_express=True)
    assert score_express < score_regular

def test_opportunity_score():
    calc = ProfitCalculator()
    opp = calc.compute_opportunity_score(
        net_profit=850.0,
        margin_pct=32.0,
        competition_score=80.0,
        confidence_score=75.0
    )
    assert 0.0 <= opp <= 100.0
    assert opp > 50.0  # High opportunity
