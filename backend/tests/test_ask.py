from finn.pull import ask


def fake_passages(symbol):
    return [{"id": f"T2026-10-p{i}-0", "kind": "transcript", "period": "Oct 2026", "page": i, "doc_url": "u", "text": t}
            for i, t in enumerate([
                "Our EBITDA margin guidance for FY27 remains at 17.5% to 18.5%.",
                "Revenue grew 11% year on year, led by the services business.",
                "We expect margins to improve in the second half as utilisation rises.",
                "The board declared an interim dividend of 12 rupees per share.",
            ], 1)]


def test_guidance_question_quotes_the_guidance(monkeypatch):
    monkeypatch.setattr(ask, "passages", fake_passages)
    monkeypatch.setattr(ask, "table_rows", lambda s, q: [])
    monkeypatch.setattr(ask.llm, "available", lambda tier="cheap": False)
    r = ask.ask("X", "What did management guide for margins?")
    assert not r["not_found"]
    assert r["citations"][0]["id"] == "T2026-10-p1-0" and "17.5% to 18.5%" in r["answer"]


def test_unrelated_question_is_not_found(monkeypatch):
    monkeypatch.setattr(ask, "passages", fake_passages)
    monkeypatch.setattr(ask, "table_rows", lambda s, q: [])
    r = ask.ask("X", "Which cricket team does the CEO support?")
    assert r["not_found"] and r["citations"] == []


def test_stemming_joins_guide_and_guidance():
    assert ask.stem("guidance") == ask.stem("guide") == "guid"
