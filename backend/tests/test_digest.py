"""digest.py output on real filings, frozen. web/lib/digest.test.ts checks the TypeScript port against the same
file, so the PWA and the reference implementation can never drift apart."""
import json
from pathlib import Path

from finn.push.digest import build_digest

CASES = json.loads((Path(__file__).parent / "fixtures" / "digest_cases.json").read_text())


def test_digest_matches_frozen_output():
    for c in CASES["cases"]:
        assert build_digest(CASES["filings"], c["start"], c["end"]) == c["expected"]


def test_results_family_folds_into_one_card_per_company():
    d = CASES["cases"][0]["expected"]
    results = [c for c in d["act"] + d["know"] if c["category"] == "results"]
    assert len(results) == len({c["symbol"] for c in results})
    assert any(len(c["attachments"]) >= 3 for c in results)


def test_counts_add_up():
    for c in CASES["cases"]:
        d = c["expected"]
        cards = len(d["act"]) + len(d["know"]) + d["routine"]["count"]
        folded = sum(len(x["attachments"]) for x in d["act"] + d["know"])
        assert cards + folded <= d["headline"]["filings"]
