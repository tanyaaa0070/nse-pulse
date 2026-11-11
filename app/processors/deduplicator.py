"""Duplicate detection and deduplication service.

Implements hash-based duplicate identification and tracking across records.
Preserves records with audit logging rather than dropping without trace.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger("nse_pulse.deduplicator")


class DeduplicationReport:
    """Summary of deduplication execution."""

    def __init__(
        self,
        dataset_name: str,
        original_count: int,
        deduplicated_count: int,
        duplicate_count: int,
        duplicate_records: List[Dict[str, Any]],
    ) -> None:
        self.dataset_name = dataset_name
        self.original_count = original_count
        self.deduplicated_count = deduplicated_count
        self.duplicate_count = duplicate_count
        self.duplicate_records = duplicate_records

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "original_count": self.original_count,
            "deduplicated_count": self.deduplicated_count,
            "duplicate_count": self.duplicate_count,
            "duplicate_rate_pct": round(
                (self.duplicate_count / self.original_count * 100.0)
                if self.original_count > 0
                else 0.0,
                2,
            ),
            "sample_duplicates": self.duplicate_records[:5],
        }


class DuplicateDetector:
    """Detects and isolates duplicate records within and across datasets."""

    @staticmethod
    def compute_record_hash(record: Dict[str, Any], key_fields: List[str]) -> str:
        """Generate a deterministic SHA-256 hash for record's key fields."""
        normalized_dict = {
            k: str(record.get(k, "")).strip().upper() for k in sorted(key_fields)
        }
        serialized = json.dumps(normalized_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def deduplicate(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        key_columns: Optional[List[str]] = None,
        keep: str = "first",
    ) -> Tuple[pd.DataFrame, DeduplicationReport]:
        """Detect and remove duplicate rows based on key columns.

        Args:
            df: Target DataFrame.
            dataset_name: Identifier for reporting.
            key_columns: Columns defining record identity (default: ['symbol']).
            keep: Which duplicate to keep ('first', 'last', or False).

        Returns:
            Tuple of (deduplicated DataFrame, DeduplicationReport).
        """
        if df.empty:
            report = DeduplicationReport(
                dataset_name=dataset_name,
                original_count=0,
                deduplicated_count=0,
                duplicate_count=0,
                duplicate_records=[],
            )
            return df.copy(), report

        if key_columns is None:
            key_columns = ["symbol"]

        active_keys = [c for c in key_columns if c in df.columns]
        if not active_keys:
            active_keys = list(df.columns)

        original_count = len(df)
        is_duplicate = df.duplicated(subset=active_keys, keep=keep)
        duplicate_indices = df.index[is_duplicate].tolist()
        duplicate_count = len(duplicate_indices)

        duplicate_samples = []
        for idx in duplicate_indices:
            row_dict = df.loc[idx].to_dict()
            duplicate_samples.append(row_dict)

        deduped_df = df.drop(index=duplicate_indices).reset_index(drop=True)

        if duplicate_count > 0:
            logger.warning(
                "Deduplicated '%s': removed %d duplicates out of %d rows using keys %s",
                dataset_name,
                duplicate_count,
                original_count,
                active_keys,
            )
        else:
            logger.debug(
                "No duplicates found in '%s' across %d rows",
                dataset_name,
                original_count,
            )

        report = DeduplicationReport(
            dataset_name=dataset_name,
            original_count=original_count,
            deduplicated_count=len(deduped_df),
            duplicate_count=duplicate_count,
            duplicate_records=duplicate_samples,
        )

        return deduped_df, report

