"""3M Model scoring engines (Market / Model / Management)."""


from .thesis import ConfidenceGrade, PropertyProfile, ScoreResult, ThesisConfig


class MarketScorer:
    """Score properties based on Market fundamentals (30% weight)."""

    def score(self, property: PropertyProfile, thesis: ThesisConfig) -> tuple[float, dict[str, float]]:
        """
        Calculate market score (0–100) based on:
        - Employment growth (25 points)
        - Population growth (15 points)
        - Cap-rate spread (30 points)
        - Employment anchor strength (30 points)

        Returns: (score, breakdown)
        """
        breakdown = {}
        total = 0.0

        # Employment growth (25 points) — linear scale
        if property.employment_growth_yoy is not None:
            growth = property.employment_growth_yoy
            if growth < 0.02:
                emp_score = 0.0
            elif growth <= 0.02:
                emp_score = 10.0
            elif growth <= 0.03:
                emp_score = 10.0 + (growth - 0.02) / (0.03 - 0.02) * 7.0
            elif growth <= 0.04:
                emp_score = 17.0 + (growth - 0.03) / (0.04 - 0.03) * 8.0
            else:
                emp_score = 25.0
            breakdown['employment_growth'] = min(25.0, emp_score)
            total += min(25.0, emp_score)
        else:
            breakdown['employment_growth'] = 0.0

        # Population growth (15 points) — linear scale
        if property.population_growth_yoy is not None:
            growth = property.population_growth_yoy
            if growth < 0.015:
                pop_score = 0.0
            elif growth <= 0.015:
                pop_score = 6.0
            elif growth <= 0.020:
                pop_score = 6.0 + (growth - 0.015) / (0.020 - 0.015) * 4.0
            elif growth <= 0.025:
                pop_score = 10.0 + (growth - 0.020) / (0.025 - 0.020) * 5.0
            else:
                pop_score = 15.0
            breakdown['population_growth'] = min(15.0, pop_score)
            total += min(15.0, pop_score)
        else:
            breakdown['population_growth'] = 0.0

        # Cap-rate spread (30 points) — vs. 6% national avg
        national_avg_cap_rate = 0.06
        if property.market_cap_rate:
            spread_bps = int((property.market_cap_rate - national_avg_cap_rate) * 10_000)
            if spread_bps < 100:
                cap_score = 0.0
            elif spread_bps < 200:
                cap_score = 10.0 * (spread_bps - 100) / 100
            elif spread_bps < 300:
                cap_score = 20.0 + 10.0 * (spread_bps - 200) / 100
            else:
                cap_score = 30.0
            breakdown['cap_rate_spread'] = min(30.0, cap_score)
            total += min(30.0, cap_score)
        else:
            breakdown['cap_rate_spread'] = 15.0  # Default neutral score
            total += 15.0

        # Employment anchor strength (30 points)
        anchor_score = 0.0
        if property.employment_anchors and thesis.employment_anchor_types:
            matched = sum(1 for anchor in property.employment_anchors if anchor in thesis.employment_anchor_types)
            if matched == 0:
                anchor_score = 0.0
            elif matched == 1:
                anchor_score = 15.0
            else:
                anchor_score = 30.0
        breakdown['employment_anchor_strength'] = anchor_score
        total += anchor_score

        return min(100.0, total), breakdown


class ModelScorer:
    """Score properties based on Model (value-add opportunity) (40% weight)."""

    def score(self, property: PropertyProfile, thesis: ThesisConfig) -> tuple[float, dict[str, float]]:
        """
        Calculate model score (0–100) based on:
        - Unit count fit (20 points)
        - Property class (20 points)
        - Occupancy gap (20 points)
        - Expense ratio gap (20 points)
        - Rent upside (20 points)

        Returns: (score, breakdown)
        """
        breakdown = {}
        total = 0.0

        # Unit count (20 points) — 70–300 in range, sweet spot 150–250
        if thesis.min_units <= property.units <= thesis.max_units:
            units_score = 20.0
        elif 50 <= property.units < thesis.min_units:
            units_score = 10.0  # Slightly below range
        elif property.units > thesis.max_units <= property.units <= 400:
            units_score = 10.0  # Slightly above range
        else:
            units_score = 0.0
        breakdown['unit_count'] = units_score
        total += units_score

        # Property class (20 points) — B/B- preferred
        preferred_classes = ['B', 'B-', 'B+']
        if property.property_class in preferred_classes:
            class_score = 20.0
        else:
            class_score = 0.0
        breakdown['property_class'] = class_score
        total += class_score

        # Occupancy (20 points) — 80–95% is sweet spot (below-market upside signal)
        if thesis.min_occupancy <= property.occupancy <= thesis.max_occupancy:
            occupancy_score = 20.0
        elif 0.75 <= property.occupancy < thesis.min_occupancy:
            occupancy_score = 10.0  # Below target, higher risk
        elif property.occupancy > thesis.max_occupancy <= 0.99:
            occupancy_score = 10.0  # Already optimized, limited upside
        else:
            occupancy_score = 0.0
        breakdown['occupancy'] = occupancy_score
        total += occupancy_score

        # Expense ratio gap (20 points) — property ABOVE benchmark
        expense_gap = property.expense_ratio - property.market_expense_ratio
        if expense_gap > 0.05:
            expense_score = 20.0  # >5% above benchmark = clear upside
        elif expense_gap >= 0.03:
            expense_score = 10.0  # 3–5% = moderate upside
        elif expense_gap > 0:
            expense_score = 5.0   # 0–2% = minimal upside
        else:
            expense_score = 0.0   # At or below benchmark = no upside
        breakdown['expense_ratio_gap'] = expense_score
        total += expense_score

        # Rent upside (20 points) — below market rent = upside
        rent_gap = property.rent_gap_pct()
        if rent_gap > 0:
            rent_score = 20.0  # Below market = upside
        elif rent_gap < -0.02:
            rent_score = 0.0   # Above market = no upside
        else:
            rent_score = 10.0  # At or slightly above market = limited upside
        breakdown['rent_upside'] = rent_score
        total += rent_score

        return min(100.0, total), breakdown


class ManagementScorer:
    """Score properties based on Management & integration (30% weight)."""

    def score(self, property: PropertyProfile, thesis: ThesisConfig) -> tuple[float, dict[str, float]]:
        """
        Calculate management score (0–100) based on:
        - PM type (20 points) — third-party preferred
        - First Communities integration fit (20 points)
        - Lory rebranding applicability (20 points)
        - Operator/team track record (20 points)

        Returns: (score, breakdown)
        """
        breakdown = {}
        total = 0.0

        # PM type (20 points) — third-party preferred (replaceable)
        if property.management_type:
            if 'third' in property.management_type.lower():
                pm_score = 20.0  # Third-party = replaceable
            elif 'owner' in property.management_type.lower():
                if 'experienced' in property.management_type.lower():
                    pm_score = 10.0  # Owner-managed but experienced
                else:
                    pm_score = 5.0   # Owner-managed, inexperienced
            else:
                pm_score = 0.0   # Complex arrangement
        else:
            pm_score = 15.0  # Unknown = neutral
        breakdown['pm_type'] = pm_score
        total += pm_score

        # First Communities integration fit (20 points)
        # Criteria: multifamily, 70–300 units, standard structure, mid-market secondary
        fc_criteria_met = 0
        if property.units >= 70 and property.units <= 300:
            fc_criteria_met += 1  # Size fits
        if property.property_class in ['B', 'B-', 'B+']:
            fc_criteria_met += 1  # Class fits Lexerd model
        if property.state in ['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS']:
            fc_criteria_met += 1  # Geographic focus

        if fc_criteria_met >= 3:
            fc_score = 20.0  # Excellent fit
        elif fc_criteria_met == 2:
            fc_score = 15.0  # Good fit
        elif fc_criteria_met == 1:
            fc_score = 10.0  # Moderate fit
        else:
            fc_score = 0.0   # Poor fit
        breakdown['first_communities_integration'] = fc_score
        total += fc_score

        # Lory rebranding playbook (20 points)
        # Criteria: Class B/B-, 70–300 units, third-party PM, secondary market
        lory_criteria_met = 0
        if property.property_class in ['B', 'B-', 'B+']:
            lory_criteria_met += 1  # Class fits
        if property.units >= 70 and property.units <= 300:
            lory_criteria_met += 1  # Size fits
        if property.management_type and 'third' in property.management_type.lower():
            lory_criteria_met += 1  # PM replaceable
        if property.state in ['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS']:
            lory_criteria_met += 1  # Secondary market

        if lory_criteria_met >= 4:
            lory_score = 20.0  # Excellent fit (all criteria)
        elif lory_criteria_met == 3:
            lory_score = 15.0  # Good fit
        elif lory_criteria_met == 2:
            lory_score = 10.0  # Moderate fit
        else:
            lory_score = 0.0   # Poor fit
        breakdown['lory_rebranding'] = lory_score
        total += lory_score

        # Operator track record (20 points)
        # (Simplified; real logic would check Lexerd portfolio history)
        # Assumption: Lexerd-backed operator = good track record
        operator_score = 15.0  # Default assumption (no track record data)
        breakdown['operator_track_record'] = operator_score
        total += operator_score

        return min(100.0, total), breakdown


class FinalScorer:
    """Weighted final fit score from 3M Model (Market 30%, Model 40%, Management 30%)."""

    def __init__(self):
        self.market_scorer = MarketScorer()
        self.model_scorer = ModelScorer()
        self.management_scorer = ManagementScorer()

    def score(self, property: PropertyProfile, thesis: ThesisConfig) -> ScoreResult:
        """
        Calculate final fit score and confidence grade.

        Returns: ScoreResult with breakdown and confidence grade.
        """
        market_score, market_breakdown = self.market_scorer.score(property, thesis)
        model_score, model_breakdown = self.model_scorer.score(property, thesis)
        management_score, management_breakdown = self.management_scorer.score(property, thesis)

        # Normalize weights to sum to 1.0
        total_weight = thesis.market_weight + thesis.model_weight + thesis.management_weight
        if total_weight == 0:
            total_weight = 1.0  # Avoid division by zero
        market_weight = thesis.market_weight / total_weight
        model_weight = thesis.model_weight / total_weight
        management_weight = thesis.management_weight / total_weight

        # Weighted final score
        final_fit_score = (
            (market_score * market_weight) +
            (model_score * model_weight) +
            (management_score * management_weight)
        )

        # Confidence grade
        if final_fit_score >= 90:
            confidence_grade = ConfidenceGrade.A
        elif final_fit_score >= 75:
            confidence_grade = ConfidenceGrade.B
        elif final_fit_score >= 60:
            confidence_grade = ConfidenceGrade.C
        else:
            confidence_grade = ConfidenceGrade.D

        # Fit rationale
        fit_rationale = self._build_rationale(property, final_fit_score, confidence_grade)

        # Key strengths & weaknesses
        key_strengths, key_weaknesses = self._extract_insights(
            property, thesis, market_breakdown, model_breakdown, management_breakdown
        )

        return ScoreResult(
            property_id=property.property_id,
            market_score=market_score,
            model_score=model_score,
            management_score=management_score,
            final_fit_score=final_fit_score,
            confidence_grade=confidence_grade,
            market_breakdown=market_breakdown,
            model_breakdown=model_breakdown,
            management_breakdown=management_breakdown,
            fit_rationale=fit_rationale,
            key_strengths=key_strengths,
            key_weaknesses=key_weaknesses,
        )

    @staticmethod
    def _build_rationale(property: PropertyProfile, score: float, grade: ConfidenceGrade) -> str:
        """Human-readable explanation of the fit score."""
        if grade == ConfidenceGrade.A:
            return f"{property.property_name} is a strong fit for Lexerd's thesis ({score:.1f}/100). Excellent market, model, and management alignment."
        elif grade == ConfidenceGrade.B:
            return f"{property.property_name} is a good fit ({score:.1f}/100). Solid opportunity with minor adjustments needed."
        elif grade == ConfidenceGrade.C:
            return f"{property.property_name} shows moderate fit ({score:.1f}/100). Requires deeper due diligence to assess viability."
        else:
            return f"{property.property_name} is a weak fit ({score:.1f}/100). Does not align well with Lexerd's thesis; recommend passing."

    @staticmethod
    def _extract_insights(property: PropertyProfile, thesis: ThesisConfig, market_bd: dict, model_bd: dict, mgmt_bd: dict) -> tuple[list[str], list[str]]:
        """Extract key strengths and weaknesses from scoring breakdown."""
        strengths = []
        weaknesses = []

        # Market insights
        if market_bd.get('employment_growth', 0) > 15:
            strengths.append("Strong employment growth anchor")
        if market_bd.get('cap_rate_spread', 0) > 20:
            strengths.append("Attractive valuation vs. national peers")

        # Model insights
        if model_bd.get('occupancy', 0) > 15:
            strengths.append("Clear occupancy upside signal")
        if model_bd.get('expense_ratio_gap', 0) > 15:
            strengths.append("Significant operational improvement opportunity")
        if model_bd.get('unit_count', 0) == 0:
            weaknesses.append("Unit count outside Lexerd's sweet spot")

        # Management insights
        if mgmt_bd.get('lory_rebranding', 0) > 15:
            strengths.append("Good fit for Lory value-add playbook")
        if mgmt_bd.get('pm_type', 0) < 10:
            weaknesses.append("Owner-managed; PM transition risk")

        return strengths or ["Moderate fit"], weaknesses or ["None major"]
