"""
Financial calculator and competition scoring for Jumia Kenya dropshipping.
"""
from typing import Dict, Any, Optional
from config import (
    DEFAULT_CATEGORY_COMMISSIONS,
    VAT_ON_COMMISSION,
    DEFAULT_PACKAGING_COST_KES,
    DEFAULT_BODA_RUNNER_COST_KES
)

class ProfitCalculator:
    def __init__(
        self,
        category_commissions: Optional[Dict[str, float]] = None,
        vat_rate: float = VAT_ON_COMMISSION,
        default_packaging: float = DEFAULT_PACKAGING_COST_KES,
        default_boda: float = DEFAULT_BODA_RUNNER_COST_KES
    ):
        self.category_commissions = category_commissions or DEFAULT_CATEGORY_COMMISSIONS
        self.vat_rate = vat_rate
        self.default_packaging = default_packaging
        self.default_boda = default_boda

    def get_commission_rate(self, category: str) -> float:
        """Get Jumia seller commission rate for a category."""
        return self.category_commissions.get(category, self.category_commissions.get("Other", 0.12))

    def calculate_deal_finances(
        self,
        jumia_price: float,
        jiji_price: float,
        category: str = "General",
        custom_packaging: Optional[float] = None,
        custom_boda: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Compute full unit economics for sourcing from Jiji and fulfilling on Jumia Kenya.
        """
        packaging = custom_packaging if custom_packaging is not None else self.default_packaging
        boda = custom_boda if custom_boda is not None else self.default_boda
        comm_rate = self.get_commission_rate(category)

        # 1. Jumia Seller Commission
        jumia_commission = round(jumia_price * comm_rate, 2)

        # 2. 16% VAT on Jumia Commission
        vat_amount = round(jumia_commission * self.vat_rate, 2)

        # 3. Total Sourcing & Fulfillment Costs
        total_deductions = round(jumia_commission + vat_amount + packaging + boda, 2)
        total_cost = round(jiji_price + total_deductions, 2)

        # 4. Net Profit & Margin
        net_profit = round(jumia_price - total_cost, 2)
        margin_pct = round((net_profit / jumia_price * 100), 2) if jumia_price > 0 else 0.0
        roi_pct = round((net_profit / jiji_price * 100), 2) if jiji_price > 0 else 0.0
        markup_multiplier = round(jumia_price / jiji_price, 2) if jiji_price > 0 else 0.0

        return {
            "jumia_price": jumia_price,
            "jiji_price": jiji_price,
            "commission_rate": comm_rate,
            "jumia_commission": jumia_commission,
            "vat_amount": vat_amount,
            "packaging_cost": packaging,
            "boda_cost": boda,
            "total_deductions": total_deductions,
            "total_cost": total_cost,
            "net_profit": net_profit,
            "margin_pct": margin_pct,
            "roi_pct": roi_pct,
            "markup_multiplier": markup_multiplier
        }

    def compute_competition_score(
        self,
        reviews_count: int,
        rating: float = 0.0,
        is_express: bool = False
    ) -> float:
        """
        Score competition from 0 (heavily saturated) to 100 (uncontested niche).
        Lower reviews = higher opportunity for a new seller to rank on Jumia.
        """
        if reviews_count == 0:
            score = 100.0
        elif reviews_count <= 5:
            score = 90.0
        elif reviews_count <= 15:
            score = 80.0
        elif reviews_count <= 35:
            score = 65.0
        elif reviews_count <= 80:
            score = 45.0
        elif reviews_count <= 150:
            score = 30.0
        else:
            score = 15.0

        # Opportunity bonus if competitors have poor ratings (below 3.8 stars)
        if 0 < rating < 3.8:
            score = min(100.0, score + 10.0)

        # Competitor penalty if dominated by Jumia Express
        if is_express:
            score = max(5.0, score - 15.0)

        return round(score, 1)

    def compute_opportunity_score(
        self,
        net_profit: float,
        margin_pct: float,
        competition_score: float,
        confidence_score: float
    ) -> float:
        """
        Composite Opportunity Score (0 to 100) weighting:
        - 35% Margin %
        - 25% Net Profit in KES
        - 25% Competition level
        - 15% Match confidence
        """
        if net_profit <= 0 or margin_pct <= 0:
            return 0.0

        # Margin normalized: 0% to 50%+
        norm_margin = min(100.0, (margin_pct / 50.0) * 100.0)

        # Net profit normalized: KES 0 to KES 2,500+
        norm_profit = min(100.0, (net_profit / 2500.0) * 100.0)

        composite = (
            (norm_margin * 0.35) +
            (norm_profit * 0.25) +
            (competition_score * 0.25) +
            (confidence_score * 0.15)
        )

        return round(max(0.0, min(100.0, composite)), 1)
