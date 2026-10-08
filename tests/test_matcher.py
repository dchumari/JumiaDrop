"""
Unit tests for ProductMatcher spec extraction and fuzzy matching.
"""
from engine.matcher import ProductMatcher

def test_spec_extraction():
    matcher = ProductMatcher()
    specs1 = matcher.extract_specs("WakeView 48V Cordless 3-in-1 Blower Vacuum Cleaner 120W")
    assert specs1.get("voltage") == "48v"
    assert specs1.get("wattage") == "120w"
    assert specs1.get("multi") == "3in1"

    specs2 = matcher.extract_specs("Power Bank 20000mAh Portable Charger 22.5W")
    assert specs2.get("battery") == "20000mah"

def test_spec_conflict_rejection():
    matcher = ProductMatcher()
    # 48V vs 12V should reject or score very low
    score, meta = matcher.compute_match_confidence(
        jumia_title="Portable High Pressure Car Washer 48V Cordless Spray",
        jiji_title="Car Washer Portable Spray Gun 12V with Hose",
        jumia_price=3500,
        jiji_price=1500
    )
    assert meta.get("reason") == "spec_conflict"
    assert score <= 10.0

def test_matching_compatible_products():
    matcher = ProductMatcher()
    score, meta = matcher.compute_match_confidence(
        jumia_title="WakeView Cordless Handheld Car Vacuum Cleaner High Power",
        jiji_title="Cordless Car Vacuum Cleaner Handheld High Power",
        jumia_price=2800,
        jiji_price=1200
    )
    assert score >= 70.0
