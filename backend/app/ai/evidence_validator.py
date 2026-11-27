from typing import List, Tuple
from app.ai.output_schema import AIAnalysisOutput


class EvidenceValidator:
    @staticmethod
    def validate_evidence_keys(
        output: AIAnalysisOutput,
        evidence_catalog: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Verify that all evidence keys referenced in insights, tradeoffs,
        and recommendations exist in the evidence catalog.
        Returns (is_valid, list_of_invalid_keys).
        """
        catalog_set = set(evidence_catalog)
        invalid_keys = []

        # Check operational insights
        for idx, insight in enumerate(output.operational_insights):
            if not insight.evidence:
                invalid_keys.append(f"insight[{idx}] has empty evidence")
            for key in insight.evidence:
                if key not in catalog_set:
                    invalid_keys.append(f"insight[{idx}]: {key}")

        # Check tradeoffs
        for idx, tradeoff in enumerate(output.optimization_interpretation.tradeoffs):
            for key in tradeoff.evidence:
                if key not in catalog_set:
                    invalid_keys.append(f"tradeoff[{idx}]: {key}")

        # Check recommendations
        for idx, rec in enumerate(output.recommendations):
            if not rec.evidence:
                invalid_keys.append(f"recommendation[{idx}] has empty evidence")
            for key in rec.evidence:
                if key not in catalog_set:
                    invalid_keys.append(f"recommendation[{idx}]: {key}")

        is_valid = len(invalid_keys) == 0
        return is_valid, invalid_keys
