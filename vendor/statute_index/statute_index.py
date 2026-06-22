"""
statute_index.py
================
Builds a lookup index from per-act JSON files in the annotatedCentralActs/
directory (one file per Central Act, ~858 acts).

Each file follows the schema:
    {
        "Act Title":      "THE NEGOTIABLE INSTRUMENTS ACT, 1881",
        "Act ID":         "ACT NO. 26 OF 1881",
        "Enactment Date": "[9th December, 1881.]",
        "Sections" | "Chapters" | "Parts": { ... nested section entries ... },
        "Schedule": {...}, "Annexure": {...}, ...
    }

Sections live at varying depths depending on the act's structure (flat
"Sections", or grouped under "Chapters" / "Parts"). They are identified by
keys of the form "Section 138." or "Section 138A." — discovered via a
recursive walk over the whole document.

BNS (Act 45 of 2023) and BNSS (Act 46 of 2023) are not in this dataset
(which ends at 2020). They are injected as hardcoded section ranges so that
direct BNS/BNSS citations still resolve.

Usage:
    from statute_index import StatuteIndex

    idx = StatuteIndex()
    canonical = idx.lookup("Section 7 of the Aadhaar Act")   # → "Aadhaar s.7"
    canonical = idx.lookup("u/s 302 I.P.C.")                 # → "BNS s.103"
    canonical = idx.lookup("Sec. 138 NI Act")                # → "NI s.138"
"""

import re
import json
from pathlib import Path

DATASET_DIR = Path(__file__).parent / "annotatedCentralActs"

# IPC → BNS and CrPC → BNSS mappings (section number level).
# Used to canonicalize legacy criminal-law citations to the modern statute.
IPC_TO_BNS: dict[str, str] = {
    "34": "BNS s.3(5)", "120B": "BNS s.61", "149": "BNS s.190",
    "302": "BNS s.103", "304": "BNS s.105", "307": "BNS s.109",
    "376": "BNS s.64", "406": "BNS s.316", "420": "BNS s.318",
    "498A": "BNS s.85", "304B": "BNS s.80", "306": "BNS s.108",
    "323": "BNS s.115", "324": "BNS s.115", "325": "BNS s.116",
    "326": "BNS s.117", "354": "BNS s.74", "363": "BNS s.137",
    "364": "BNS s.140", "365": "BNS s.141", "366": "BNS s.137",
    "377": "BNS s.38", "379": "BNS s.303", "380": "BNS s.304",
    "382": "BNS s.305", "384": "BNS s.308", "385": "BNS s.308",
    "386": "BNS s.309", "392": "BNS s.310", "394": "BNS s.310",
    "395": "BNS s.311", "396": "BNS s.311", "397": "BNS s.310",
    "399": "BNS s.311", "447": "BNS s.329", "448": "BNS s.330",
    "449": "BNS s.331", "450": "BNS s.332", "452": "BNS s.333",
    "457": "BNS s.336", "458": "BNS s.337", "459": "BNS s.338",
    "460": "BNS s.339", "465": "BNS s.336", "467": "BNS s.337",
    "468": "BNS s.338", "471": "BNS s.340", "489A": "BNS s.357",
}

CRPC_TO_BNSS: dict[str, str] = {
    "154": "BNSS s.173", "161": "BNSS s.180", "162": "BNSS s.181",
    "163": "BNSS s.182", "164": "BNSS s.183", "167": "BNSS s.187",
    "173": "BNSS s.193", "177": "BNSS s.196", "190": "BNSS s.210",
    "193": "BNSS s.213", "197": "BNSS s.218", "200": "BNSS s.223",
    "204": "BNSS s.227", "207": "BNSS s.230", "211": "BNSS s.234",
    "227": "BNSS s.250", "228": "BNSS s.251", "229": "BNSS s.252",
    "231": "BNSS s.254", "232": "BNSS s.255", "235": "BNSS s.258",
    "239": "BNSS s.262", "240": "BNSS s.263", "241": "BNSS s.264",
    "242": "BNSS s.265", "243": "BNSS s.266", "245": "BNSS s.268",
    "246": "BNSS s.269", "248": "BNSS s.271", "250": "BNSS s.273",
    "256": "BNSS s.279", "257": "BNSS s.280", "258": "BNSS s.281",
    "260": "BNSS s.283", "265A": "BNSS s.290", "265B": "BNSS s.291",
    "268": "BNSS s.298", "300": "BNSS s.337", "301": "BNSS s.338",
    "302": "BNSS s.339", "304": "BNSS s.341", "305": "BNSS s.342",
    "306": "BNSS s.343", "307": "BNSS s.344", "308": "BNSS s.345",
    "309": "BNSS s.346", "311": "BNSS s.348", "313": "BNSS s.351",
    "314": "BNSS s.352", "315": "BNSS s.353", "317": "BNSS s.355",
    "320": "BNSS s.359", "321": "BNSS s.360", "323": "BNSS s.362",
    "324": "BNSS s.363", "325": "BNSS s.364", "326": "BNSS s.365",
    "327": "BNSS s.366", "329": "BNSS s.368", "330": "BNSS s.369",
    "340": "BNSS s.379", "341": "BNSS s.380", "344": "BNSS s.383",
    "346": "BNSS s.385", "347": "BNSS s.386", "348": "BNSS s.387",
    "350": "BNSS s.389", "354": "BNSS s.392", "355": "BNSS s.393",
    "357": "BNSS s.395", "360": "BNSS s.398", "362": "BNSS s.400",
    "363": "BNSS s.401", "366": "BNSS s.404", "367": "BNSS s.405",
    "368": "BNSS s.406", "369": "BNSS s.407", "372": "BNSS s.412",
    "373": "BNSS s.413", "374": "BNSS s.415", "375": "BNSS s.416",
    "376": "BNSS s.417", "377": "BNSS s.418", "378": "BNSS s.419",
    "379": "BNSS s.420", "380": "BNSS s.421", "381": "BNSS s.422",
    "382": "BNSS s.423", "384": "BNSS s.425", "385": "BNSS s.426",
    "386": "BNSS s.427", "387": "BNSS s.428", "389": "BNSS s.430",
    "390": "BNSS s.431", "391": "BNSS s.432", "395": "BNSS s.436",
    "396": "BNSS s.437", "397": "BNSS s.438", "399": "BNSS s.440",
    "400": "BNSS s.441", "401": "BNSS s.442", "406": "BNSS s.447",
    "407": "BNSS s.448", "408": "BNSS s.449", "409": "BNSS s.450",
    "410": "BNSS s.451", "411": "BNSS s.452", "412": "BNSS s.453",
    "413": "BNSS s.454", "414": "BNSS s.455", "415": "BNSS s.456",
    "417": "BNSS s.458", "420": "BNSS s.461", "421": "BNSS s.462",
    "422": "BNSS s.463", "423": "BNSS s.464", "424": "BNSS s.465",
    "425": "BNSS s.466", "426": "BNSS s.467", "427": "BNSS s.468",
    "428": "BNSS s.469", "429": "BNSS s.470", "430": "BNSS s.471",
    "431": "BNSS s.472", "432": "BNSS s.473", "433": "BNSS s.474",
    "433A": "BNSS s.475", "434": "BNSS s.476", "435": "BNSS s.477",
    "436": "BNSS s.478", "436A": "BNSS s.479", "437": "BNSS s.480",
    "437A": "BNSS s.481", "438": "BNSS s.482", "439": "BNSS s.483",
    "440": "BNSS s.484", "441": "BNSS s.485", "446": "BNSS s.490",
    "447": "BNSS s.491", "451": "BNSS s.497", "452": "BNSS s.498",
    "453": "BNSS s.499", "454": "BNSS s.500", "457": "BNSS s.503",
    "458": "BNSS s.504", "459": "BNSS s.505", "460": "BNSS s.506",
    "461": "BNSS s.507", "462": "BNSS s.508", "468": "BNSS s.531",
    "469": "BNSS s.532", "470": "BNSS s.533", "471": "BNSS s.534",
    "472": "BNSS s.535", "473": "BNSS s.536", "474": "BNSS s.537",
    "475": "BNSS s.538", "476": "BNSS s.539", "477": "BNSS s.540",
    "477A": "BNSS s.541", "478": "BNSS s.542", "479": "BNSS s.543",
    "480": "BNSS s.544", "481": "BNSS s.545", "482": "BNSS s.528",
    "483": "BNSS s.529", "484": "BNSS s.530",
}

# Known-act alias map. For acts not listed here, aliases are derived from
# the title by stripping stopwords and building an acronym (see
# generate_act_aliases). Lifted from build_statutes_fast.py so this module
# has no dependency on the deprecated scraper.
ACT_ALIAS_MAP: dict[str, list[str]] = {
    "Aadhaar":                            ["Aadhaar Act", "UIDAI Act"],
    "Bharatiya Nagarik Suraksha Sanhita": ["BNSS", "B.N.S.S."],
    "Bharatiya Nyaya Sanhita":            ["BNS", "B.N.S."],
    "Bharatiya Sakshya Adhiniyam":        ["BSA", "B.S.A."],
    "Indian Penal Code":                  ["IPC", "I.P.C."],
    "Code of Criminal Procedure":         ["CrPC", "Cr.P.C.", "CrPC 1973"],
    "Indian Evidence Act":                ["IEA", "Evidence Act", "Indian Evidence Act"],
    "Code of Civil Procedure":            ["CPC", "C.P.C."],
    "Constitution of India":              ["Constitution"],
    "Limitation Act":                     ["Limitation Act"],
    "Specific Relief Act":                ["SRA"],
    "Transfer of Property Act":           ["TPA", "T.P.A."],
    "Contract Act":                       ["ICA", "Contract Act"],
    "Companies Act":                      ["Companies Act"],
    "Income-tax Act":                     ["IT Act", "Income Tax Act"],
    "Income Tax Act":                     ["IT Act"],
    "Arbitration and Conciliation Act":   ["A&C Act", "Arbitration Act"],
    "Motor Vehicles Act":                 ["MVA"],
    "Negotiable Instruments Act":         ["NI Act", "N.I. Act", "NI"],
    "Hindu Adoption":                     ["HAMA", "Hindu Adoption and Maintenance Act",
                                           "Hindu Adoptions and Maintenance Act"],
    "Securitisation":                     ["SARFAESI", "SARFAESI Act",
                                           "Securitisation Act",
                                           "Securitisation and Reconstruction Act"],
    "Protection of Children":             ["POCSO"],
    "Prevention of Atrocities":           ["SC/ST Act"],
    "Insolvency and Bankruptcy Code":     ["IBC"],
    "Prevention of Money-Laundering":     ["PMLA"],
    "Prevention of Money Laundering":     ["PMLA"],
    "Right to Information Act":           ["RTI Act"],
    "Consumer Protection Act":            ["Consumer Act"],
    "Environment Protection Act":         ["EPA"],
    "Narcotic Drugs and Psychotropic":    ["NDPS"],
    "Foreign Exchange Management Act":    ["FEMA"],
    "Information Technology Act":         ["IT Act 2000"],
}

# Words to drop when building / querying the index.
# Note: "article" / "articles" are NOT stopwords — keeping them is what
# distinguishes Constitutional Articles ("article 21") from generic section 21.
_STOPWORDS = {
    "section", "sections", "sec", "s", "u", "of", "the", "and",
    "act", "code", "sanhita", "adhiniyam", "rules", "rule",
    "order", "schedule", "clause", "clauses",
}


def _strip_words(text: str) -> str:
    """Drop stopwords and trailing year from a short alias/title, preserving case."""
    t = re.sub(r",?\s*(18|19|20)\d{2}$", "", text.strip())
    tokens = [w for w in t.split() if w.lower() not in _STOPWORDS]
    return " ".join(tokens)


def _clean_act_title(title: str) -> str:
    """
    Drop dataset-specific noise from an act title before it's used as an
    index key. Strips trailing "Last update*" metadata that
    annotatedCentralActs appends to some titles in several formats:
        "Last Update 01-6-2020"                  (IBC)
        "Last updated:-13-3-2020"                (Indian Evidence Act)
        "(Last Updated on 1st January, 2020)"    (SARFAESI Act)
    """
    return re.sub(
        r"\s*\(?\s*Last\s+update\S*\s*[:\-(\s].*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()


def strip_key(text: str) -> str:
    """
    Reduce a statute citation to its bare essentials: section number + act tokens.

    Examples:
        "Section 7 of the Aadhaar Act"     → "7 aadhaar"
        "u/s 302 I.P.C."                   → "302 ipc"
        "Sec. 161 Cr.P.C. 1973"            → "161 crpc"
        "s. 7 UIDAI Act"                   → "7 uidai"
        "Section 142(a) NI Act"            → "142 ni"
        "Article 19(1)(c) Constitution"    → "article 19 constitution"
    """
    t = text.lower()
    t = re.sub(r"\([^)]*\)", "", t)            # drop sub-clause parens: (a), (1)(c), etc.
    t = t.replace(".", "")
    t = t.replace("/", " ")
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\b(18|19|20)\d{2}\b", "", t)
    tokens = t.split()
    tokens = [tok for tok in tokens if tok not in _STOPWORDS]
    return " ".join(tokens)


def generate_act_aliases(title: str) -> list[str]:
    """
    Return short aliases for an act title. Looks up ACT_ALIAS_MAP first;
    falls back to an acronym (sig words + first letter of each paren word)
    plus a short common name.
    """
    # Normalize case for matching: dataset titles are ALL CAPS
    title_cmp = title.title() if title.isupper() else title

    for keyword, aliases in ACT_ALIAS_MAP.items():
        if keyword.lower() in title_cmp.lower():
            return aliases

    paren_words = " ".join(re.findall(r"\(([^)]+)\)", title_cmp)).split()
    no_paren = re.sub(r"\s*\([^)]+\)", "", title_cmp).strip()
    no_paren = re.sub(r",?\s*\d{4}$", "", no_paren).strip()

    stop = {"of", "and", "for", "the", "to", "in", "a", "an", "act", "code", "sanhita"}
    sig = [w for w in no_paren.split() if w.lower() not in stop]

    paren_abbr = "".join(w[0].upper() for w in paren_words if w.lower() not in stop)
    main_abbr  = "".join(w[0].upper() for w in sig)
    acronym    = main_abbr + paren_abbr

    suffix     = "Code" if "Code" in title_cmp else "Act"
    short_name = " ".join(sig) + " " + suffix

    aliases = []
    if len(acronym) >= 2:
        aliases.append(acronym)
    if short_name.strip() != suffix:
        aliases.append(short_name)
    return aliases if aliases else [title_cmp[:30]]


_SECTION_KEY_RE = re.compile(r"^\s*Section\s+(\d+[A-Z]*)\b", re.IGNORECASE)


def _iter_section_numbers(obj) -> set[str]:
    """
    Recursively walk a parsed act JSON and return the set of section numbers
    found. Section keys look like "Section 138." or "Section 138A." and may
    appear at varying depths (under "Sections" flat, or nested in
    "Chapters" / "Parts").
    """
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str):
                    m = _SECTION_KEY_RE.match(k)
                    if m:
                        found.add(m.group(1))
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return found


# ── CPC Orders pre-detection ──────────────────────────────────────────────────
# CPC has Orders 1-51. Cited as "Order N Rule M CPC" or "Order VII Rule 11 CPC"
# (roman numeral form). strip_key drops "order" / "rule" as stopwords, so
# detection has to run on the raw input string before keying.

_ROMAN_NUMERAL: dict[str, int] = {
    "i": 1,    "ii": 2,    "iii": 3,   "iv": 4,    "v": 5,
    "vi": 6,   "vii": 7,   "viii": 8,  "ix": 9,    "x": 10,
    "xi": 11,  "xii": 12,  "xiii": 13, "xiv": 14,  "xv": 15,
    "xvi": 16, "xvii": 17, "xviii": 18,"xix": 19,  "xx": 20,
    "xxi": 21, "xxii": 22, "xxiii": 23,"xxiv": 24, "xxv": 25,
    "xxvi": 26,"xxvii": 27,"xxviii":28,"xxix": 29, "xxx": 30,
    "xxxi": 31,"xxxii": 32,"xxxiii":33,"xxxiv":34, "xxxv": 35,
    "xxxvi":36,"xxxvii":37,"xxxviii":38,"xxxix":39,"xl": 40,
    "xli": 41, "xlii": 42, "xliii":43, "xliv": 44, "xlv": 45,
    "xlvi":46, "xlvii":47, "xlviii":48,"xlix":49,  "l": 50,
    "li": 51,
}

# Match "Order N" or "Order N Rule M" (case-insensitive). Allows comma between.
_CPC_ORDER_RE = re.compile(
    r"order\s+([ivxl]+|\d+)\b\s*(?:,?\s*rule\s*(\d+[a-z]?))?",
    re.IGNORECASE,
)


def _parse_cpc_order(raw: str) -> str | None:
    """
    Detect CPC Order/Rule citations and return canonical form, or None.

    Returns:
        "CPC O.N R.M"  — when both Order and Rule are matched
        "CPC O.N"      — when only Order matches
        None           — when no Order N pattern found, or another act is
                         explicitly named in the raw text.
    """
    m = _CPC_ORDER_RE.search(raw)
    if not m:
        return None

    order_raw = m.group(1).lower()
    rule_raw  = m.group(2)

    order_n = int(order_raw) if order_raw.isdigit() else _ROMAN_NUMERAL.get(order_raw)
    if order_n is None or not (1 <= order_n <= 51):
        return None  # unknown or out-of-range — fall through to normal lookup

    # Gate: only claim this as CPC if either "CPC" / "civil procedure" is
    # explicitly present, OR no competing act/article keyword is in raw.
    lower = raw.lower()
    explicit_cpc = "cpc" in lower or "civil procedure" in lower
    competing = any(kw in lower for kw in (
        "ipc", "crpc", "criminal procedure", "penal code", "constitution",
        "article", "nyaya", "nagarik",
    ))
    if not explicit_cpc and competing:
        return None

    if rule_raw:
        return f"CPC O.{order_n} R.{rule_raw.upper()}"
    return f"CPC O.{order_n}"


class StatuteIndex:
    """
    Lookup table: stripped_key → canonical tag (e.g. "IPC s.302").

    Built from all per-act JSON files in dataset_dir at construction time.
    """

    def __init__(self, dataset_dir: Path = DATASET_DIR):
        self._index: dict[str, str] = {}
        # Side-table for the case-level act inventory (Option C in future_changes).
        # _acts[primary] = {
        #   "primary":         e.g. "IPC"
        #   "display_name":    e.g. "Indian Penal Code (IPC)"   — for prompt
        #   "scan_aliases":    raw aliases used to find this act in document text
        #                       (case-insensitive regex with word boundaries)
        #   "numeric_max":     int max numeric section/article
        #   "letter_variants": list[str] non-numeric sections (e.g. "498A", "304B")
        #   "uses_articles":   True iff the act labels its units "Article" not "Section"
        # }
        self._acts: dict[str, dict] = {}
        # Bare-act side-lookup: maps strip_key(alias) → primary.
        # Catches inputs that are act-only (no section number) like
        # "Companies Act" or "Constitution of India". Populated alongside
        # _acts during _register_act.
        self._bare_acts: dict[str, str] = {}
        self._build(dataset_dir)

    # ── Side-table helpers ────────────────────────────────────────────────────
    def _register_act(
        self,
        primary: str,
        display_name: str,
        scan_aliases: list[str],
        section_numbers: list[str],
        uses_articles: bool = False,
    ) -> None:
        """Populate / merge _acts[primary] with the given metadata."""
        numeric = [int(s) for s in section_numbers if s.isdigit()]
        letters = sorted({s for s in section_numbers if not s.isdigit()})
        entry = self._acts.setdefault(primary, {
            "primary":         primary,
            "display_name":    display_name,
            "scan_aliases":    [],
            "numeric_max":     0,
            "letter_variants": [],
            "uses_articles":   uses_articles,
        })
        entry["display_name"] = display_name or entry["display_name"]
        entry["uses_articles"] = uses_articles or entry["uses_articles"]
        if numeric:
            entry["numeric_max"] = max(entry["numeric_max"], max(numeric))
        if letters:
            entry["letter_variants"] = sorted(set(entry["letter_variants"]) | set(letters))
        for a in scan_aliases:
            if a and a not in entry["scan_aliases"]:
                entry["scan_aliases"].append(a)

        # Bare-act lookup: register every alias under its strip_key form
        # so plain "Companies Act" / "Constitution of India" inputs resolve.
        for a in (primary, display_name, *scan_aliases):
            if not a:
                continue
            k = strip_key(a)
            if k:
                self._bare_acts.setdefault(k, primary)

    def _inject_hardcoded(self) -> None:
        """
        After loading the dataset, inject:
          - IPC s.1–511 with BNS canonical where mapped, else "IPC s.N"
          - CrPC s.1–484 with BNSS canonical where mapped, else "CrPC s.N"
          - BNS s.1–358 and BNSS s.1–531 (not in the 1838–2020 dataset)

        These overwrite anything from the per-act files so that legacy
        criminal-law citations always resolve to the modern statute.
        """
        ipc_aliases  = ["ipc", "i p c", "indian penal code", "penal code"]
        crpc_aliases = ["crpc", "cr p c", "code of criminal procedure", "criminal procedure code"]
        bns_aliases  = ["bns", "b n s", "bharatiya nyaya sanhita", "nyaya sanhita"]
        bnss_aliases = ["bnss", "b n s s", "bharatiya nagarik suraksha sanhita", "nagarik suraksha"]

        def inject(sections: list[str], aliases: list[str], mapping: dict[str, str], default_prefix: str):
            for sec in sections:
                canonical = mapping.get(sec, f"{default_prefix} s.{sec}")
                for alias in aliases:
                    # Index both input forms: "NUMBER ALIAS" (hand-typed) and
                    # "ALIAS s.NUMBER" (Claude output format)
                    for input_form in (f"{sec} {alias}", f"{alias} s.{sec}"):
                        key = strip_key(input_form)
                        if key:
                            self._index[key] = canonical

        inject([str(i) for i in range(1, 512)], ipc_aliases,  IPC_TO_BNS,    "IPC")
        # CrPC range extended to 565 to cover pre-1973 (CrPC 1898) section
        # citations like "Section 488 CrPC" — sections 485-565 fall through
        # to default "CrPC s.N" (no BNSS mapping).
        inject([str(i) for i in range(1, 566)], crpc_aliases, CRPC_TO_BNSS,  "CrPC")
        inject([str(i) for i in range(1, 359)], bns_aliases,  {},            "BNS")
        inject([str(i) for i in range(1, 532)], bnss_aliases, {},            "BNSS")

        # Register acts in the side-table for inventory scanning
        ipc_letters  = [s for s in IPC_TO_BNS.keys()  if not s.isdigit()]
        crpc_letters = [s for s in CRPC_TO_BNSS.keys() if not s.isdigit()]
        self._register_act(
            primary="IPC", display_name="Indian Penal Code (IPC)",
            scan_aliases=["IPC", "I.P.C.", "Indian Penal Code", "Penal Code"],
            section_numbers=[str(i) for i in range(1, 512)] + ipc_letters,
        )
        self._register_act(
            primary="CrPC", display_name="Code of Criminal Procedure (CrPC)",
            scan_aliases=["CrPC", "Cr.P.C.", "Code of Criminal Procedure", "Criminal Procedure Code"],
            section_numbers=[str(i) for i in range(1, 566)] + crpc_letters,
        )
        self._register_act(
            primary="BNS", display_name="Bharatiya Nyaya Sanhita (BNS)",
            scan_aliases=["BNS", "B.N.S.", "Bharatiya Nyaya Sanhita", "Nyaya Sanhita"],
            section_numbers=[str(i) for i in range(1, 359)],
        )
        self._register_act(
            primary="BNSS", display_name="Bharatiya Nagarik Suraksha Sanhita (BNSS)",
            scan_aliases=["BNSS", "B.N.S.S.", "Bharatiya Nagarik Suraksha Sanhita", "Nagarik Suraksha"],
            section_numbers=[str(i) for i in range(1, 532)],
        )

        # Alphanumeric inserts (e.g. 436A, 498A, 265B) for IPC/CrPC
        for sec, canonical in IPC_TO_BNS.items():
            if not sec.isdigit():
                for alias in ipc_aliases:
                    for input_form in (f"{sec} {alias}", f"{alias} s.{sec}"):
                        key = strip_key(input_form)
                        if key:
                            self._index[key] = canonical

        for sec, canonical in CRPC_TO_BNSS.items():
            if not sec.isdigit():
                for alias in crpc_aliases:
                    for input_form in (f"{sec} {alias}", f"{alias} s.{sec}"):
                        key = strip_key(input_form)
                        if key:
                            self._index[key] = canonical

        self._inject_constitution()

    def _inject_constitution(self) -> None:
        """
        Inject Constitution of India Articles into the index.

        Two key forms supported because "article" is no longer a stopword:
          - "Article 21"               → "21 article"        (key)
          - "Article 21 Constitution"  → "21 article constitution"

        Covers Articles 1-395 numerically + known letter-variant Articles
        (e.g. 21A, 31A, 124A, 226A, 311A, 323A, 323B, 348A, 350A, 350B).
        """
        constitution_aliases = [
            "constitution",
            "constitution of india",
            "indian constitution",
            "the constitution",
        ]
        # Numeric Articles 1-395
        article_numbers = [str(i) for i in range(1, 396)]
        # Common letter-variant Articles inserted via Constitutional amendments
        article_numbers += [
            "15A", "21A", "29A", "31A", "31B", "31C", "31D",
            "32A", "39A", "43A", "43B", "48A", "51A",
            "131A", "139A", "131A",
            "224A",
            "226A", "227A",
            "300A",
            "311A", "312A",
            "323A", "323B",
            "338A", "338B",
            "342A",
            "343A",
            "348A",
            "350A", "350B",
            "361A", "361B",
            "371A", "371B", "371C", "371D", "371E", "371F", "371G",
            "371H", "371I", "371J",
            "372A",
            "394A",
        ]

        self._register_act(
            primary="Constitution",
            display_name="Constitution of India",
            scan_aliases=["Constitution of India", "Indian Constitution", "the Constitution", "Constitution"],
            section_numbers=article_numbers,
            uses_articles=True,
        )

        for art in article_numbers:
            canonical = f"Constitution s.{art}"

            # Bare form: "Article 21" → key becomes "21 article"
            for input_form in (
                f"Article {art}",
                f"Art {art}",
                f"Art. {art}",
                f"Articles {art}",
            ):
                key = strip_key(input_form)
                if key:
                    self._index[key] = canonical

            # With Constitution alias.
            # Includes "Section N <alias>" variants because some judgments
            # malform Constitutional references as "Section 15 Constitution
            # of India" (semantically wrong but common in our corpus).
            # The "Section N" form is ONLY registered when the Constitution
            # alias is present — never bare — to avoid colliding with real
            # Section N citations of other acts.
            for alias in constitution_aliases:
                for input_form in (
                    f"Article {art} of {alias}",
                    f"Article {art} {alias}",
                    f"Art {art} of {alias}",
                    f"Art. {art} of {alias}",
                    f"{alias} Article {art}",
                    f"{alias} Art {art}",
                    f"Section {art} of {alias}",
                    f"Section {art} {alias}",
                    f"Sec. {art} of {alias}",
                    f"Sec. {art} {alias}",
                    f"S. {art} of {alias}",
                ):
                    key = strip_key(input_form)
                    if key:
                        self._index[key] = canonical

    def _build(self, dataset_dir: Path) -> None:
        for act_file in sorted(dataset_dir.glob("*.json")):
            try:
                data = json.loads(act_file.read_text())
            except Exception:
                continue

            act_title = _clean_act_title(data.get("Act Title") or "")
            if not act_title:
                continue

            section_nums = _iter_section_numbers(data)
            if not section_nums:
                continue

            aliases = generate_act_aliases(act_title)
            primary = _strip_words(aliases[0]) if aliases else _strip_words(act_title)

            for sec_num in section_nums:
                canonical = f"{primary} s.{sec_num}"

                for alias in aliases:
                    # Index both input forms: "NUMBER ALIAS" (hand-typed) and
                    # "ALIAS s.NUMBER" (Claude output format)
                    for input_form in (f"{sec_num} {alias}", f"{alias} s.{sec_num}"):
                        key = strip_key(input_form)
                        if key:
                            self._index[key] = canonical

                # Also index using the full act title so judges who write
                # the long form ("Negotiable Instruments Act") are matched
                for input_form in (f"{sec_num} {act_title}", f"{act_title} s.{sec_num}"):
                    key = strip_key(input_form)
                    if key and key not in self._index:
                        self._index[key] = canonical

            # Register for inventory scanning. Use full title + short aliases
            # as scan_aliases so document scanning catches either form.
            display = f"{act_title} ({aliases[0]})" if aliases and aliases[0] != act_title else act_title
            self._register_act(
                primary=primary,
                display_name=display,
                scan_aliases=[act_title] + list(aliases),
                section_numbers=list(section_nums),
            )

        self._inject_hardcoded()

    def get_act_inventory_entry(self, primary_or_alias: str) -> dict | None:
        """
        Return the inventory metadata dict for an act, looked up by either its
        primary key (e.g. "IPC") or one of its scan_aliases (case-insensitive).
        """
        if primary_or_alias in self._acts:
            return self._acts[primary_or_alias]
        needle = primary_or_alias.strip().lower()
        for entry in self._acts.values():
            if any(needle == a.lower() for a in entry["scan_aliases"]):
                return entry
        return None

    def scan_document_for_acts(self, text: str) -> list[dict]:
        """
        Find every known act mentioned in `text`. Returns a deduped list of
        inventory entries (the same dicts get_act_inventory_entry returns).

        Matching is case-insensitive with word boundaries. Order in the
        returned list reflects first-mention order in `text`.
        """
        if not self._acts:
            return []
        # Build a single combined regex per call — text is the variable input.
        # Sort aliases by length DESC so longer aliases match before shorter
        # ones (e.g. "Indian Penal Code" wins over "IPC" inside the same span).
        alias_to_primary: list[tuple[str, str]] = []
        for entry in self._acts.values():
            for alias in entry["scan_aliases"]:
                alias_to_primary.append((alias, entry["primary"]))
        alias_to_primary.sort(key=lambda x: len(x[0]), reverse=True)

        pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(a) for a, _ in alias_to_primary) + r")\b",
            re.IGNORECASE,
        )
        alias_lookup = {a.lower(): p for a, p in alias_to_primary}

        first_seen: dict[str, int] = {}
        for m in pattern.finditer(text):
            primary = alias_lookup.get(m.group(0).lower())
            if primary and primary not in first_seen:
                first_seen[primary] = m.start()
        return [self._acts[p] for p, _ in sorted(first_seen.items(), key=lambda x: x[1])]

    def lookup(self, raw_extraction: str) -> dict | None:
        """
        Normalize a raw LangExtract output and return structured statute data.

        Returns:
            dict with keys:
              canonical : str   — full canonical tag, e.g. "NI Act s.138"
              act       : str   — act portion, e.g. "NI Act"
              section   : str | None — section number, e.g. "138" (None if act-only)
            or None if not found in the index (unknown act).
        """
        # CPC Orders pre-detection — runs on raw input because strip_key
        # would drop "order" / "rule" as stopwords.
        cpc_canonical = _parse_cpc_order(raw_extraction)
        if cpc_canonical:
            _, _, sec_part = cpc_canonical.partition(" ")
            return {
                "canonical": cpc_canonical,
                "act": "CPC",
                "section": sec_part or None,
            }

        key = strip_key(raw_extraction)
        canonical = self._index.get(key)
        if canonical is not None:
            act, sep, section = canonical.partition(" s.")
            return {
                "canonical": canonical,
                "act": act,
                "section": section if sep else None,
            }

        # Fallback: bare act mention (no section, just the act name).
        bare = self._bare_acts.get(key)
        if bare:
            return {"canonical": bare, "act": bare, "section": None}

        return None

    def __len__(self) -> int:
        return len(self._index)


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    idx = StatuteIndex()
    print(f"Index built: {len(idx)} entries\n")

    test_cases = [
        # Aadhaar — alias variants all collapse to same canonical
        ("Section 7 of the Aadhaar Act",        "Aadhaar s.7"),
        ("u/s 7 UIDAI Act",                     "Aadhaar s.7"),
        ("Sec. 7 of Aadhaar Act",               "Aadhaar s.7"),
        ("s. 7 of the UIDAI Act",               "Aadhaar s.7"),
        # IPC → BNS via hardcoded mapping
        ("Section 302 IPC",                     "BNS s.103"),
        ("u/s 302 I.P.C.",                      "BNS s.103"),
        # IPC section with no BNS mapping → stays as IPC
        ("Section 1 IPC",                       "IPC s.1"),
        # CrPC → BNSS via hardcoded mapping
        ("Section 161 Cr.P.C.",                 "BNSS s.180"),
        ("S. 439 CrPC",                         "BNSS s.483"),
        ("Section 436A CrPC",                   "BNSS s.479"),
        # BNS / BNSS direct (hardcoded, not in dataset)
        ("Section 103 Bharatiya Nyaya Sanhita", "BNS s.103"),
        ("u/s 103 B.N.S.",                      "BNS s.103"),
        # NI Act — was missing from old scrape; should now resolve
        ("Section 138 NI Act",                  "NI s.138"),
        ("u/s 138 of the Negotiable Instruments Act", "NI s.138"),
        # IBC — also missing from old scrape
        ("Section 7 IBC",                       "IBC s.7"),
        ("Sec. 17 of the Insolvency and Bankruptcy Code", "IBC s.17"),
        # Claude prompt-target output format (from chunk_info_extractor.py)
        ("IPC s.302",                           "BNS s.103"),
        ("CrPC s.439",                          "BNSS s.483"),
        ("BNS s.103",                           "BNS s.103"),
        ("BNSS s.187",                          "BNSS s.187"),
        ("NI Act s.138",                        "NI s.138"),
        ("IBC s.7",                             "IBC s.7"),
        # ── Fix 1: bare act mentions (no section) ───────────────────────
        ("Companies Act",                       "Companies"),
        ("Constitution of India",               "Constitution"),
        ("Negotiable Instruments Act",          "NI"),
        # ── Fix 2: parenthetical sub-clauses ────────────────────────────
        ("Section 142(a) NI Act",               "NI s.142"),
        ("Section 396(3) IPC",                  "BNS s.311"),
        ("Article 19(1)(c) Constitution of India", "Constitution s.19"),
        # ── Fix 3: CPC Orders ───────────────────────────────────────────
        ("Order 7 Rule 11 CPC",                 "CPC O.7 R.11"),
        ("Order VII Rule 11 CPC",               "CPC O.7 R.11"),
        ("Order 3 Rule 2 CPC",                  "CPC O.3 R.2"),
        ("Order VI Rule 16 CPC",                "CPC O.6 R.16"),
        # ── Fix 4: old-CrPC range ───────────────────────────────────────
        ("Section 488 CrPC",                    "CrPC s.488"),
        ("Section 561 Cr.P.C.",                 "CrPC s.561"),
        # ── Section-prefix Constitutional refs (malformed but common) ───
        ("Section 15 Constitution of India",    "Constitution s.15"),
        ("Section 21 of the Constitution",      "Constitution s.21"),
        # ── ACT_ALIAS_MAP additions ─────────────────────────────────────
        ("Section 92 Indian Evidence Act",      "IEA s.92"),
        ("Section 92 Evidence Act",             "IEA s.92"),
        ("Section 20 Hindu Adoption and Maintenance Act, 1956", "HAMA s.20"),
        ("Section 20 Hindu Adoptions and Maintenance Act",      "HAMA s.20"),
        ("Section 20 HAMA",                     "HAMA s.20"),
        ("SARFAESI",                            "SARFAESI"),
        ("SARFAESI Act",                        "SARFAESI"),
        ("Section 13 SARFAESI Act",             "SARFAESI s.13"),
        ("Section 13 Securitisation Act",       "SARFAESI s.13"),
    ]

    passed = 0
    for raw, expected in test_cases:
        result = idx.lookup(raw)
        actual = result["canonical"] if result else None
        ok = actual == expected
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {raw!r}  →  {actual!r}")
        if not ok:
            print(f"       expected: {expected!r}")
            print(f"       key:      {strip_key(raw)!r}")

    print(f"\n{passed}/{len(test_cases)} passed")
