"""
Dynamic facet extraction and listing relevance scoring.

Flow:
    1. `extract_query_facets(query)` → one LLM call, produces a structured spec
       of the facets implied by the query (brand, model, storage, color, ...),
       each tagged with a weight and optional `required` flag. Cached per query.
    2. `score_listing(spec, title, price, max_price)` → deterministic match
       between the spec and a listing title. No LLM per listing.
    3. `price_score(...)` + `combine_scores(...)` → fold relevance with
       price attractiveness into a final rank score in [0, 1].
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

from litellm import acompletion
from loguru import logger

from backend import db
from backend.config import settings


# ---------- data shapes ----------


@dataclass
class Facet:
    key: str
    value: str
    weight: float = 0.25
    required: bool = False


@dataclass
class FacetSpec:
    query: str
    facets: list[Facet]

    def to_json(self) -> str:
        return json.dumps(
            {
                "query": self.query,
                "facets": [asdict(f) for f in self.facets],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> FacetSpec:
        d = json.loads(text)
        return cls(
            query=d["query"],
            facets=[Facet(**f) for f in d["facets"]],
        )


@dataclass
class MatchResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    rejected: bool = False
    reject_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- facet extraction (LLM) ----------


def _configure_llm_env() -> None:
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key


_FACET_PROMPT = """Extract structured facets from this used-item search query: "{query}"

Return ONLY a JSON object of this exact shape:
{{"facets": [{{"key": "<snake_case>", "value": "<string>", "weight": <0..1>, "required": <bool>}}, ...]}}

Guidelines:
- keys are lowercase snake_case. Typical keys: brand, model, storage, ram, size, color, condition, year, generation, material.
- value is a specific desired value. Examples: "iPhone 15 Pro", "256GB", "black", "good", "M2", "queen".
- weights should roughly sum to 1.0 across all facets; more-defining facets get higher weights.
- required=true ONLY for identity-defining facets (the specific model/size that would make the listing a totally different item).
- 2 to 6 facets. Skip vague descriptors ("cheap", "nice"). Skip facets not implied by the query.

Return the JSON only. No prose. No markdown fences."""


_FIRST_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    """Extract the first JSON object from an LLM response.

    Handles: raw JSON, fenced code blocks (```json ... ```), and prose-wrapped
    responses ("Here is the JSON: {...}"). Leaves parsing to the caller.
    """
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            return inner.strip()
    match = _FIRST_JSON_OBJECT.search(text)
    return match.group(0) if match else text


async def extract_query_facets(query: str, force_refresh: bool = False) -> FacetSpec:
    """Extract a facet spec from a query string. Cached by normalized query."""
    query_norm = query.strip().lower()

    if not force_refresh:
        cached = await db.get_cached_facets(query_norm)
        if cached:
            logger.debug("Facet cache hit for '{}'", query_norm)
            return FacetSpec.from_json(cached["facets_json"])

    _configure_llm_env()
    model = settings.resolved_llm_model
    logger.info("Extracting facets for '{}' via {}", query, model)

    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": _FACET_PROMPT.format(query=query)}],
        max_tokens=400,
        timeout=30,
    )
    raw = response.choices[0].message.content
    text = _extract_json(raw)
    parsed = json.loads(text)

    facets = [
        Facet(
            key=str(f["key"]).strip().lower(),
            value=str(f["value"]).strip(),
            weight=float(f.get("weight", 0.25)),
            required=bool(f.get("required", False)),
        )
        for f in parsed["facets"]
        if f.get("value")
    ]
    spec = FacetSpec(query=query, facets=facets)
    await db.save_facets_cache(query_norm, spec.to_json())
    logger.info(
        "Extracted {} facets for '{}': {}",
        len(facets),
        query,
        [(f.key, f.value, "req" if f.required else f"w={f.weight:.2f}") for f in facets],
    )
    return spec


# ---------- deterministic scoring ----------


_WORD = re.compile(r"[A-Za-z0-9]+")


def _tokens(s: str) -> list[str]:
    return [t for t in _WORD.findall(s.lower())]


def _facet_matches(value: str, title_lower: str, title_tokens: set[str]) -> bool:
    v = value.strip().lower()
    if not v:
        return False
    # Direct substring (best for multi-word values and "256gb"-style)
    if v in title_lower:
        return True
    # Compact form: "256 gb" → "256gb"
    v_compact = re.sub(r"\s+", "", v)
    t_compact = re.sub(r"\s+", "", title_lower)
    if v_compact and v_compact in t_compact:
        return True
    # Token-wise AND (handles reordered multi-word values)
    v_toks = _tokens(v)
    if v_toks and all(tok in title_tokens for tok in v_toks):
        return True
    return False


def score_listing(
    spec: FacetSpec,
    title: str,
    price: float | None = None,
    max_price: float | None = None,
) -> MatchResult:
    """Deterministic score of a listing title against a FacetSpec."""
    if not spec.facets:
        return MatchResult(score=0.0)

    title_lower = title.lower()
    title_tokens = set(_tokens(title))

    matched: list[str] = []
    missed: list[str] = []
    weighted_hit = 0.0
    total_weight = 0.0
    rejected = False
    reject_reason: str | None = None

    for facet in spec.facets:
        total_weight += facet.weight
        if _facet_matches(facet.value, title_lower, title_tokens):
            matched.append(facet.key)
            weighted_hit += facet.weight
        else:
            missed.append(facet.key)
            if facet.required:
                rejected = True
                reject_reason = f"missing required facet: {facet.key}={facet.value}"

    if max_price is not None and price is not None and price > max_price:
        rejected = True
        reject_reason = f"price ${price:.0f} over cap ${max_price:.0f}"

    score = (weighted_hit / total_weight) if total_weight > 0 else 0.0
    if rejected:
        score = 0.0

    return MatchResult(
        score=round(score, 3),
        matched=matched,
        missed=missed,
        rejected=rejected,
        reject_reason=reject_reason,
    )


# ---------- price + combined ranking ----------


def price_score(listing_price: float, fair_price: float | None) -> float:
    """Attractiveness of the price vs fair price, in [0, 1]. 0.5 when unknown."""
    if fair_price is None or fair_price <= 0:
        return 0.5  # neutral — can't evaluate
    ratio = listing_price / fair_price
    great = settings.great_deal_threshold  # e.g. 0.60
    if ratio <= great:
        return 1.0
    if ratio >= 1.0:
        return 0.0
    # Linear falloff from great→fair
    return round((1.0 - ratio) / (1.0 - great), 3)


def combine_scores(relevance: float | None, price_sc: float) -> float:
    """final = relevance × price. Pass-through price when relevance missing."""
    if relevance is None:
        return round(price_sc, 3)
    return round(relevance * price_sc, 3)
