from typing import Dict, Any


RULE_UNITS: Dict[str, Dict[str, Dict[str, Any]]] = {

    # -------------------------
    # Oversight (Caremark line)
    # -------------------------
    "oversight": {
        "foundation": {
            "case": "Caremark",
            "source": "caremark.txt",
            "rule_unit": "utter failure to attempt to assure that a reasonable reporting or information system exists",
            "concept": "implementation failure",
        },
        "supreme_refinement": {
            "case": "Stone",
            "source": "stone.txt",
            "rule_unit": "failure to act in good faith",
            "concept": "loyalty linkage",
        },
        "modern_application": {
            "case": "Marchand",
            "source": "marchand.txt",
            "rule_unit": "good faith effort to implement an oversight system",
            "concept": "monitoring refinement",
        },
    },

    # -------------------------
    # Takeover Defense (Unocal)
    # -------------------------
    "takeover_defense": {
        "foundation": {
            "case": "Unocal",
            "source": "unocal.txt",
            "rule_unit": "reasonable grounds for believing that a threat to corporate policy and effectiveness existed",
            "concept": "threat perception",
        },
        "supreme_refinement": {
            "case": "Unitrin",
            "source": "unitrin.txt",
            "rule_unit": "neither coercive nor preclusive",
            "concept": "outer bounds",
        },
        "modern_application": {
            "case": "Airgas",
            "source": "airgas.txt",
            "rule_unit": "within a range of reasonableness",
            "concept": "proportionality",
        },
    },

    # -------------------------
    # Controller Transactions (MFW)
    # -------------------------
    "controller_transactions": {
        "foundation": {
            "case": "Kahn",
            "source": "kahn.txt",
            "rule_unit": "entire fairness is the standard of review for a controller transaction",
            "concept": "controller conflict baseline",
        },
        "supreme_refinement": {
            "case": "MFW",
            "source": "mfw.txt",
            "rule_unit": "conditioned from the outset on approval by both an independent special committee and an informed, uncoerced majority of the minority",
            "concept": "dual cleansing protections",
        },
        "modern_application": {
            "case": "Tesla",
            "source": "tesla.txt",
            "rule_unit": "business judgment deference is unavailable if the MFW conditions are not satisfied",
            "concept": "modern application",
        },
    },

    # -------------------------
    # Stockholder Vote Cleansing (Corwin)
    # -------------------------
    "stockholder_vote_cleansing": {
        "foundation": {
            "case": "Corwin",
            "source": "corwin.txt",
            "rule_unit": "a fully informed and uncoerced vote of disinterested stockholders invokes business judgment review",
            "concept": "cleansing baseline",
        },
        "supreme_refinement": {
            "case": "Corwin",
            "source": "corwin.txt",
            "rule_unit": "the vote must be fully informed",
            "concept": "information condition",
        },
        "modern_application": {
            "case": "Corwin",
            "source": "corwin.txt",
            "rule_unit": "the vote must be uncoerced",
            "concept": "coercion condition",
        },
    },

    # -------------------------
    # Sale of Control (Revlon)
    # -------------------------
    "sale_of_control": {
        "foundation": {
            "case": "Revlon",
            "source": "revlon.txt",
            "rule_unit": "once the corporation is for sale, directors must seek the best value reasonably available to stockholders",
            "concept": "sale mode baseline",
        },
        "supreme_refinement": {
            "case": "QVC",
            "source": "qvc.txt",
            "rule_unit": "the duty applies when a transaction will result in a change of control",
            "concept": "change-of-control trigger",
        },
        "modern_application": {
            "case": "Lyondell",
            "source": "lyondell.txt",
            "rule_unit": "directors satisfy their duties if they act reasonably to secure the best value reasonably available",
            "concept": "modern application",
        },
    },

    # -------------------------
    # Demand Futility (Aronson/Rales/Zuckerberg)
    # -------------------------
    "demand_futility": {
        "foundation": {
            "case": "Aronson",
            "source": "aronson.txt",
            "rule_unit": "demand is excused where particularized facts create a reasonable doubt that the directors are disinterested and independent or that the challenged transaction was a valid exercise of business judgment",
            "concept": "board decision challenge",
        },
        "supreme_refinement": {
            "case": "Rales",
            "source": "rales.txt",
            "rule_unit": "demand is excused where particularized facts create a reasonable doubt that a majority of the board could impartially consider a demand",
            "concept": "board capacity to consider demand",
        },
        "modern_application": {
            "case": "Zuckerberg",
            "source": "zuckerberg.txt",
            "rule_unit": "the court asks on a director-by-director basis whether at least half of the board could exercise independent and disinterested judgment in responding to a demand",
            "concept": "modern framework",
        },
    },

    # -------------------------
    # Disclosure Loyalty (Malone)
    # -------------------------
    "disclosure_loyalty": {
        "foundation": {
            "case": "Malone",
            "source": "malone.txt",
            "rule_unit": "directors who communicate with stockholders owe a duty to speak truthfully and completely",
            "concept": "truthful disclosure baseline",
        },
        "supreme_refinement": {
            "case": "Malone",
            "source": "malone.txt",
            "rule_unit": "disclosure that is materially misleading may constitute a breach of the duty of loyalty",
            "concept": "material misstatement refinement",
        },
        "modern_application": {
            "case": "Malone",
            "source": "malone.txt",
            "rule_unit": "directors may not knowingly disseminate false information to stockholders",
            "concept": "knowing falsity application",
        },
    },
}


# -------------------------
# Helpers
# -------------------------

def get_rule_units_for_line(doctrine_line: str) -> Dict[str, Dict[str, Any]]:
    return RULE_UNITS.get(doctrine_line, {})


def get_rule_unit(doctrine_line: str, role: str) -> Dict[str, Any]:
    line = RULE_UNITS.get(doctrine_line, {})
    return line.get(role) or {}


def get_rule_text(doctrine_line: str, role: str) -> str:
    unit = get_rule_unit(doctrine_line, role)
    return unit.get("rule_unit", "")


def get_rule_case(doctrine_line: str, role: str) -> str:
    unit = get_rule_unit(doctrine_line, role)
    return unit.get("case", "")


def get_rule_source(doctrine_line: str, role: str) -> str:
    unit = get_rule_unit(doctrine_line, role)
    return unit.get("source", "")


def get_rule_concept(doctrine_line: str, role: str) -> str:
    unit = get_rule_unit(doctrine_line, role)
    return unit.get("concept", "")

    return ""
def has_rule_units(doctrine_line: str) -> bool:
    return doctrine_line in RULE_UNITS


def get_rule_triplet(doctrine_line: str) -> Dict[str, str]:
    return {
        "foundation": get_rule_text(doctrine_line, "foundation"),
        "supreme_refinement": get_rule_text(doctrine_line, "supreme_refinement"),
        "modern_application": get_rule_text(doctrine_line, "modern_application"),
    }


def get_core_concept(doctrine_line: str) -> str:
    units = RULE_UNITS.get(doctrine_line, {})
    for role in ["supreme_refinement", "foundation", "modern_application"]:
        concept = units.get(role, {}).get("concept")
        if concept:
            return concept
    return ""