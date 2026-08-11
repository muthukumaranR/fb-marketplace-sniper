"""
Facet-based relevance scoring.

A fair price is computed once per watch term, then compared against every
listing FB returns for that term. Without a relevance gate, watching "PS5"
prices controllers and games against a $400 console, and every accessory
looks like a great deal.

One LLM call converts the search term into a structured spec (cached 30 days);
scoring itself is deterministic and offline, so it is cheap and fully testable.
"""

import json
import re
from dataclasses import dataclass, field

from litellm import acompletion
from loguru import logger

from backend import db
from backend.config import settings

# Condition/completeness terms that disqualify a listing regardless of item.
# These describe something that is not a working unit of the thing you want.
DEFAULT_EXCLUSIONS = [
    "for parts", "parts only", "not working", "doesn't work", "does not work",
    "broken", "cracked", "damaged", "as is", "as-is", "repair", "faulty",
    "box only", "empty box", "read description", "locked", "icloud locked",
    "replica", "fake", "clone",
]

FACET_CACHE_DAYS = 30


@dataclass
class Facet:
    """
    One attribute the listing should exhibit, e.g. storage=128GB.

    `values` holds interchangeable spellings — "PlayStation 5" and "PS5" are the
    same attribute, and matching any one of them satisfies the facet. A bare
    string is accepted and wrapped, so Facet("model", "PS5") still works.
    """
    name: str
    values: list[str]
    weight: float = 1.0
    required: bool = False

    def __post_init__(self):
        if isinstance(self.values, str):
            self.values = [self.values]
        self.values = [v for v in (str(v).strip() for v in self.values) if v]

    @property
    def label(self) -> str:
        return "|".join(self.values)

    def matched_value(self, title: str) -> str | None:
        return next((v for v in self.values if matches(v, title)), None)


@dataclass
class FacetSpec:
    """Structured form of a free-text watch term."""
    query: str
    facets: list[Facet] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @property
    def all_exclusions(self) -> list[str]:
        return DEFAULT_EXCLUSIONS + self.exclude


@dataclass
class MatchResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    excluded_by: str | None = None

    def as_json(self) -> str:
        return json.dumps({
            "score": self.score,
            "matched": self.matched,
            "missed": self.missed,
            "excluded_by": self.excluded_by,
        })


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _compact_units(text: str) -> str:
    """Join a number to a following unit so '1 TB' and '1tb' compare equal."""
    return re.sub(r"\b(\d+)\s+(tb|gb|mb|ghz|mhz|hz|in|inch|w|k)\b", r"\1\2", text)


def _prepare(text: str) -> str:
    return _compact_units(_normalize(text))


def matches(value: str, title: str) -> bool:
    """
    Does `value` appear in `title`? Tries whole-phrase substring, then the
    squashed form so 'PS-5' matches 'PS5', then token-set containment so word
    order does not matter.
    """
    v, t = _prepare(value), _prepare(title)
    if not v:
        return False
    if v in t:
        return True
    if v.replace(" ", "") in t.replace(" ", ""):
        return True
    v_tokens, t_tokens = set(v.split()), set(t.split())
    return bool(v_tokens) and v_tokens.issubset(t_tokens)


def excluded_by(title: str, terms: list[str]) -> str | None:
    """
    First exclusion term present in the title as whole words, else None.

    Word boundaries are essential here: a substring check makes 'locked' fire
    on 'unlocked', which would suppress most legitimate phone listings.
    """
    prepared = _prepare(title)
    for term in terms:
        pattern = _prepare(term)
        if pattern and re.search(rf"\b{re.escape(pattern)}\b", prepared):
            return term
    return None


def score_listing(title: str, spec: FacetSpec, description: str | None = None) -> MatchResult:
    """
    Deterministic relevance of a listing against a facet spec.

    Returns 0.0 when an exclusion term applies or a required facet is absent —
    those are disqualifications, not deductions.

    The description is used for facet and condition matching but deliberately
    NOT for accessory exclusions. Accessory terms say what the item IS, which
    only the title asserts: a genuine console body reads "comes with 2
    controllers" or "no controller included", and scanning it for "controller"
    would reject exactly the listings we want.
    """
    # Accessory/companion terms — title only.
    hit = excluded_by(title, spec.exclude)
    if hit:
        return MatchResult(score=0.0, excluded_by=hit)

    # Condition terms — anywhere, since "for parts" is usually only in the body.
    searchable = f"{title} {description}" if description else title
    hit = excluded_by(searchable, DEFAULT_EXCLUSIONS)
    if hit:
        return MatchResult(score=0.0, excluded_by=hit)

    if not spec.facets:
        # No spec to judge against — treat as neutral rather than inventing a score.
        return MatchResult(score=1.0)

    # Facets sharing a name are ALTERNATIVES, not conjunctions. Extraction
    # routinely emits model="PS5" and model="PlayStation 5", both required;
    # AND-ing them rejects every real listing, since a title says one or the other.
    groups: dict[str, list[Facet]] = {}
    for facet in spec.facets:
        groups.setdefault(facet.name, []).append(facet)

    matched: list[str] = []
    missed: list[str] = []
    earned = 0.0
    total = 0.0

    for name, alternatives in groups.items():
        weight = max(max(0.0, f.weight) for f in alternatives)
        required = any(f.required for f in alternatives)
        total += weight

        hit = next(
            (v for f in alternatives if (v := f.matched_value(searchable)) is not None), None
        )
        if hit:
            matched.append(f"{name}={hit}")
            earned += weight
        else:
            missed.append(f"{name}={'|'.join(f.label for f in alternatives)}")
            if required:
                return MatchResult(score=0.0, matched=matched, missed=missed)

    score = earned / total if total > 0 else 1.0
    return MatchResult(score=round(score, 4), matched=matched, missed=missed)


def price_score(price: float, fair_price: float | None) -> float:
    """Price attractiveness in [0, 1]. At or above fair price scores 0."""
    if not fair_price or fair_price <= 0 or price < 0:
        return 0.0
    return round(max(0.0, min(1.0, 1.0 - price / fair_price)), 4)


def combine_scores(relevance: float, price: float) -> float:
    """A great price on the wrong item must zero out, so these multiply."""
    return round(relevance * price, 4)


def _fallback_spec(query: str) -> FacetSpec:
    """
    Deterministic spec used when LLM extraction is unavailable.

    Every token of the query becomes a required facet — strictly better than
    no gate at all, and it still applies DEFAULT_EXCLUSIONS.
    """
    tokens = _prepare(query).split()
    return FacetSpec(
        query=query,
        facets=[Facet(name=f"term{i}", values=[t], weight=1.0, required=True)
                for i, t in enumerate(tokens)],
    )


def _spec_from_payload(query: str, payload: dict) -> FacetSpec:
    facets = []
    for raw in payload.get("facets", []):
        # Accept either `values: [...]` or a legacy single `value`.
        raw_values = raw.get("values", raw.get("value", []))
        if isinstance(raw_values, str):
            raw_values = [raw_values]
        values = [str(v).strip() for v in raw_values if str(v).strip()]
        if not values:
            continue
        facets.append(Facet(
            name=str(raw.get("name", "attr")).strip() or "attr",
            values=values,
            weight=float(raw.get("weight", 1.0)),
            required=bool(raw.get("required", False)),
        ))
    exclude = [str(e).strip() for e in payload.get("exclude", []) if str(e).strip()]
    return FacetSpec(query=query, facets=facets, exclude=exclude)


EXTRACTION_PROMPT = """Convert this marketplace search term into a matching spec: "{query}"

Return ONLY JSON:
{{"facets": [{{"name": "...", "values": ["...", "..."], "weight": 1-3, "required": true|false}}],
  "exclude": ["..."]}}

facets = attributes a correct listing's TITLE would contain (model, capacity, size, generation, color).
- values = ALL interchangeable spellings of that ONE attribute. Sellers write it different ways,
  so group every synonym, abbreviation and expansion together:
  {{"name": "model", "values": ["PlayStation 5", "PS5", "PS 5"], "weight": 3, "required": true}}
  Never split spellings of the same attribute into separate facets.
- weight 3 = identifies the product, 1 = nice to have.
- required: true for AT MOST ONE facet — the one naming the product itself.
  A brand or color is never required.
exclude = words that mean the listing is an ACCESSORY, PART, or COMPANION item rather than
the product itself. For "PS5" that is: controller, game, headset, cover, stand, cable, skin, dock.
Be thorough with exclude — accessories are the main source of false matches.
No explanation, just the JSON."""


async def extract_query_facets(query: str, force_refresh: bool = False) -> FacetSpec:
    """One LLM call per watch term, cached for 30 days."""
    if not force_refresh:
        cached = await db.get_cached_facets(query, max_age_days=FACET_CACHE_DAYS)
        if cached:
            logger.debug("Using cached facet spec for '{}'", query)
            return _spec_from_payload(query, json.loads(cached))

    try:
        response = await acompletion(
            **settings.llm_call_kwargs(),
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(query=query)}],
            # Specs run long — a truncated response fails to parse and silently
            # drops back to a spec with no exclusions, defeating the whole gate.
            max_tokens=1500,
            timeout=45,
        )
        payload = _extract_json_object(response.choices[0].message.content.strip())
    except Exception as e:
        logger.warning("Facet extraction failed for '{}': {} — using token fallback", query, e)
        return _fallback_spec(query)

    spec = _spec_from_payload(query, payload)
    if not spec.facets:
        logger.warning("Facet extraction returned no facets for '{}' — using token fallback", query)
        return _fallback_spec(query)

    await db.save_facets_cache(query, json.dumps(payload))
    logger.info(
        "Extracted {} facets ({} required) and {} exclusions for '{}'",
        len(spec.facets), sum(f.required for f in spec.facets), len(spec.exclude), query,
    )
    return spec


def _extract_json_object(text: str) -> dict:
    """Scan for the first JSON object carrying a `facets` key."""
    candidates = []
    if "```" in text:
        for block in text.split("```")[1::2]:
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            candidates.append(block)
    candidates.append(text)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        for start, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(candidate[start:])
            except ValueError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("facets"), list):
                return obj
    raise ValueError(f"No facet JSON in model response: {text[:300]!r}")
