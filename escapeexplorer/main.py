import json
import re
from dataclasses import asdict, dataclass
from enum import Enum, StrEnum, auto
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup


class TerrorLevel(StrEnum):
    NONE = "None"
    SPOOKY = "Spooky"
    PASSIVELY_SCARY = "Passively scary"
    ACTIVELY_SCARY = "Actively scary"


@dataclass
class EscapeRoom:
    room_name_english: str
    room_name_original: Optional[str]
    company_name: str
    location: str
    languages: List[str]
    terror_level: TerrorLevel
    phase1_nominations: int
    phase2_rank: str


@dataclass
class Phase1Room:
    name: str
    nominations: int
    new: bool
    terror_level: TerrorLevel
    languages: List[str]


@dataclass
class Phase2Room:
    rank: str
    name: str
    score: str
    players: str
    coverage: str
    comps: str
    abstains: str
    last_years_rank: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


def strip(s: str) -> str:
    return s.strip() if s is not None else s


def read_phase1(soup: BeautifulSoup) -> List[Phase1Room]:
    phase1 = []
    text = str(soup.find(id="phase1rooms").select(".panel-body")[0].p)

    def _strip(s: str) -> str:
        return (
            s.strip("\n")
            .replace("<strong>", "")
            .replace("</strong>", "")
            .split("\n")[
                -1
            ]  # This handles the first line, which doesn't have the right <br>
        )

    def parse_terror_level(line: str) -> TerrorLevel:
        if "☀" in line:
            return TerrorLevel.NONE
        if "👻" in line:
            return TerrorLevel.SPOOKY
        if "🔦" in line:
            return TerrorLevel.PASSIVELY_SCARY
        if "😱" in line:
            return TerrorLevel.ACTIVELY_SCARY

        raise AttributeError(f"Couldn't find a terror level in '{line}'")

    def parse_languages(line: str) -> List[str]:
        if "🇬🇧" in line:
            yield "English"
        if "EU" in line:
            yield "Basque"
        if "🇧🇬" in line:
            yield "Bulgarian"
        if "CA" in line:
            yield "Catalan"
        if "🇭🇷" in line:
            yield "Croatian"
        if "🇨🇿" in line:
            yield "Czech"
        if "🇩🇰" in line:
            yield "Danish"
        if "🇳🇱" in line:
            yield "Dutch"
        if "🇪🇪" in line:
            yield "Estonian"
        if "🇫🇮" in line:
            yield "Finnish"
        if "🇫🇷" in line:
            yield "French"
        if "🇩🇪" in line:
            yield "German"
        if "🇬🇷" in line:
            yield "Greek"
        if "🇮🇱" in line:
            yield "Hebrew"
        if "🇭🇺" in line:
            yield "Hungarian"
        if "🇮🇹" in line:
            yield "Italian"
        if "🇯🇵" in line:
            yield "Japanese"
        if "🇱🇻" in line:
            yield "Latvian"
        if "🇱🇹" in line:
            yield "Lithuanian"
        if "🇵🇱" in line:
            yield "Polish"
        if "🇵🇹" in line:
            yield "Portuguese"
        if "🇷🇴" in line:
            yield "Romanian"
        if "🇷🇺" in line:
            yield "Russian"
        if "🇷🇸" in line:
            yield "Serbian"
        if "🇸🇰" in line:
            yield "Slovak"
        if "🇸🇮" in line:
            yield "Slovenian"
        if "🇪🇸" in line:
            yield "Spanish"
        if "🇸🇪" in line:
            yield "Swedish"
        if "🇺🇦" in line:
            yield "Ukrainian"

    #################
    for line in [_strip(s) for s in text.split("<br/>")[:-1]]:
        phase1.append(
            Phase1Room(
                name=" ".join(line.split(" ")[:-2]),
                nominations=line.split(" ")[-2].strip("()"),
                new="🆕" in line,
                terror_level=parse_terror_level(line),
                languages=list(parse_languages(line)),
            )
        )
    return phase1


def read_phase2(soup: BeautifulSoup) -> List[Phase2Room]:
    phase2 = []
    for row_html in soup.find(id="phase2rooms").select(".tablerow")[1:]:
        raw_data = [
            strip(item.strong.string)
            if item.find(lambda t: t.name == "strong")
            else strip(item.string)
            for item in row_html.find_all("div")
        ]

        phase2.append(
            Phase2Room(
                raw_data[0],
                raw_data[1],
                raw_data[2],
                raw_data[3],
                raw_data[4],
                raw_data[5],
                raw_data[6],
                raw_data[7],
            )
        )
    return phase2


def get_rooms(phase1: List[Phase1Room], phase2: List[Phase2Room]) -> List[EscapeRoom]:
    rooms = []
    for room in phase1:
        room_name_english, room_name_original, company_name, location = parse_name(
            room.name
        )
        rooms.append(
            EscapeRoom(
                room_name_english=room_name_english,
                room_name_original=room_name_original,
                company_name=company_name,
                location=location,
                languages=room.languages,
                terror_level=room.terror_level,
                phase1_nominations=room.nominations,
                phase2_rank="Not ranked",
            )
        )

    def find_room(english_name: str, copmany_name: str) -> EscapeRoom:
        room_candidates = [
            r
            for r in rooms
            if r.room_name_english == english_name and r.company_name == company_name
        ]
        assert (
            len(room_candidates) == 1
        ), f"Found {len(room_candidates)} with name {english_name} and company {company_name}"
        return room_candidates[0]

    # Remove Petra, since it appears twice in the phase1 list, and it is
    # combined under 1 item in phase 2
    rooms.pop(
        rooms.index(
            [r for r in rooms if r.room_name_english == "Petra - The Lost Kingdom"][0]
        )
    )

    for room in phase2:
        (
            room_name_english,
            _,
            company_name,
            _,
        ) = parse_name(room.name)
        room_ref = find_room(room_name_english, company_name)
        room_ref.phase2_rank = room.rank

    return rooms


def parse_name(line: str) -> (str, str, str, str):
    line = line.replace("&amp;", "&").replace("🆕", "")

    # This particular room has a ' - ' in the "company name", thus making
    # the parsing ambiguous
    if "- Escape Stories - Live Escape Game Wuppertal" in line:
        room_name_part = line.split(" - Escape Stories")[0]
    else:
        room_name_part = " - ".join(line.split(" - ")[:-1])

    room_name_english = room_name_part.split("[")[0]
    room_name_original = (
        room_name_part.split("[")[1].replace("]", "") if "[" in room_name_part else None
    )

    # Manually handle petra, has differnt names in phase 1 and in phase 2, but they are
    # combined in phase 2 (so it only has 1 ranking)
    if "Petra - The Lost Kingdom" in line:
        room_name_english = "Petra - The Lost Kingdom"
        room_name_original = "Petra - El reino perdido"

    room_location_part = line.replace(room_name_part, "").lstrip(" - ")
    location = room_location_part.split("(")[-1].rstrip(")")
    company_name = room_location_part.replace(f"({location})", "").strip(" ")

    return room_name_english, room_name_original, company_name, location


def import_2022():
    with open(Path(__file__).parent.parent / "data" / "input" / "2022.html") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    phase1 = read_phase1(soup)
    phase2 = read_phase2(soup)
    return get_rooms(phase1, phase2)


def main():
    rooms_2022 = import_2022()
    with open(Path(".") / "data" / "terpeca-2022.json", "w") as f:
        f.write(json.dumps([asdict(r) for r in rooms_2022], indent=2))


if __name__ == "__main__":
    main()
