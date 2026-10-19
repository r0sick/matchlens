"""Fictional league: clubs, tactical identities and procedurally generated squads.

Everything here is invented. Club names, cities and player names are synthetic
combinations and do not represent real clubs or people.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------- #
# Name pools by nationality (used for multi-market storytelling)
# --------------------------------------------------------------------------- #
NAME_POOLS = {
    "ENG": (["Oliver", "Harry", "Jack", "Charlie", "George", "Alfie", "Callum", "Reece", "Mason", "Toby", "Lewis", "Owen"],
            ["Ashworth", "Pembridge", "Cartwright", "Hollins", "Marlow", "Whitfield", "Drayton", "Kettering", "Fenwick", "Bramley", "Thorne", "Calloway"]),
    "ESP": (["Pablo", "Álvaro", "Iker", "Sergio", "Hugo", "Adrián", "Rubén", "Marcos", "Dani", "Javi", "Nacho", "Unai"],
            ["Valcárcel", "Ortuño", "Bermejo", "Llorente", "Cabañas", "Sarrión", "Mendívil", "Escribá", "Lozano", "Arteche", "Peiró", "Quesada"]),
    "FRA": (["Lucas", "Théo", "Hugo", "Mathis", "Enzo", "Kylian", "Rayan", "Noah", "Baptiste", "Yanis", "Jules", "Maxence"],
            ["Durand", "Lefèvre", "Marchetti", "Bonnaud", "Garnier", "Rousseau", "Fontaine", "Chevalier", "Lambert", "Moreau", "Delattre", "Brunet"]),
    "GER": (["Leon", "Jonas", "Felix", "Niklas", "Lukas", "Tim", "Finn", "Moritz", "Jannik", "Paul", "Elias", "Kai"],
            ["Brandt", "Kessler", "Hofmann", "Lindner", "Vogt", "Steiner", "Krämer", "Busch", "Wendel", "Albrecht", "Seidel", "Ostermann"]),
    "POR": (["João", "Tiago", "Rúben", "Diogo", "Gonçalo", "Rafael", "Nuno", "Bruno", "André", "Vítor", "Francisco", "Miguel"],
            ["Carvalhal", "Mendonça", "Esteves", "Pinheiro", "Valente", "Brás", "Quintela", "Sobral", "Teixeira", "Amaral", "Fonseca", "Lobato"]),
    "ITA": (["Lorenzo", "Matteo", "Federico", "Alessandro", "Davide", "Simone", "Nicolò", "Riccardo", "Gianluca", "Tommaso", "Andrea", "Marco"],
            ["Ferraresi", "Galvani", "Monteleone", "Bassani", "Caruso", "Pellegrini", "Rinaldi", "Santoro", "Vitale", "Zanetti", "Lombardo", "Benedetti"]),
    "NED": (["Daan", "Sem", "Milan", "Thijs", "Bram", "Luuk", "Jesse", "Ruben", "Stijn", "Joris", "Teun", "Niels"],
            ["van Dalen", "de Wit", "Verhoef", "Bosman", "Kuipers", "van Rijn", "Hendriks", "Mulder", "de Graaf", "Schouten", "Visser", "Bakker"]),
    "BRA": (["Gabriel", "Matheus", "Vinícius", "Lucas", "Thiago", "Rodrigo", "Caio", "Felipe", "Igor", "Murilo", "Renan", "Wesley"],
            ["Nascimento", "Araújo", "Siqueira", "Barbosa", "Cardoso", "Moraes", "Teles", "Rezende", "Vasconcelos", "Paiva", "Queiroz", "Bastos"]),
    "ARG": (["Facundo", "Tomás", "Agustín", "Joaquín", "Lautaro", "Franco", "Thiago", "Nahuel", "Valentín", "Santino", "Bruno", "Ezequiel"],
            ["Echeverría", "Benítez", "Ledesma", "Aguirre", "Sosa", "Villalba", "Medina", "Correa", "Paredes", "Funes", "Godoy", "Ríos"]),
    "NGA": (["Chidi", "Emeka", "Tunde", "Femi", "Ifeanyi", "Samuel", "Victor", "Kelechi", "Ademola", "Uche", "Tobi", "Musa"],
            ["Okafor", "Adeyemi", "Nwosu", "Balogun", "Eze", "Okonkwo", "Adebayo", "Olatunji", "Chukwu", "Afolabi", "Nnamdi", "Ibekwe"]),
    "JPN": (["Haruto", "Ren", "Sota", "Yuto", "Kaito", "Daiki", "Takumi", "Riku", "Shun", "Kenta", "Hiroki", "Yuma"],
            ["Takeda", "Morimoto", "Kawano", "Fujisaki", "Hayama", "Ishida", "Nakagawa", "Okuda", "Sakamoto", "Tanabe", "Uchida", "Yoshimura"]),
    "KOR": (["Min-jun", "Seo-jun", "Ji-ho", "Do-yun", "Hyun-woo", "Jun-seo", "Woo-jin", "Sung-min", "Tae-yang", "Joon-ho", "Jae-won", "Dong-hyun"],
            ["Park", "Han", "Seo", "Yoon", "Jang", "Lim", "Kang", "Shin", "Baek", "Cho", "Oh", "Ryu"]),
    "MAR": (["Achraf", "Yassine", "Hakim", "Sofiane", "Ilias", "Bilal", "Anas", "Ayoub", "Zakaria", "Amine", "Walid", "Nabil"],
            ["El Idrissi", "Benali", "Ouazzani", "Tahiri", "Amrani", "Bensaïd", "Lahlou", "Chraibi", "Berrada", "Kettani", "Alaoui", "Ziani"]),
    "USA": (["Tyler", "Brandon", "Cole", "Austin", "Logan", "Jordan", "Chase", "Wyatt", "Hunter", "Blake", "Grant", "Tanner"],
            ["Whitaker", "Lindqvist", "Montgomery", "Delgado", "Harlan", "Prescott", "Sutton", "Bishop", "Crawford", "Holloway", "Rhodes", "Vance"]),
}

# --------------------------------------------------------------------------- #
# Formations: role list + base shape in the attacking frame (x 0..105 toward
# the opponent goal, y 0..68 left->right looking at the opponent goal), for a
# team in possession with the ball around midfield. The engine shifts and
# compresses this shape with the ball.
# --------------------------------------------------------------------------- #
FORMATIONS = {
    "4-3-3": [("GK", 5, 34), ("RB", 38, 60), ("RCB", 28, 45), ("LCB", 28, 23), ("LB", 38, 8),
              ("RCM", 52, 46), ("DM", 42, 34), ("LCM", 52, 22),
              ("RW", 72, 60), ("ST", 80, 34), ("LW", 72, 8)],
    "4-2-3-1": [("GK", 5, 34), ("RB", 38, 60), ("RCB", 28, 45), ("LCB", 28, 23), ("LB", 38, 8),
                ("RDM", 45, 42), ("LDM", 45, 26),
                ("RAM", 66, 56), ("CAM", 66, 34), ("LAM", 66, 12), ("ST", 82, 34)],
    "4-4-2": [("GK", 5, 34), ("RB", 36, 60), ("RCB", 27, 45), ("LCB", 27, 23), ("LB", 36, 8),
              ("RM", 58, 60), ("RCM", 48, 42), ("LCM", 48, 26), ("LM", 58, 8),
              ("RST", 78, 42), ("LST", 78, 26)],
    "3-5-2": [("GK", 5, 34), ("RCB", 30, 50), ("CB", 26, 34), ("LCB", 30, 18),
              ("RWB", 56, 63), ("RCM", 52, 44), ("DM", 42, 34), ("LCM", 52, 24), ("LWB", 56, 5),
              ("RST", 78, 40), ("LST", 78, 28)],
    "3-4-3": [("GK", 5, 34), ("RCB", 30, 50), ("CB", 26, 34), ("LCB", 30, 18),
              ("RWB", 55, 63), ("RCM", 48, 42), ("LCM", 48, 26), ("LWB", 55, 5),
              ("RW", 74, 54), ("ST", 82, 34), ("LW", 74, 14)],
}

# Role -> broad position group (for attribute profiles and narratives)
ROLE_GROUP = {
    "GK": "GK",
    "RB": "FB", "LB": "FB", "RWB": "FB", "LWB": "FB",
    "RCB": "CB", "LCB": "CB", "CB": "CB",
    "DM": "DM", "RDM": "DM", "LDM": "DM",
    "RCM": "CM", "LCM": "CM",
    "RM": "WM", "LM": "WM",
    "RAM": "AM", "LAM": "AM", "CAM": "AM",
    "RW": "W", "LW": "W",
    "ST": "ST", "RST": "ST", "LST": "ST",
}

# Attribute profile offsets per position group (added to club base rating)
PROFILES = {
    #        pass vis drib fin  pow  pace stam tack posi comp aer  keep
    "GK": dict(passing=-12, vision=-15, dribbling=-30, finishing=-50, shot_power=-20, pace=-20, stamina=-10,
               tackling=-40, positioning=0, composure=0, aerial=0, keeping=8),
    "CB": dict(passing=-6, vision=-10, dribbling=-12, finishing=-25, shot_power=-5, pace=-4, stamina=0,
               tackling=8, positioning=6, composure=0, aerial=8, keeping=-60),
    "FB": dict(passing=-2, vision=-5, dribbling=0, finishing=-18, shot_power=-6, pace=6, stamina=6,
               tackling=2, positioning=0, composure=-2, aerial=-6, keeping=-60),
    "DM": dict(passing=4, vision=2, dribbling=-4, finishing=-15, shot_power=0, pace=-4, stamina=6,
               tackling=6, positioning=6, composure=4, aerial=0, keeping=-60),
    "CM": dict(passing=6, vision=5, dribbling=2, finishing=-8, shot_power=2, pace=0, stamina=6,
               tackling=0, positioning=2, composure=4, aerial=-4, keeping=-60),
    "WM": dict(passing=2, vision=2, dribbling=4, finishing=-6, shot_power=0, pace=6, stamina=5,
               tackling=-4, positioning=0, composure=0, aerial=-8, keeping=-60),
    "AM": dict(passing=6, vision=8, dribbling=6, finishing=0, shot_power=2, pace=2, stamina=0,
               tackling=-12, positioning=4, composure=6, aerial=-8, keeping=-60),
    "W":  dict(passing=0, vision=2, dribbling=8, finishing=0, shot_power=2, pace=10, stamina=2,
               tackling=-15, positioning=2, composure=2, aerial=-10, keeping=-60),
    "ST": dict(passing=-4, vision=0, dribbling=2, finishing=10, shot_power=6, pace=4, stamina=0,
               tackling=-18, positioning=8, composure=6, aerial=4, keeping=-60),
}

ATTRS = ["passing", "vision", "dribbling", "finishing", "shot_power", "pace", "stamina",
         "tackling", "positioning", "composure", "aerial", "keeping"]


@dataclass
class Player:
    player_id: str
    name: str
    short_name: str
    nationality: str
    shirt: int
    position: str          # natural role in the club formation (e.g. "RCB")
    group: str             # GK/CB/FB/DM/CM/WM/AM/W/ST
    foot: str
    age: int
    height_cm: int
    attrs: dict = field(default_factory=dict)
    is_star: bool = False

    def overall(self) -> int:
        keys = {"GK": ["keeping", "positioning", "composure", "aerial"],
                "CB": ["tackling", "positioning", "aerial", "passing"],
                "FB": ["pace", "tackling", "passing", "stamina"],
                "DM": ["tackling", "passing", "positioning", "stamina"],
                "CM": ["passing", "vision", "stamina", "composure"],
                "WM": ["pace", "passing", "dribbling", "stamina"],
                "AM": ["passing", "vision", "dribbling", "composure"],
                "W": ["pace", "dribbling", "finishing", "passing"],
                "ST": ["finishing", "positioning", "composure", "shot_power"]}[self.group]
        return round(sum(self.attrs[k] for k in keys) / len(keys))


@dataclass
class Club:
    club_id: str
    name: str
    short_name: str
    abbr: str
    city: str
    country_market: str     # primary fan market / language
    stadium: str
    capacity: int
    colors: dict            # {"primary": hex, "secondary": hex, "text": hex}
    formation: str
    style: dict             # possession, press, directness, tempo, width, line_height (0..1)
    rating: int             # base attribute level
    nickname: str
    squad: list = field(default_factory=list)

    def to_dict(self, include_squad: bool = True) -> dict:
        d = asdict(self)
        if include_squad:
            d["squad"] = [asdict(p) | {"overall": p.overall()} for p in self.squad]
        else:
            d.pop("squad")
        return d


CLUB_SPECS = [
    # name, short, abbr, city, market, stadium, cap, colors, formation, style, rating, nickname, nation mix
    ("Thornbury Rovers", "Thornbury", "THR", "Thornbury", "en", "Ashgrove Park", 52000,
     {"primary": "#B3122E", "secondary": "#FFFFFF", "text": "#FFFFFF"}, "4-3-3",
     dict(possession=0.80, press=0.75, directness=0.30, tempo=0.70, width=0.70, line_height=0.75), 80, "The Kestrels",
     {"ENG": 4, "ESP": 2, "BRA": 2, "NED": 2, "FRA": 2, "NGA": 1, "KOR": 1, "MAR": 1, "GER": 1, "POR": 2}),
    ("Kingsmere United", "Kingsmere", "KMU", "Kingsmere", "en", "The Old Foundry", 61000,
     {"primary": "#1D3F8C", "secondary": "#F2C230", "text": "#FFFFFF"}, "4-2-3-1",
     dict(possession=0.65, press=0.60, directness=0.45, tempo=0.60, width=0.60, line_height=0.60), 79, "The Foundrymen",
     {"ENG": 5, "FRA": 3, "POR": 2, "ARG": 2, "NGA": 2, "JPN": 1, "GER": 2, "USA": 1}),
    ("CD Mirasol", "Mirasol", "MIR", "Mirasol de la Vega", "es", "Estadio Las Salinas", 34000,
     {"primary": "#F28C1B", "secondary": "#0B2545", "text": "#0B2545"}, "4-3-3",
     dict(possession=0.75, press=0.55, directness=0.25, tempo=0.55, width=0.65, line_height=0.60), 76, "Los Naranjos",
     {"ESP": 9, "ARG": 3, "BRA": 1, "MAR": 2, "POR": 1, "FRA": 1, "JPN": 1}),
    ("Olympique Rivemont", "Rivemont", "OLR", "Rivemont-sur-Loire", "fr", "Stade des Tisserands", 41000,
     {"primary": "#5B2A86", "secondary": "#E8E8E8", "text": "#FFFFFF"}, "4-2-3-1",
     dict(possession=0.55, press=0.65, directness=0.55, tempo=0.70, width=0.55, line_height=0.55), 77, "Les Tisserands",
     {"FRA": 8, "MAR": 3, "NGA": 2, "POR": 1, "BRA": 2, "GER": 1, "KOR": 1}),
    ("SV Hafenberg", "Hafenberg", "SVH", "Hafenberg", "de", "Kranhaus-Arena", 47000,
     {"primary": "#0F7B3F", "secondary": "#FFFFFF", "text": "#FFFFFF"}, "3-4-3",
     dict(possession=0.50, press=0.90, directness=0.60, tempo=0.85, width=0.75, line_height=0.80), 78, "Die Kraniche",
     {"GER": 8, "NED": 2, "KOR": 2, "JPN": 2, "USA": 1, "NGA": 1, "FRA": 1, "ARG": 1}),
    ("AC Montevio", "Montevio", "ACM", "Montevio", "it", "Stadio del Belvedere", 38000,
     {"primary": "#111111", "secondary": "#7FB3E0", "text": "#FFFFFF"}, "3-5-2",
     dict(possession=0.45, press=0.40, directness=0.45, tempo=0.40, width=0.50, line_height=0.35), 76, "I Corvi",
     {"ITA": 9, "ARG": 2, "BRA": 2, "POR": 1, "ESP": 1, "NGA": 1, "FRA": 1}),
    ("FC Aldeia Nova", "Aldeia Nova", "FAN", "Aldeia Nova", "pt", "Estádio do Farol", 30000,
     {"primary": "#00A19A", "secondary": "#F5F5F5", "text": "#FFFFFF"}, "4-4-2",
     dict(possession=0.55, press=0.50, directness=0.50, tempo=0.60, width=0.80, line_height=0.50), 74, "Os Faroleiros",
     {"POR": 8, "BRA": 4, "ARG": 1, "ESP": 2, "NGA": 1, "MAR": 1}),
    ("Blackwater Athletic", "Blackwater", "BWA", "Blackwater", "en", "Mill Lane", 27000,
     {"primary": "#2E2E2E", "secondary": "#E85D04", "text": "#E85D04"}, "4-4-2",
     dict(possession=0.35, press=0.45, directness=0.85, tempo=0.65, width=0.70, line_height=0.40), 73, "The Millers",
     {"ENG": 9, "NGA": 2, "USA": 2, "NED": 1, "GER": 1, "FRA": 1}),
    ("Haven Zeeland FC", "Haven Zeeland", "HZF", "Zeelhaven", "nl", "De Dijk", 26000,
     {"primary": "#E4002B", "secondary": "#003DA5", "text": "#FFFFFF"}, "4-3-3",
     dict(possession=0.70, press=0.70, directness=0.35, tempo=0.70, width=0.75, line_height=0.65), 74, "De Dijkers",
     {"NED": 9, "MAR": 2, "GER": 1, "KOR": 1, "BRA": 1, "NGA": 2, "USA": 1}),
    ("Ironbridge Town", "Ironbridge", "IBT", "Ironbridge", "en", "Furnace Road", 24000,
     {"primary": "#7A1F2B", "secondary": "#7FC8F8", "text": "#FFFFFF"}, "3-5-2",
     dict(possession=0.40, press=0.55, directness=0.70, tempo=0.55, width=0.55, line_height=0.45), 72, "The Smelters",
     {"ENG": 8, "USA": 2, "JPN": 2, "ESP": 1, "NGA": 1, "ARG": 1, "ITA": 1}),
]

# Squad template: 23 players. Bench covers every group.
BENCH_GROUPS = ["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST", "CM", "CB", "W", "GK"]
BENCH_ROLE_FOR_GROUP = {"GK": "GK", "CB": "CB", "FB": "RB", "DM": "DM", "CM": "RCM", "AM": "CAM",
                        "W": "RW", "ST": "ST", "WM": "RM"}


def _clamp(v, lo=25, hi=97):
    return max(lo, min(hi, int(round(v))))


def _make_name(rng: random.Random, nat: str, used: set) -> tuple[str, str]:
    firsts, lasts = NAME_POOLS[nat]
    for _ in range(50):
        f, l = rng.choice(firsts), rng.choice(lasts)
        full = f"{f} {l}"
        if full not in used:
            used.add(full)
            # Brazilian-style single names for some players
            if nat == "BRA" and rng.random() < 0.35:
                return full, f
            return full, l
    full = f"{rng.choice(firsts)} {rng.choice(lasts)}-{rng.choice(lasts)}"
    used.add(full)
    return full, full.split(" ", 1)[1]


def _make_player(rng, club_idx, n, role, group, rating, nat, used, star=False) -> Player:
    name, short = _make_name(rng, nat, used)
    prof = PROFILES[group]
    base = rating + (rng.gauss(7, 2) if star else rng.gauss(0, 3.5))
    attrs = {}
    for a in ATTRS:
        attrs[a] = _clamp(base + prof[a] + rng.gauss(0, 4))
    if group != "GK":
        attrs["keeping"] = _clamp(rng.uniform(10, 25), 5, 30)
    height = int(rng.gauss({"GK": 191, "CB": 188, "ST": 183}.get(group, 178), 5))
    if group in ("CB", "GK", "ST"):
        attrs["aerial"] = _clamp(attrs["aerial"] + (height - 183) * 0.6)
    return Player(
        player_id=f"P{club_idx:02d}{n:02d}",
        name=name, short_name=short, nationality=nat, shirt=0,
        position=role, group=group,
        foot=rng.choices(["right", "left", "both"], [0.72, 0.24, 0.04])[0],
        age=int(min(37, max(17, rng.gauss(26.5, 4)))),
        height_cm=height, attrs=attrs, is_star=star,
    )


def build_league(seed: int = 2026) -> list[Club]:
    """Create the 10-club fictional league deterministically from a seed."""
    rng = random.Random(seed)
    clubs: list[Club] = []
    used_names: set = set()
    for ci, spec in enumerate(CLUB_SPECS, start=1):
        (name, short, abbr, city, market, stadium, cap, colors, formation, style,
         rating, nickname, mix) = spec
        nat_bag = [k for k, v in mix.items() for _ in range(v)]
        rng.shuffle(nat_bag)
        club = Club(club_id=f"C{ci:02d}", name=name, short_name=short, abbr=abbr, city=city,
                    country_market=market, stadium=stadium, capacity=cap, colors=colors,
                    formation=formation, style=style, rating=rating, nickname=nickname)
        roles = FORMATIONS[formation]
        star_slots = set(rng.sample(range(5, 11), k=2))   # stars among mids/forwards
        n = 1
        for i, (role, _, _) in enumerate(roles):
            nat = nat_bag[(n - 1) % len(nat_bag)]
            club.squad.append(_make_player(rng, ci, n, role, ROLE_GROUP[role], rating, nat,
                                           used_names, star=i in star_slots))
            n += 1
        for g in BENCH_GROUPS:
            nat = nat_bag[(n - 1) % len(nat_bag)]
            p = _make_player(rng, ci, n, BENCH_ROLE_FOR_GROUP[g], g, rating - 3, nat, used_names)
            club.squad.append(p)
            n += 1
        # Re-centre so the starting XI strength follows the intended club rating
        delta = (rating + 5) - sum(p.overall() for p in club.squad[:11]) / 11
        for p in club.squad:
            for k in ATTRS:
                if k == "keeping" and p.group != "GK":
                    continue
                p.attrs[k] = _clamp(p.attrs[k] + delta)
        # Shirt numbers: classic numbers for starters where possible
        classic = {"GK": 1, "RB": 2, "RWB": 2, "LB": 3, "LWB": 3, "RCB": 5, "CB": 4, "LCB": 6,
                   "DM": 6, "RDM": 6, "LDM": 8, "RCM": 8, "LCM": 10, "CAM": 10, "RAM": 7,
                   "LAM": 11, "RM": 7, "LM": 11, "RW": 7, "LW": 11, "ST": 9, "RST": 9, "LST": 10}
        taken = set()
        for p in club.squad[:11]:
            num = classic.get(p.position, 0)
            if num in taken or num == 0:
                num = next(k for k in range(2, 99) if k not in taken)
            p.shirt = num
            taken.add(num)
        pool = [k for k in range(12, 45) if k not in taken]
        rng.shuffle(pool)
        for p in club.squad[11:]:
            p.shirt = 13 if p.group == "GK" and 13 not in taken else pool.pop()
            taken.add(p.shirt)
        clubs.append(club)
    return clubs


def club_by_id(clubs: list[Club], cid: str) -> Club:
    for c in clubs:
        if c.club_id == cid or c.abbr == cid or c.short_name.lower() == cid.lower():
            return c
    raise KeyError(cid)
