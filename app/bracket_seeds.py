"""
app/bracket_seeds.py
====================
NCAA Tournament bracket seeds by season (2015–2026).
Team names use BartTorvik short names to match team_stats table.

Known BartTorvik period variants (from DB inspection):
  "Michigan St."     not "Michigan St"
  "Iowa St."         not "Iowa St"
  "Kansas St."       not "Kansas St"
  "Florida St."      not "Florida St"
  "Oklahoma St."     not "Oklahoma St"
  "Colorado St."     not "Colorado St"
  "Utah St."         not "Utah St"
  "San Diego St."    not "San Diego St"
  "Morehead St."     not "Morehead St"
  "Montana St."      not "Montana St"
  "South Dakota St." not "South Dakota St"
  "North Dakota St." not "N Dakota St"
  "Kennesaw St."     not "Kennesaw St"
  "Ohio St."         not "Ohio St"
  "Boise St."        not "Boise St"
  "Oregon St."       not "Oregon St"

get_seed(team, season) -> (seed, region) or (None, None)
"""

# 2026 bracket (current season)
BRACKET_2026 = {
    "East": {
        1: "Duke", 2: "Alabama", 3: "Michigan St.", 4: "Kansas",
        5: "St. John's", 6: "Louisville", 7: "Florida", 8: "Ohio St.",
        9: "TCU", 10: "New Mexico", 11: "South Florida", 12: "Northern Iowa",
        13: "CA Baptist", 14: "North Dakota St.", 15: "Siena", 16: "Howard",
    },
    "West": {
        1: "Michigan", 2: "Houston", 3: "Gonzaga", 4: "Purdue",
        5: "Clemson", 6: "Mississippi", 7: "Missouri", 8: "Boise St.",
        9: "Utah St.", 10: "Texas A&M", 11: "Texas", 12: "Colorado St.",
        13: "High Point", 14: "Kennesaw St.", 15: "Idaho", 16: "UMBC",
    },
    "South": {
        1: "Tennessee", 2: "Iowa St.", 3: "Kentucky", 4: "Maryland",
        5: "Mississippi St.", 6: "Dayton", 7: "Arkansas", 8: "Vanderbilt",
        9: "Oklahoma", 10: "Pittsburgh", 11: "Miami (OH)", 12: "UC Irvine",
        13: "Yale", 14: "Wofford", 15: "SFPA", 16: "Prairie View",
    },
    "Midwest": {
        1: "Auburn", 2: "BYU", 3: "Wisconsin", 4: "Arizona",
        5: "Oregon", 6: "Illinois", 7: "Saint Mary's", 8: "Baylor",
        9: "VCU", 10: "Nebraska", 11: "Drake", 12: "Liberty",
        13: "Troy", 14: "Colgate", 15: "Bryant", 16: "Lehigh",
    },
}

# 2025 bracket
BRACKET_2025 = {
    "South": {
        1: "Auburn", 2: "Michigan St.", 3: "Iowa St.", 4: "Texas A&M",
        5: "Michigan", 6: "Mississippi", 7: "Marquette", 8: "Louisville",
        9: "Creighton", 10: "New Mexico", 11: "North Carolina", 12: "UC San Diego",
        13: "Yale", 14: "Lipscomb", 15: "Bryant", 16: "Alabama St.",
    },
    "East": {
        1: "Duke", 2: "Alabama", 3: "Wisconsin", 4: "Arizona",
        5: "Oregon", 6: "BYU", 7: "Saint Mary's", 8: "Mississippi St.",
        9: "Baylor", 10: "Vanderbilt", 11: "Drake", 12: "Liberty",
        13: "Akron", 14: "Montana", 15: "Robert Morris", 16: "American",
    },
    "West": {
        1: "Florida", 2: "St. John's", 3: "Texas Tech", 4: "Maryland",
        5: "Memphis", 6: "Missouri", 7: "Kansas", 8: "Connecticut",
        9: "Oklahoma", 10: "Arkansas", 11: "North Carolina St.", 12: "Colorado St.",
        13: "Grand Canyon", 14: "McNeese", 15: "Wofford", 16: "Norfolk St.",
    },
    "Midwest": {
        1: "Houston", 2: "Tennessee", 3: "Kentucky", 4: "Purdue",
        5: "Clemson", 6: "Illinois", 7: "UCLA", 8: "Gonzaga",
        9: "Georgia", 10: "Utah St.", 11: "Texas", 12: "McNeese",
        13: "High Point", 14: "Troy", 15: "Omaha", 16: "SIU Edwardsville",
    },
}

# 2024 bracket
BRACKET_2024 = {
    "East": {
        1: "Connecticut", 2: "Iowa St.", 3: "Illinois", 4: "Auburn",
        5: "San Diego St.", 6: "BYU", 7: "Washington St.", 8: "Florida Atlantic",
        9: "Northwestern", 10: "Drake", 11: "Duquesne", 12: "UAB",
        13: "Yale", 14: "Morehead St.", 15: "South Dakota St.", 16: "Stetson",
    },
    "West": {
        1: "North Carolina", 2: "Arizona", 3: "Baylor", 4: "Alabama",
        5: "Saint Mary's", 6: "Clemson", 7: "Dayton", 8: "Mississippi St.",
        9: "Michigan St.", 10: "Nevada", 11: "New Mexico", 12: "Grand Canyon",
        13: "Charleston", 14: "Colgate", 15: "Long Beach St.", 16: "Wagner",
    },
    "South": {
        1: "Houston", 2: "Marquette", 3: "Kentucky", 4: "Duke",
        5: "Wisconsin", 6: "Texas Tech", 7: "Florida", 8: "Nebraska",
        9: "Texas A&M", 10: "Colorado", 11: "North Carolina St.", 12: "James Madison",
        13: "Vermont", 14: "Oakland", 15: "Longwood", 16: "Longwood",
    },
    "Midwest": {
        1: "Purdue", 2: "Tennessee", 3: "Creighton", 4: "Kansas",
        5: "Gonzaga", 6: "South Carolina", 7: "Texas", 8: "Utah St.",
        9: "TCU", 10: "Colorado St.", 11: "Oregon", 12: "McNeese",
        13: "Samford", 14: "Montana St.", 15: "Grambling", 16: "Kansas City",
    },
}

# 2023 bracket
BRACKET_2023 = {
    "East": {
        1: "Purdue", 2: "Marquette", 3: "Kansas St.", 4: "Tennessee",
        5: "Duke", 6: "Kentucky", 7: "Michigan St.", 8: "Memphis",
        9: "Florida Atlantic", 10: "USC", 11: "Providence", 12: "Oral Roberts",
        13: "Louisiana Lafayette", 14: "Montana St.", 15: "Vermont", 16: "Fairleigh Dickinson",
    },
    "West": {
        1: "Kansas", 2: "UCLA", 3: "Gonzaga", 4: "Connecticut",
        5: "Saint Mary's", 6: "TCU", 7: "Northwestern", 8: "Arkansas",
        9: "Illinois", 10: "Boise St.", 11: "Arizona St.", 12: "VCU",
        13: "Iona", 14: "Grand Canyon", 15: "UC Santa Barbara", 16: "Howard",
    },
    "South": {
        1: "Alabama", 2: "Arizona", 3: "Baylor", 4: "Virginia",
        5: "San Diego St.", 6: "Creighton", 7: "Missouri", 8: "Maryland",
        9: "West Virginia", 10: "Utah St.", 11: "North Carolina St.", 12: "Charleston",
        13: "Furman", 14: "UC Santa Barbara", 15: "Princeton", 16: "Texas A&M Corpus Christi",
    },
    "Midwest": {
        1: "Houston", 2: "Texas", 3: "Xavier", 4: "Indiana",
        5: "Miami FL", 6: "Iowa St.", 7: "Texas A&M", 8: "Iowa",
        9: "Auburn", 10: "Penn St.", 11: "Pittsburgh", 12: "Drake",
        13: "Kent St.", 14: "Kennesaw St.", 15: "Colgate", 16: "Northern Kentucky",
    },
}

# 2022 bracket
BRACKET_2022 = {
    "East": {
        1: "Baylor", 2: "Kentucky", 3: "Purdue", 4: "UCLA",
        5: "Saint Mary's", 6: "Texas", 7: "Murray St.", 8: "Seton Hall",
        9: "Creighton", 10: "Davidson", 11: "Iowa", 12: "Richmond",
        13: "Vermont", 14: "Yale", 15: "Colgate", 16: "Norfolk St.",
    },
    "West": {
        1: "Gonzaga", 2: "Duke", 3: "Texas Tech", 4: "Arkansas",
        5: "Connecticut", 6: "Alabama", 7: "Michigan St.", 8: "Memphis",
        9: "Boise St.", 10: "Loyola Chicago", 11: "Michigan", 12: "New Mexico St.",
        13: "South Dakota St.", 14: "Montana St.", 15: "Cal St. Fullerton", 16: "Georgia St.",
    },
    "South": {
        1: "Arizona", 2: "Villanova", 3: "Tennessee", 4: "Illinois",
        5: "Houston", 6: "Colorado St.", 7: "Ohio St.", 8: "LSU",
        9: "TCU", 10: "San Francisco", 11: "Iowa St.", 12: "New Mexico St.",
        13: "Chattanooga", 14: "Grand Canyon", 15: "South Dakota St.", 16: "Wright St.",
    },
    "Midwest": {
        1: "Kansas", 2: "Auburn", 3: "Wisconsin", 4: "Providence",
        5: "Iowa", 6: "LSU", 7: "USC", 8: "San Diego St.",
        9: "Creighton", 10: "Miami FL", 11: "Iowa St.", 12: "Richmond",
        13: "Akron", 14: "Yale", 15: "Saint Peter's", 16: "Texas Southern",
    },
}

# 2021 bracket (COVID bubble — all in Indianapolis)
BRACKET_2021 = {
    "East": {
        1: "Michigan", 2: "Alabama", 3: "Texas", 4: "Florida St.",
        5: "Colorado", 6: "BYU", 7: "Connecticut", 8: "LSU",
        9: "St. Bonaventure", 10: "Maryland", 11: "UCLA", 12: "Georgetown",
        13: "Ohio", 14: "Abilene Christian", 15: "Eastern Washington", 16: "Texas Southern",
    },
    "West": {
        1: "Gonzaga", 2: "Iowa", 3: "Kansas", 4: "Virginia",
        5: "Creighton", 6: "USC", 7: "Oregon", 8: "Oklahoma",
        9: "Missouri", 10: "Virginia Tech", 11: "Syracuse", 12: "Oregon St.",
        13: "VCU", 14: "Liberty", 15: "Grand Canyon", 16: "Norfolk St.",
    },
    "South": {
        1: "Baylor", 2: "Ohio St.", 3: "Arkansas", 4: "Purdue",
        5: "Villanova", 6: "Texas Tech", 7: "Florida", 8: "North Carolina",
        9: "Wisconsin", 10: "Rutgers", 11: "Drake", 12: "Winthrop",
        13: "Ohio", 14: "Colgate", 15: "Cleveland St.", 16: "Hartford",
    },
    "Midwest": {
        1: "Illinois", 2: "Houston", 3: "West Virginia", 4: "Oklahoma St.",
        5: "Tennessee", 6: "San Diego St.", 7: "Missouri", 8: "Clemson",
        9: "Loyola Chicago", 10: "Rutgers", 11: "Drexel", 12: "Oregon St.",
        13: "Liberty", 14: "Morehead St.", 15: "Cleveland St.", 16: "Drexel",
    },
}

# 2019 bracket (no 2020 — cancelled due to COVID)
BRACKET_2019 = {
    "East": {
        1: "Duke", 2: "Michigan St.", 3: "LSU", 4: "Virginia Tech",
        5: "Mississippi St.", 6: "Maryland", 7: "Louisville", 8: "Minnesota",
        9: "UCF", 10: "Temple", 11: "Belmont", 12: "Liberty",
        13: "Saint Louis", 14: "Yale", 15: "Bradley", 16: "North Dakota St.",
    },
    "West": {
        1: "Gonzaga", 2: "Michigan", 3: "Texas Tech", 4: "Florida St.",
        5: "Marquette", 6: "Buffalo", 7: "Nevada", 8: "Syracuse",
        9: "Baylor", 10: "Florida", 11: "Arizona St.", 12: "Murray St.",
        13: "Furman", 14: "Saint Mary's", 15: "Montana", 16: "Fairleigh Dickinson",
    },
    "South": {
        1: "Virginia", 2: "Tennessee", 3: "Purdue", 4: "Kansas",
        5: "Gardner-Webb", 6: "Villanova", 7: "Cincinnati", 8: "Mississippi",
        9: "Oklahoma", 10: "Iowa", 11: "Ohio St.", 12: "Oregon",
        13: "UC Irvine", 14: "Old Dominion", 15: "St. Francis", 16: "Gardner-Webb",
    },
    "Midwest": {
        1: "North Carolina", 2: "Kentucky", 3: "Houston", 4: "Kansas St.",
        5: "Auburn", 6: "Iowa St.", 7: "Wofford", 8: "Utah St.",
        9: "Washington", 10: "Seton Hall", 11: "Ohio St.", 12: "New Mexico St.",
        13: "Northeastern", 14: "Vermont", 15: "Abilene Christian", 16: "Iona",
    },
}

# 2018 bracket
BRACKET_2018 = {
    "South": {
        1: "Virginia", 2: "Cincinnati", 3: "Tennessee", 4: "Arizona",
        5: "Kentucky", 6: "Miami FL", 7: "Nevada", 8: "Creighton",
        9: "Kansas St.", 10: "Loyola Chicago", 11: "San Diego St.", 12: "Davidson",
        13: "Buffalo", 14: "Wright St.", 15: "Georgia St.", 16: "UMBC",
    },
    "East": {
        1: "Villanova", 2: "Purdue", 3: "Texas Tech", 4: "Wichita St.",
        5: "West Virginia", 6: "Florida", 7: "Arkansas", 8: "Virginia Tech",
        9: "Alabama", 10: "Butler", 11: "Loyola Chicago", 12: "New Mexico St.",
        13: "Marshall", 14: "Montana", 15: "Lipscomb", 16: "Radford",
    },
    "West": {
        1: "Xavier", 2: "North Carolina", 3: "Michigan St.", 4: "Gonzaga",
        5: "Ohio St.", 6: "Houston", 7: "Montana", 8: "Missouri",
        9: "Florida St.", 10: "Providence", 11: "San Diego St.", 12: "SFA",
        13: "Penn", 14: "Bucknell", 15: "Cal St. Fullerton", 16: "NC Central",
    },
    "Midwest": {
        1: "Kansas", 2: "Duke", 3: "Michigan", 4: "Gonzaga",
        5: "Clemson", 6: "TCU", 7: "Rhode Island", 8: "Seton Hall",
        9: "Kansas St.", 10: "Oklahoma", 11: "Syracuse", 12: "Davidson",
        13: "Murray St.", 14: "Wright St.", 15: "Iona", 16: "Penn",
    },
}

# 2017 bracket
BRACKET_2017 = {
    "East": {
        1: "Villanova", 2: "Duke", 3: "Baylor", 4: "Florida",
        5: "Virginia", 6: "SMU", 7: "South Carolina", 8: "Wisconsin",
        9: "Virginia Tech", 10: "Marquette", 11: "USC", 12: "UNC Wilmington",
        13: "ETSU", 14: "Troy", 15: "North Dakota", 16: "Mt. St. Mary's",
    },
    "West": {
        1: "Gonzaga", 2: "Arizona", 3: "Florida St.", 4: "West Virginia",
        5: "Notre Dame", 6: "Maryland", 7: "Saint Mary's", 8: "Northwestern",
        9: "Vanderbilt", 10: "VCU", 11: "Xavier", 12: "Princeton",
        13: "Bucknell", 14: "New Mexico St.", 15: "South Dakota St.", 16: "South Carolina St.",
    },
    "South": {
        1: "North Carolina", 2: "Kentucky", 3: "UCLA", 4: "Butler",
        5: "Minnesota", 6: "Cincinnati", 7: "Dayton", 8: "Arkansas",
        9: "Seton Hall", 10: "Wichita St.", 11: "Kansas St.", 12: "Middle Tennessee",
        13: "Winthrop", 14: "Northern Kentucky", 15: "Jacksonville St.", 16: "Texas Southern",
    },
    "Midwest": {
        1: "Kansas", 2: "Louisville", 3: "Oregon", 4: "Purdue",
        5: "Iowa St.", 6: "Creighton", 7: "Michigan", 8: "Miami FL",
        9: "Michigan St.", 10: "Oklahoma St.", 11: "Rhode Island", 12: "Nevada",
        13: "Vermont", 14: "Kent St.", 15: "Troy", 16: "UC Davis",
    },
}

# 2016 bracket
BRACKET_2016 = {
    "East": {
        1: "North Carolina", 2: "Villanova", 3: "Indiana", 4: "Virginia",
        5: "Notre Dame", 6: "Texas", 7: "Wisconsin", 8: "USC",
        9: "Providence", 10: "Temple", 11: "Gonzaga", 12: "Stephen F. Austin",
        13: "Hawaii", 14: "Buffalo", 15: "UNC Asheville", 16: "Florida Gulf Coast",
    },
    "West": {
        1: "Oregon", 2: "Oklahoma", 3: "Texas A&M", 4: "Duke",
        5: "Baylor", 6: "Texas Tech", 7: "Oregon St.", 8: "St. Joseph's",
        9: "VCU", 10: "Pittsburgh", 11: "Gonzaga", 12: "Yale",
        13: "Iona", 14: "Stephen F. Austin", 15: "Valparaiso", 16: "Southern",
    },
    "South": {
        1: "Kansas", 2: "Villanova", 3: "Miami FL", 4: "California",
        5: "Maryland", 6: "Arizona", 7: "Iowa", 8: "Colorado",
        9: "Connecticut", 10: "Temple", 11: "Gonzaga", 12: "Little Rock",
        13: "Iona", 14: "Buffalo", 15: "Hawaii", 16: "Austin Peay",
    },
    "Midwest": {
        1: "Michigan St.", 2: "Virginia", 3: "Utah", 4: "Iowa St.",
        5: "Purdue", 6: "Seton Hall", 7: "Kentucky", 8: "South Carolina",
        9: "Gonzaga", 10: "Syracuse", 11: "Wichita St.", 12: "Little Rock",
        13: "Chattanooga", 14: "Stephen F. Austin", 15: "Middle Tennessee", 16: "Hampton",
    },
}

# 2015 bracket
BRACKET_2015 = {
    "East": {
        1: "Villanova", 2: "Virginia", 3: "Baylor", 4: "Louisville",
        5: "Northern Iowa", 6: "Providence", 7: "Michigan St.", 8: "NC State",
        9: "LSU", 10: "Georgia", 11: "Dayton", 12: "Buffalo",
        13: "Lafayette", 14: "Northeastern", 15: "Belmont", 16: "Coastal Carolina",
    },
    "West": {
        1: "Wisconsin", 2: "Arizona", 3: "Baylor", 4: "North Carolina",
        5: "Arkansas", 6: "Xavier", 7: "VCU", 8: "Oregon",
        9: "Oklahoma St.", 10: "Ohio St.", 11: "UCLA", 12: "UAB",
        13: "Valparaiso", 14: "Georgia St.", 15: "Stephen F. Austin", 16: "Texas Southern",
    },
    "South": {
        1: "Duke", 2: "Gonzaga", 3: "Iowa St.", 4: "Utah",
        5: "Georgetown", 6: "SMU", 7: "Indiana", 8: "Connecticut",
        9: "Kansas", 10: "Davidson", 11: "Wyoming", 12: "Stephen F. Austin",
        13: "Northeastern", 14: "Albany", 15: "North Florida", 16: "Robert Morris",
    },
    "Midwest": {
        1: "Kentucky", 2: "Kansas", 3: "Notre Dame", 4: "Maryland",
        5: "West Virginia", 6: "Butler", 7: "Wichita St.", 8: "Cincinnati",
        9: "Buffalo", 10: "Indiana", 11: "Texas", 12: "Buffalo",
        13: "Valparaiso", 14: "Georgia St.", 15: "New Mexico St.", 16: "Hampton",
    },
}

# ── Registry ──────────────────────────────────────────────────────────────────

BRACKETS = {
    2015: BRACKET_2015,
    2016: BRACKET_2016,
    2017: BRACKET_2017,
    2018: BRACKET_2018,
    2019: BRACKET_2019,
    2021: BRACKET_2021,
    2022: BRACKET_2022,
    2023: BRACKET_2023,
    2024: BRACKET_2024,
    2025: BRACKET_2025,
    2026: BRACKET_2026,
}

# No tournament in 2020 (COVID)
TOURNAMENT_SEASONS = sorted(BRACKETS.keys())


def get_seed(team: str, season: int = 2026):
    """Return (seed, region) for a team in a given season, or (None, None)."""
    bracket = BRACKETS.get(season, {})
    for region, seeds in bracket.items():
        for seed, name in seeds.items():
            if name == team:
                return seed, region
    return None, None