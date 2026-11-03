from finn.pull.bundle import ar_sections
from finn.pull.chunks import ar_chunks, call_key, transcript_chunks


def test_call_key():
    assert call_key("Aug 2026") == "2026-08"
    assert call_key("May 2025") == "2025-05"


def test_transcript_turns_carry_speaker_and_page():
    pages = ["Moderator: Welcome to the call.\nAmit Syngle: Demand improved in Q2.\n",
             "We expect double-digit volume growth.\nPercy Panthaki: What about margins?\n"]
    ch = transcript_chunks(pages, "Aug 2026")
    assert [c["id"] for c in ch] == ["T2026-08-p1-0", "T2026-08-p1-1", "T2026-08-p2-0", "T2026-08-p2-1"]
    assert ch[2]["speaker"] == "Amit Syngle"          # continuation across the page break
    assert ch[3]["speaker"] == "Percy Panthaki"


def test_long_turns_split_at_1500_chars():
    ch = transcript_chunks(["CEO Name: " + "x" * 3200], "Aug 2026")
    assert [len(c["text"]) for c in ch] == [1500, 1500, 200]


def test_mdna_is_the_longest_run_not_the_contents_page():
    pages = ["Contents\nChairman's letter 4\nManagement Discussion and Analysis 24\nCorporate Governance 90\n"
             "Business Responsibility 120\nFinancial Statements 150"]
    pages += ["intro"] * 5
    pages += [f"page {i} text ... MANAGEMENT DISCUSSION AND ANALYSIS" for i in range(6)]
    pages += ["Directors' report"] * 4 + ["see Management Discussion and Analysis on page 24"]
    pages += ["Note 32: Operating segments ..."]
    s = ar_sections(pages)
    assert s["mdna"] == [7, 8, 9, 10, 11, 12]
    assert s["segments"] == [18]
    assert [c["id"] for c in ar_chunks(pages, "2026", s["mdna"][:2])] == ["AR2026-p7", "AR2026-p8"]
