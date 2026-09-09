#!/usr/bin/env python3
"""famous.py -- the wide coverage sweep.

coverage.py is a 51-case tripwire kept small so it can gate every build. This is the
other thing: a deliberately large, deliberately global list of events an ordinary person
would expect to find on the year they happened. It exists because the first coverage
audit only tested six events, five of which were missing, and a six-case sample cannot
tell you how big the hole is.

Each case is a year and a phrase (alternatives separated by "|") that must appear
somewhere in that year's published entries. Cases are chosen to spread across regions,
not just Britain and the United States, because the measured bias of this corpus is
Anglocentric and a test drawn only from Anglo history would never see it.

A miss is not automatically our bug -- the event may sit on a neighbouring year in
Wikipedia, or the phrase may not be how Wikipedia words it. --explain says, for every
miss, whether the row exists in data/claims (we extracted it and the build dropped it)
or does not (we never pulled it in), which is the difference between a ranking bug and
an extraction bug.

Usage:
  famous.py [--site data/site] [--claims data/claims] [--explain] [--json report.json]

Three case lists: CASES (events, by year), PEOPLE (births and deaths, by year) and
DAY_CASES (calendar pages).
"""
from __future__ import annotations

import argparse, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# year -> phrase|alternatives that must appear in that year's published entries.
# NOTE the BCE convention, which cost a whole first run of this file: pages are keyed in
# astronomical numbering, so 776 BC is -775 and 44 BC is -43. Writing the BC year with a
# minus sign in front tests the year before the one you meant.
CASES: dict[int, str] = {
    # --- ancient / classical ---
    -2999: "Egypt|Sumer|writing",
    -1749: "Hammurabi|Babylon",
    -1273: "Kadesh|Ramesses",                         # (regression) section allow-list
    -775: "Olympic|Olympiad",
    -752: "Rome is founded|founding of Rome|Romulus",   # (regression) section allow-list
    -508: "Roman Republic|Tarquin",
    -489: "Marathon",
    -479: "Thermopylae|Salamis",
    -430: "Peloponnesian War",
    -398: "Socrates",
    -335: "Alexander",
    -330: "Gaugamela|Alexander",
    -322: "Alexander",
    -220: "Qin|China is unified|Shi Huang",
    -217: "Hannibal|Alps",                            # (regression) colon-indented bullets
    -215: "Cannae",
    -145: "Carthage|Corinth",
    -72: "Spartacus",
    -48: "Rubicon|Caesar",
    -43: "Caesar",
    -30: "Actium",
    -26: "Augustus",
    # --- CE 1-1000 ---
    9: "Teutoburg|Varus",
    33: "Jesus|crucifixion|crucified",
    64: "Great Fire of Rome|Nero",
    79: "Vesuvius|Pompeii",
    117: "Trajan|Hadrian",
    313: "Edict of Milan|Constantine",
    325: "Nicaea",
    410: "Alaric|sack of Rome|Visigoths",
    476: "Romulus Augustulus",
    527: "Justinian",
    570: "Muhammad",
    610: "Muhammad|Heraclius",
    622: "Hijra|Medina|Mecca",
    632: "Muhammad",
    711: "Tariq|Iberia|Umayyad",
    732: "Tours|Poitiers|Martel",
    800: "Charlemagne",
    843: "Verdun",
    862: "Rurik|Novgorod|Rus",
    960: "Song dynasty",
    988: "Vladimir|Kievan Rus|Christianity",
    1000: "Leif|Vinland|Stephen|Hungary",
    # --- medieval ---
    1066: "Hastings",
    1071: "Manzikert",
    1095: "Crusade|Urban",
    1099: "Jerusalem",
    1187: "Hattin|Saladin",
    1204: "Constantinople",
    1206: "Genghis|Temujin|Mongol",
    1215: "Magna Carta",
    1258: "Baghdad",
    1271: "Marco Polo|Kublai",
    1279: "Song|Yuan|Kublai",
    1291: "Acre|Swiss",
    1324: "Mansa Musa|Mali",
    1337: "Hundred Years",
    1347: "Black Death|plague",
    1368: "Ming",
    1381: "Peasants' Revolt",
    1415: "Agincourt|Ceuta",
    1431: "Joan of Arc",
    1440: "Montezuma|Gutenberg|Aztec",
    1453: "Constantinople",
    1455: "Gutenberg|Wars of the Roses",
    1467: "Onin|Ōnin",
    1487: "Dias|Aztec|Bartolomeu",
    1492: "Columbus|Granada",
    1494: "Tordesillas",
    1498: "Vasco da Gama|Calicut",
    # --- early modern ---
    1517: "Luther|Ninety-five|Ninety-Five",
    1519: "Cortés|Cortes|Magellan|Tenochtitlan",
    1521: "Tenochtitlan|Cortés|Cortes|Worms",
    1526: "Panipat|Babur|Mohács|Mohacs",
    1532: "Pizarro|Atahualpa|Cajamarca",
    1543: "Copernicus|Revolutionibus|Vesalius",
    1556: "Akbar|Shaanxi|earthquake",
    1571: "Lepanto",
    1588: "Armada",
    1600: "Sekigahara|East India Company",
    1603: "Tokugawa|Elizabeth",
    1605: "Gunpowder Plot|Quixote",
    1609: "Galileo|Hudson|telescope",
    1618: "Thirty Years|Defenestration",
    1620: "Mayflower|Pilgrims|Plymouth",
    1632: "Taj Mahal|Galileo|Lützen",
    1642: "English Civil War|Tasman",
    1648: "Westphalia",
    1649: "Charles I",
    1652: "Cape|Van Riebeeck|Anglo-Dutch",
    1687: "Principia|Newton",
    1688: "Glorious Revolution|William of Orange",
    1707: "Acts of Union|Great Britain|Aurangzeb",
    1721: "Nystad|Peter the Great|Russian Empire",
    1740: "Austrian Succession|Frederick",
    1755: "Lisbon earthquake|Lisbon",
    1757: "Plassey",
    1763: "Paris|Seven Years",
    1769: "Watt|steam engine|Napoleon",
    1770: "Cook|Botany Bay|Boston Massacre",
    1776: "Declaration of Independence",
    1781: "Yorktown|Uranus",
    1787: "Constitution",
    1789: "Bastille|French Revolution",
    1791: "Haitian Revolution|Saint-Domingue|slave revolt",
    1793: "Louis XVI|guillotine|Reign of Terror",
    1798: "Pyramids|Rosetta|Napoleon",
    1804: "Napoleon|Haiti|Haitian independence",
    1805: "Trafalgar|Austerlitz",
    1807: "Slave Trade Act|abolition of the slave trade|slave trade",
    1812: "Borodino|Moscow|War of 1812",
    1815: "Waterloo|Tambora",
    1819: "Singapore|Bolívar|Bolivar|Boyacá",
    1821: "Napoleon|Greek War of Independence|Mexico|independence",
    1825: "Stockton|Darlington|railway|Decembrist",
    1833: "Slavery Abolition Act|abolition of slavery",
    1836: "Alamo|Texas",
    1839: "Opium War|Opium|photography|daguerreotype",
    1848: "revolutions|Communist Manifesto|Seneca Falls",
    1853: "Crimean War|Perry|Japan",
    1857: "Indian Rebellion|Sepoy|mutiny",
    1859: "Origin of Species|Darwin",
    1861: "Fort Sumter|American Civil War|serfdom",
    1863: "Gettysburg|Emancipation Proclamation",
    1865: "Lincoln|Thirteenth Amendment|Appomattox",
    1867: "Canada|Dominion|Meiji|Alaska",
    1869: "Suez Canal|transcontinental|Mendeleev",
    1871: "German Empire|Paris Commune|Franco-Prussian",
    1876: "Little Bighorn|telephone|Bell",
    1879: "Isandlwana|Zulu|light bulb|Edison",
    1884: "Berlin Conference|Berlin",
    1885: "Congo|Berlin|Benz|Khartoum",
    1886: "Coca-Cola|Statue of Liberty|Haymarket|Johannesburg",
    1889: "Eiffel|Brazil|republic",
    1893: "New Zealand|women's suffrage|suffrage",
    1896: "Adwa|Olympic|radioactivity",
    1898: "Spanish-American|Spanish–American|Maine|Curie|radium",
    1899: "Boer War|Boer",
    1900: "Boxer Rebellion|Boxer|Freud|Planck",
    # --- 20th century ---
    1901: "Nobel|Victoria|Marconi|Australia",
    1903: "Wright|flight",
    1905: "Einstein|relativity|Russo-Japanese|Tsushima|Bloody Sunday",
    1906: "San Francisco earthquake|earthquake",
    1908: "Model T|Ford|Tunguska|Young Turk",
    1910: "Mexican Revolution|Japan annexes Korea|Korea|Union of South Africa",
    1911: "Xinhai|Qing|Amundsen|South Pole|Machu Picchu",
    1912: "Titanic|Republic of China",
    1914: "World War I|Franz Ferdinand|Sarajevo|Panama Canal",
    1915: "Lusitania|Armenian|Gallipoli",
    1916: "Somme|Verdun|Easter Rising",
    1917: "Bolshevik|October Revolution|Balfour",
    1918: "armistice|Armistice|influenza|Spanish flu",
    1919: "Versailles|Amritsar|League of Nations",
    1920: "League of Nations|Prohibition|women the right to vote|Nineteenth Amendment",
    1922: "Mussolini|Soviet Union|Tutankhamun|Irish Free State|Turkey",
    1924: "Lenin|Stalin",
    1927: "Lindbergh|Jazz Singer|Chiang|talking",
    1928: "penicillin|Fleming|Kellogg",
    1929: "Wall Street|stock market|Lateran",
    1930: "Gandhi|Salt March|salt|World Cup",
    1931: "Empire State Building|Mukden|Manchuria|Spanish Republic",
    1932: "Hunger|Roosevelt|Iraq|neutron",
    1933: "Hitler|Reichstag|New Deal|Dachau",
    1936: "Spanish Civil War|Jesse Owens|Berlin Olympics|Rhineland",
    1937: "Nanking|Nanjing|Hindenburg|Guernica|Marco Polo Bridge",
    1938: "Anschluss|Munich Agreement|Kristallnacht",
    1939: "Germany invades Poland|invasion of Poland|World War II begins",
    1940: "Dunkirk|Battle of Britain|Blitz|France surrenders",
    1941: "Pearl Harbor|Barbarossa",
    1942: "Stalingrad|Midway|Wannsee|El Alamein",
    1943: "Stalingrad|Warsaw Ghetto|Kursk|Bengal famine",
    1944: "D-Day|Normandy|Bretton Woods",
    1945: "atomic bomb|Hiroshima|United Nations|Auschwitz|surrender",
    1946: "Nuremberg|Iron Curtain|ENIAC|Philippines",
    1947: "India|Pakistan|partition|Marshall|Dead Sea Scrolls",
    1948: "Israel|apartheid|Berlin Airlift|Universal Declaration|Gandhi",
    1949: "People's Republic of China|NATO|Germany",
    1950: "Korean War|Korea",
    1953: "double helix|DNA|Everest|Stalin|Elizabeth II",
    1954: "Dien Bien Phu|Điện Biên Phủ|Brown v.|Algerian",
    1955: "Rosa Parks|Montgomery|Warsaw Pact|Bandung",
    1956: "Suez|Hungarian Revolution|Hungary",
    1957: "Sputnik|Ghana|Treaty of Rome",
    1959: "Cuban Revolution|Castro|Dalai Lama|Tibet",
    1960: "Sharpeville|independence|Congo|Nigeria",
    1961: "Berlin Wall|Gagarin|Bay of Pigs",
    1962: "Cuban Missile Crisis|Algeria|Vatican II",
    1963: "Kennedy|March on Washington|I Have a Dream",
    1964: "Civil Rights Act|Mandela|Tokyo Olympics|Gulf of Tonkin",
    1965: "Malcolm X|Selma|Voting Rights|Indo-Pakistani",
    1966: "Cultural Revolution|World Cup",
    1967: "Six-Day War|Biafra|heart transplant",
    1968: "Martin Luther King|Tet|Prague Spring|Robert F. Kennedy",
    1969: "Apollo 11|Moon|Woodstock|Stonewall",
    1971: "Bangladesh|Intel|Attica",
    1972: "Munich|Watergate|Nixon|Bloody Sunday",
    1973: "Yom Kippur|oil embargo|Pinochet|Chile|Roe v.",
    1974: "Nixon resigns|resignation|Carnation|Haile Selassie|Lucy",
    1975: "Saigon|Vietnam War ends|Khmer Rouge|Phnom Penh|Franco",
    1976: "Soweto|Mao|Tangshan|Concorde",
    1977: "Star Wars|Elvis|Apple II|Voyager|Sadat",
    1978: "Camp David|Jonestown|test-tube|in vitro|Pope John Paul II",
    1979: "Iranian Revolution|Iran|Three Mile Island|Afghanistan|Sandinista",
    1980: "Mount St. Helens|Iran-Iraq|Iran–Iraq|John Lennon|Solidarity|Zimbabwe",
    1981: "AIDS|Sadat|Reagan|shuttle|IBM Personal Computer",
    1982: "Falklands|Sabra|Lebanon|Michael Jackson|Thriller",
    1984: "Bhopal|Indira Gandhi|famine|Macintosh|miners",
    1985: "Gorbachev|Live Aid|Titanic wreck|Mexico City earthquake",
    1986: "Chernobyl|Challenger",
    1987: "Black Monday|Intifada|ozone|Montreal Protocol",
    1988: "Lockerbie|Pan Am|Iran-Iraq|Iran–Iraq|Halabja",
    1989: "Berlin Wall|Tiananmen|Exxon Valdez|Velvet",
    1990: "Mandela|Kuwait|German reunification|Hubble",
    1991: "Soviet Union|Gulf War|Yugoslavia|apartheid",
    1992: "Bosnia|Los Angeles riots|Maastricht|Sarajevo",
    1993: "World Trade Center|Oslo Accords|European Union|Waco|Czech",
    1994: "Rwanda|Mandela|Channel Tunnel|Chechnya|NAFTA",
    1995: "Srebrenica|Oklahoma City|Rabin|Dayton|Windows 95",
    1996: "Dolly|Taliban|Kabul|Olympic|Everest",
    1997: "Diana|Hong Kong|Kyoto|Deep Blue|Mother Teresa",
    1998: "Google|Good Friday|Clinton|embassy bombings|Iraq",
    1999: "Kosovo|Columbine|euro|East Timor|Putin",
    2000: "Putin|Kursk|Bush|dot-com|Concorde",
    # --- 21st century ---
    2001: "September 11|World Trade Center|Afghanistan|2,977",
    2002: "euro|Bali|Guantanamo|Guantánamo",
    2003: "Iraq|Columbia|SARS|Saddam",
    2004: "tsunami|Madrid|Beslan|Facebook|Abu Ghraib",
    2005: "Katrina|London bombings|Kashmir earthquake|YouTube|Benedict",
    2006: "Saddam|Twitter|Pluto|North Korea|Lebanon",
    2007: "iPhone|Bhutto|subprime",
    2008: "Lehman|financial crisis|Obama|Beijing Olympics|Mumbai",
    2009: "Obama|swine flu|H1N1|Michael Jackson|Bitcoin",
    2010: "Haiti earthquake|Deepwater Horizon|Chilean miners|WikiLeaks|Bouazizi",
    2011: "Fukushima|bin Laden|Arab Spring|Mubarak|Gaddafi|South Sudan",
    2012: "Higgs|Sandy|Curiosity|Delhi|Aurora",
    2013: "Snowden|Francis|Rana Plaza|Mandela|Boston Marathon",
    2014: "Crimea|Ebola|MH370|MH17|Islamic State|Ferguson",
    2015: "Paris attacks|Paris|Nepal earthquake|Paris Agreement|refugee|Charlie Hebdo",
    2016: "Brexit|Trump|Zika|Aleppo|gravitational waves|Nice",
    2017: "Trump|Charlottesville|Hurricane Harvey|Rohingya|Grenfell|Las Vegas",
    2018: "Khashoggi|Thai cave|Kim Jong-un|March for Our Lives|Camp Fire",
    2019: "Notre-Dame|Hong Kong|black hole|Amazon|impeach|Christchurch",
    2020: "COVID-19|coronavirus|George Floyd|pandemic",
    2021: "Capitol|Taliban|Kabul|vaccine|Suez|Omicron",
    2022: "Ukraine|Russia|Elizabeth II|inflation|Roe",
    2023: "earthquake|Hamas|Gaza|OpenAI|Titan|Maui",
    2024: "election|Gaza|Assad|Trump|hurricane|Olympics",
    2025: "Trump|Gaza|Francis|Los Angeles|ceasefire",
}

# Years whose absence is the source's, not ours, kept here so nobody re-opens them.
# 2560 BC (slug -2559): Wikipedia has no article for the year, and the 26th century BC
# article dates the Great Pyramid only as a span ("c. 2551-2526 BC: Reign of Khufu"). A
# span is not a year, so the line is correctly dropped and the year gets no page.
EXPECTED_ABSENT = {-2559: "Great Pyramid — sourced only as a reign span, not a year"}

# Births are missing from 34 year pages between 1981 and 2022 and that is the source's
# absence, not ours: those year articles carry no Births section at all, only a pointer to
# "Category:1990 births". A category is a list of article titles, not a sentence anyone
# wrote, so there is nothing to quote and nothing to cite. Deaths in the same years WERE
# recoverable, because Wikipedia moved them to "Deaths in <month> <year>" rather than to a
# category, and deaths.py harvests those.
BIRTHS_NOT_PUBLISHED_UPSTREAM = [1981, 1982, 1983, 1984, 1985, 1989, 1990, 1991, 1992,
                                 1993, 1997, 1999, 2000, 2001, 2002, 2003, 2004, 2006,
                                 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015,
                                 2016, 2017, 2018, 2019, 2020, 2021, 2022]

# The other half of coverage: people. A year page has a Births and a Deaths list, and
# testing events alone cannot see that they are wrong -- which they were. Ranked with the
# genericness discount that events use, 1879 published Grace Coolidge and left out Albert
# Einstein; measured across these cases only 15 of 62 people were on the right list. Worse,
# every year from 1977 on had NO deaths at all, because Wikipedia moved them into "Deaths
# in <year>" and we never harvested it. Both are fixed; these keep them fixed.
# ("b", year) means the person must be in that year's Births; ("d", year) in its Deaths.
PEOPLE: list[tuple[int, str, str]] = [
    (1452, "b", "Leonardo"), (1475, "b", "Michelangelo"), (1519, "d", "Leonardo"),
    (1564, "b", "Shakespeare"), (1642, "d", "Galileo"), (1643, "b", "Isaac Newton"),
    (1706, "b", "Franklin"), (1727, "d", "Newton"), (1743, "b", "Jefferson"),
    (1756, "b", "Mozart"), (1769, "b", "Napoleon"), (1770, "b", "Beethoven"),
    (1791, "d", "Mozart"), (1809, "b", "Darwin"), (1809, "b", "Lincoln"),
    (1818, "b", "Karl Marx"), (1821, "d", "Napoleon"), (1827, "d", "Beethoven"),
    (1856, "b", "Freud"), (1867, "b", "Marie Curie"), (1869, "b", "Gandhi"),
    (1874, "b", "Churchill"), (1879, "b", "Einstein"), (1881, "b", "Picasso"),
    (1882, "b", "Franklin D. Roosevelt"), (1889, "b", "Hitler"), (1890, "b", "Ho Chi Minh"),
    (1890, "d", "van Gogh"), (1893, "b", "Mao"), (1898, "b", "Zhou Enlai"),
    (1899, "b", "Borges"), (1901, "b", "Hirohito"), (1910, "b", "Mother Teresa"),
    (1912, "b", "Alan Turing"), (1917, "b", "Kennedy"), (1918, "b", "Mandela"),
    (1926, "b", "Elizabeth II"), (1927, "b", "García Márquez"), (1928, "b", "Che Guevara"),
    (1929, "b", "Martin Luther King"), (1934, "d", "Curie"),
    (1935, "b", "Presley"), (1940, "b", "John Lennon"), (1945, "d", "Hitler"),
    (1945, "d", "Roosevelt"), (1948, "d", "Gandhi"), (1954, "d", "Turing"),
    (1955, "b", "Steve Jobs"), (1955, "d", "Einstein"), (1958, "b", "Michael Jackson"),
    (1963, "d", "Kennedy"), (1965, "d", "Churchill"), (1967, "d", "Che Guevara"),
    (1968, "d", "Martin Luther King"), (1973, "d", "Picasso"), (1976, "d", "Mao"),
    (1977, "d", "Presley"), (1980, "d", "Lennon"), (1989, "d", "Hirohito"),
    (1997, "d", "Diana"), (1997, "d", "Teresa"), (2009, "d", "Michael Jackson"),
    (2011, "d", "Steve Jobs"), (2013, "d", "Mandela"), (2014, "d", "García Márquez"),
    (2016, "d", "Muhammad Ali"), (2018, "d", "Hawking"), (2022, "d", "Elizabeth II"),
    (2013, "d", "Achebe"),
]
# Deliberately NOT here: Chinua Achebe among the 1930 births. 1930 has 334 sourced births
# and the page shows 14; he ranks just below Neil Armstrong, Buzz Aldrin, Clint Eastwood,
# Warren Buffett, Harvey Milk and Mobutu Sese Seko. A case belongs in this file only when
# its absence would be a defect, not when a fixed cap put someone reasonable below the
# line -- otherwise the test stops meaning anything. His death is tested instead.

DAY_CASES: list[tuple[str, str]] = [
    ("july-4", "Declaration of Independence"),
    ("december-7", "Pearl Harbor"),
    ("june-6", "D-Day|Normandy"),
    ("july-20", "Moon|Apollo"),
    ("november-9", "Berlin Wall"),
    ("september-11", "September 11|2,977"),
    ("july-14", "Bastille"),
    ("april-15", "Titanic|Lincoln|Notre-Dame"),
    ("may-8", "Victory in Europe|V-E|surrender"),
    ("august-6", "Hiroshima"),
    ("october-29", "Wall Street|stock market"),       # (regression) day spans
    ("january-1", "euro|Cuba|Republic"),
    ("february-14", "Valentine|massacre"),
    ("march-15", "Ides|Caesar"),
    ("december-25", "Charlemagne|Soviet|Christmas"),
]


def load_year(site: str, year: int):
    p = os.path.join(site, f"{year}.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def year_text(site: str, year: int) -> str | None:
    d = load_year(site, year)
    if d is None:
        return None
    return "\n".join(i["text"] for s in d.get("sections", []) for i in s["items"])


def year_all_text(site: str, year: int) -> str | None:
    """entries plus the lead -- the lead is displayed but is not an entry."""
    d = load_year(site, year)
    if d is None:
        return None
    body = "\n".join(i["text"] for s in d.get("sections", []) for i in s["items"])
    return (d.get("lead") or "") + "\n" + body


def date_text(site: str, slug: str) -> str | None:
    p = os.path.join(site, "dates", f"{slug}.json")
    if not os.path.exists(p):
        return None
    return json.dumps(json.load(open(p, encoding="utf-8")), ensure_ascii=False)


def hit(hay: str | None, phrase: str) -> str | None:
    if not hay:
        return None
    low = hay.lower()
    for p in phrase.split("|"):
        if p.strip().lower() in low:
            return p.strip()
    return None


_claims_cache: dict[int, str] = {}


def claims_text(claims_dir: str, year: int) -> str:
    if year in _claims_cache:
        return _claims_cache[year]
    txt = ""
    for pat in (f"{year}.json", f"{year}.jsonl", f"{year}.ndjson"):
        p = os.path.join(claims_dir, pat)
        if os.path.exists(p):
            txt = open(p, encoding="utf-8", errors="replace").read()
            break
    _claims_cache[year] = txt
    return txt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default=os.path.join(ROOT, "data", "site"))
    ap.add_argument("--claims", default=os.path.join(ROOT, "data", "claims"))
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    rows = []
    for year, phrase in sorted(CASES.items()):
        entries = year_text(a.site, year)
        h = hit(entries, phrase)
        state = "ok" if h else ("nopage" if entries is None else "missing")
        row = {"where": str(year), "phrase": phrase, "state": state, "matched": h}
        if state == "missing" and a.explain:
            ct = claims_text(a.claims, year)
            row["in_claims"] = bool(hit(ct, phrase))
            row["in_lead"] = bool(hit(year_all_text(a.site, year), phrase))
        rows.append(row)
    for year, kind, name in PEOPLE:
        want = "Births" if kind == "b" else "Deaths"
        d = load_year(a.site, year)
        state = "nopage"
        if d is not None:
            listed = "\n".join(i["text"] for s in d["sections"]
                                if s["title"] == want for i in s["items"])
            state = "ok" if hit(listed, name) else "missing"
        rows.append({"where": f"{year} {want}", "phrase": name, "state": state,
                     "matched": name if state == "ok" else None})

    for slug, phrase in DAY_CASES:
        t = date_text(a.site, slug)
        h = hit(t, phrase)
        rows.append({"where": f"/on/{slug}", "phrase": phrase,
                     "state": "ok" if h else "missing", "matched": h})

    bad = [r for r in rows if r["state"] != "ok"]
    print(f"famous: {len(rows) - len(bad)}/{len(rows)} present "
          f"({100 * (len(rows) - len(bad)) / len(rows):.1f}%)")
    for r in bad:
        extra = ""
        if a.explain and r["state"] == "missing":
            extra = "  [in claims, dropped by build]" if r.get("in_claims") else "  [never extracted]"
            if r.get("in_lead"):
                extra += " [but IS in the lead]"
        print(f"  {r['state'].upper():>7}  {r['where']:>12}  {r['phrase']}{extra}")
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
