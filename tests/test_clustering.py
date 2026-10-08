"""
Unit tests for ProductClusterEngine: price distributions and abundance-scarcity indexing.
"""
import pandas as pd
from engine.clustering import ProductClusterEngine

def test_product_clustering_and_distributions():
    engine = ProductClusterEngine()

    mock_deals = pd.DataFrame([
        {
            "jumia_title": "120W Portable Car Vacuum Cleaner Cordless Handheld",
            "jiji_title": "Cordless Car Vacuum Cleaner 120W Handheld",
            "category": "Auto Accessories",
            "jumia_price": 2500.0,
            "jiji_price": 1000.0,
            "jumia_reviews": 5,
            "jumia_rating": 4.1,
            "jumia_express": False,
            "jumia_url": "https://jumia.co.ke/v1",
            "jiji_url": "https://jiji.co.ke/adv1",
            "jumia_image": "img1.jpg",
            "jiji_image": "img2.jpg",
            "jiji_region": "Nairobi CBD",
            "jiji_location": "River Road",
            "jiji_phone": "0712345678"
        },
        {
            "jumia_title": "120W Portable Car Vacuum Cleaner High Power Suction",
            "jiji_title": "Portable Vacuum Cleaner 120W for Car and Home",
            "category": "Auto Accessories",
            "jumia_price": 3200.0,
            "jiji_price": 850.0,
            "jumia_reviews": 2,
            "jumia_rating": 4.0,
            "jumia_express": False,
            "jumia_url": "https://jumia.co.ke/v2",
            "jiji_url": "https://jiji.co.ke/adv2",
            "jumia_image": "img1.jpg",
            "jiji_image": "img3.jpg",
            "jiji_region": "Kamukunji",
            "jiji_location": "Nairobi",
            "jiji_phone": "0798765432"
        },
        {
            "jumia_title": "120W Portable Car Vacuum Cleaner Wet and Dry",
            "jiji_title": "Car Vacuum Cleaner 120W Rechargeable",
            "category": "Auto Accessories",
            "jumia_price": 2800.0,
            "jiji_price": 950.0,
            "jumia_reviews": 1,
            "jumia_rating": 4.5,
            "jumia_express": False,
            "jumia_url": "https://jumia.co.ke/v3",
            "jiji_url": "https://jiji.co.ke/adv3",
            "jumia_image": "img1.jpg",
            "jiji_image": "img4.jpg",
            "jiji_region": "Eastleigh",
            "jiji_location": "Nairobi",
            "jiji_phone": "0755555555"
        }
    ])

    clusters = engine.analyze_clusters(mock_deals)
    assert len(clusters) == 1
    c = clusters[0]

    # Check Jumia price distributions: [2500, 3200, 2800]
    assert c["jumia_min"] == 2500.0
    assert c["jumia_max"] == 3200.0
    assert c["jumia_median"] == 2800.0
    assert c["jumia_avg"] == 2833.33

    # Check Jiji wholesale distributions: [1000, 850, 950]
    assert c["jiji_min"] == 850.0
    assert c["jiji_max"] == 1000.0
    assert c["jiji_median"] == 950.0

    # Check Supply vs Demand
    assert c["jumia_sellers_count"] == 3
    assert c["jiji_suppliers_count"] == 3
    assert c["supply_demand_ratio"] == 1.0

    # Best supplier should be the 850 KSh one
    assert c["best_supplier"]["price"] == 850.0
    assert c["net_profit"] > 1000.0
