import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from b2b_domain.source_adapters import RawRecord, RawScalar


class CanonicalEntity(StrEnum):
    CUSTOMERS = "customers"
    PRODUCTS = "products"
    INVOICES = "invoices"
    INVOICE_ITEMS = "invoice_items"
    RETURNS = "returns"
    INVENTORY = "inventory"


@dataclass(frozen=True)
class SourceMapping:
    source_name: str
    entity: CanonicalEntity
    fields: Mapping[str, str]

    def __post_init__(self) -> None:
        targets = tuple(self.fields.values())
        if len(targets) != len(set(targets)):
            raise ValueError("Canonical target fields must be unique within a source mapping")


@dataclass(frozen=True)
class CanonicalRecord:
    entity: CanonicalEntity
    source_name: str
    original_row_number: int
    values: Mapping[str, RawScalar]


@dataclass(frozen=True)
class EntityCandidate:
    left_id: str
    right_id: str
    normalized_name: str
    similarity: float
    edit_similarity: float
    token_similarity: float


def map_record(record: RawRecord, mapping: SourceMapping) -> CanonicalRecord:
    if record.source_name != mapping.source_name:
        raise ValueError(f"Mapping expects {mapping.source_name}, got {record.source_name}")
    missing = set(mapping.fields) - set(record.values)
    if missing:
        raise ValueError(f"Source fields are missing: {', '.join(sorted(missing))}")
    return CanonicalRecord(
        entity=mapping.entity,
        source_name=record.source_name,
        original_row_number=record.original_row_number,
        values={target: record.values[source] for source, target in mapping.fields.items()},
    )


def normalize_entity_name(value: str, abbreviations: Mapping[str, str] | None = None) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    tokens = normalized.split()
    replacements = abbreviations or {}
    return " ".join(replacements.get(token, token) for token in tokens)


def _edit_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_character != right_character),
                )
            )
        previous = current
    return 1 - previous[-1] / max(len(left), len(right))


def _token_similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = set(left.split()), set(right.split())
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def entity_match_candidates(
    entities: list[Mapping[str, RawScalar]],
    *,
    id_field: str,
    name_field: str,
    minimum_similarity: float = 0.9,
) -> tuple[EntityCandidate, ...]:
    candidates: list[EntityCandidate] = []
    prepared = [
        (
            str(entity.get(id_field) or ""),
            normalize_entity_name(str(entity.get(name_field) or "")),
        )
        for entity in entities
    ]
    for index, (left_id, left_name) in enumerate(prepared):
        if not left_id or not left_name:
            continue
        for right_id, right_name in prepared[index + 1 :]:
            if not right_id or not right_name or left_id == right_id:
                continue
            sequence_similarity = SequenceMatcher(None, left_name, right_name).ratio()
            edit_similarity = _edit_similarity(left_name, right_name)
            token_similarity = _token_similarity(left_name, right_name)
            similarity = max(sequence_similarity, edit_similarity, token_similarity)
            if similarity >= minimum_similarity:
                candidates.append(
                    EntityCandidate(
                        left_id,
                        right_id,
                        left_name,
                        round(similarity, 4),
                        round(edit_similarity, 4),
                        round(token_similarity, 4),
                    )
                )
    return tuple(candidates)
