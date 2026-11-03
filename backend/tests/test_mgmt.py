from finn.push.mgmt import facts_from_text, plausible, role_class


def test_rule_parse_appointment_and_departure():
    a = facts_from_text("Appointment of Mr Rajiv Dube as Non- Executive Director of the company w.e.f. October 30, 2026.")[0]
    assert (a["name"], a["action"], a["role_class"], a["effective_date"]) == ("Rajiv Dube", "appointment", "director", "October 30, 2026")
    r = facts_from_text("Resignation of Mr. Saurabh Gupta as Chief Financial Officer with effect from November 15, 2026")[0]
    assert (r["name"], r["action"], r["role_class"]) == ("Saurabh Gupta", "resignation", "cfo")


def test_role_classes():
    assert role_class("Chief Executive Officer") == "ceo"
    assert role_class("Non-Executive Independent Director") == "independent_director"
    assert role_class("Company Secretary & Compliance Officer") == "cs"


def test_namesake_filter_needs_name_and_a_tie_to_the_company_or_career():
    good = {"title": "Rajiv Dube - Trent", "content": "Rajiv Dube has served on boards of Tata group companies including Trent."}
    namesake = {"title": "Rajiv Dube, dentist", "content": "Dr Rajiv Dube runs a dental clinic in Pune."}
    wrong_person = {"title": "Rajiv Sharma joins Trent", "content": "Trent appoints Rajiv Sharma."}
    via_employer = {"title": "Profile", "content": "Rajiv Dube spent 20 years at Tata Motors before ..."}
    assert plausible(good, "Rajiv Dube", "Trent Limited", "Director", [])
    assert not plausible(namesake, "Rajiv Dube", "Trent Limited", "Director", [])
    assert not plausible(wrong_person, "Rajiv Dube", "Trent Limited", "Director", [])
    assert plausible(via_employer, "Rajiv Dube", "Trent Limited", None, ["Tata Motors"])
