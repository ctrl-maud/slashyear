"""Independent check list for the office holders the year pages name.

Wikidata's P39 statements are uneven: terms go missing, rebels and occupiers are
recorded as holders, a dictatorship is entered as a person. facts.py publishes a state's
office for a year only when the set of people Wikidata puts in it that year matches this
list exactly; any year that disagrees is left out rather than shown. Each entry is
(token that appears in the holder's Wikidata label, first year, last year), acting
holders included, written from
the official lists (whitehouse.gov, gov.uk, pm.gc.ca, bundeskanzler.de, elysee.fr).
"""

US_PRESIDENT = [
    ("John Adams", 1797, 1801), ("Jefferson", 1801, 1809), ("Madison", 1809, 1817), ("Monroe", 1817, 1825),
    ("John Quincy Adams", 1825, 1829), ("Andrew Jackson", 1829, 1837), ("Van Buren", 1837, 1841),
    ("William Henry Harrison", 1841, 1841), ("John Tyler", 1841, 1845), ("Polk", 1845, 1849),
    ("Zachary Taylor", 1849, 1850), ("Fillmore", 1850, 1853), ("Franklin Pierce", 1853, 1857),
    ("Buchanan", 1857, 1861), ("Lincoln", 1861, 1865), ("Andrew Johnson", 1865, 1869),
    ("Grant", 1869, 1877), ("Hayes", 1877, 1881), ("Garfield", 1881, 1881),
    ("Chester A. Arthur", 1881, 1885), ("Cleveland", 1885, 1889), ("Benjamin Harrison", 1889, 1893),
    ("Cleveland", 1893, 1897), ("McKinley", 1897, 1901), ("Theodore Roosevelt", 1901, 1909),
    ("Taft", 1909, 1913), ("Woodrow Wilson", 1913, 1921), ("Harding", 1921, 1923),
    ("Coolidge", 1923, 1929), ("Hoover", 1929, 1933), ("Delano Roosevelt", 1933, 1945),
    ("Truman", 1945, 1953), ("Eisenhower", 1953, 1961), ("Kennedy", 1961, 1963),
    ("Lyndon B. Johnson", 1963, 1969), ("Nixon", 1969, 1974), ("Gerald Ford", 1974, 1977),
    ("Carter", 1977, 1981), ("Reagan", 1981, 1989), ("George H. W. Bush", 1989, 1993),
    ("Clinton", 1993, 2001), ("George W. Bush", 2001, 2009), ("Obama", 2009, 2017),
    ("Trump", 2017, 2021), ("Biden", 2021, 2025), ("Trump", 2025, 2029),
]

UK_PRIME_MINISTER = [
    ("Pitt", 1800, 1801), ("Addington", 1801, 1804), ("Pitt", 1804, 1806), ("Grenville", 1806, 1807),
    ("Portland", 1807, 1809), ("Perceval", 1809, 1812), ("Liverpool", 1812, 1827),
    ("Canning", 1827, 1827), ("Goderich", 1827, 1828), ("Wellington", 1828, 1830), ("Grey", 1830, 1834),
    ("Melbourne", 1834, 1834), ("Wellington", 1834, 1834), ("Peel", 1834, 1835),
    ("Melbourne", 1835, 1841), ("Peel", 1841, 1846), ("Russell", 1846, 1852), ("Derby", 1852, 1852),
    ("Aberdeen", 1852, 1855), ("Palmerston", 1855, 1858), ("Derby", 1858, 1859),
    ("Palmerston", 1859, 1865), ("Russell", 1865, 1866), ("Derby", 1866, 1868),
    ("Disraeli", 1868, 1868), ("Gladstone", 1868, 1874), ("Disraeli", 1874, 1880),
    ("Gladstone", 1880, 1885), ("Salisbury", 1885, 1886), ("Gladstone", 1886, 1886),
    ("Salisbury", 1886, 1892), ("Gladstone", 1892, 1894), ("Rosebery", 1894, 1895),
    ("Salisbury", 1895, 1902), ("Balfour", 1902, 1905), ("Campbell-Bannerman", 1905, 1908),
    ("Asquith", 1908, 1916), ("Lloyd George", 1916, 1922), ("Bonar Law", 1922, 1923),
    ("Baldwin", 1923, 1924), ("MacDonald", 1924, 1924), ("Baldwin", 1924, 1929),
    ("MacDonald", 1929, 1935), ("Baldwin", 1935, 1937), ("Chamberlain", 1937, 1940),
    ("Churchill", 1940, 1945), ("Attlee", 1945, 1951), ("Churchill", 1951, 1955), ("Eden", 1955, 1957),
    ("Macmillan", 1957, 1963), ("Douglas-Home", 1963, 1964), ("Harold Wilson", 1964, 1970),
    ("Heath", 1970, 1974), ("Harold Wilson", 1974, 1976), ("Callaghan", 1976, 1979),
    ("Thatcher", 1979, 1990), ("John Major", 1990, 1997), ("Blair", 1997, 2007),
    ("Gordon Brown", 2007, 2010), ("Cameron", 2010, 2016), ("Theresa May", 2016, 2019),
    ("Boris Johnson", 2019, 2022), ("Truss", 2022, 2022), ("Sunak", 2022, 2024),
    ("Starmer", 2024, 2029),
]

UK_MONARCH = [
    ("George III", 1760, 1820), ("George IV", 1820, 1830), ("William IV", 1830, 1837),
    ("Victoria", 1837, 1901), ("Edward VII", 1901, 1910), ("George V", 1910, 1936),
    ("Edward VIII", 1936, 1936), ("George VI", 1936, 1952), ("Elizabeth II", 1952, 2022),
    ("Charles III", 2022, 2029),
]

CANADA_PRIME_MINISTER = [
    ("John A. Macdonald", 1867, 1873), ("Alexander Mackenzie", 1873, 1878),
    ("John A. Macdonald", 1878, 1891), ("Abbott", 1891, 1892), ("Thompson", 1892, 1894),
    ("Bowell", 1894, 1896), ("Tupper", 1896, 1896), ("Laurier", 1896, 1911), ("Borden", 1911, 1920),
    ("Meighen", 1920, 1921), ("King", 1921, 1926), ("Meighen", 1926, 1926), ("King", 1926, 1930),
    ("Bennett", 1930, 1935), ("King", 1935, 1948), ("St. Laurent", 1948, 1957),
    ("Diefenbaker", 1957, 1963), ("Pearson", 1963, 1968), ("Pierre Trudeau", 1968, 1979),
    ("Joe Clark", 1979, 1980), ("Pierre Trudeau", 1980, 1984), ("John Turner", 1984, 1984),
    ("Mulroney", 1984, 1993), ("Kim Campbell", 1993, 1993), ("Chrétien", 1993, 2003),
    ("Paul Martin", 2003, 2006), ("Harper", 2006, 2015), ("Justin Trudeau", 2015, 2025),
    ("Carney", 2025, 2029),
]

GERMANY_CHANCELLOR = [
    ("Adenauer", 1949, 1963), ("Erhard", 1963, 1966), ("Kiesinger", 1966, 1969), ("Brandt", 1969, 1974), ("Scheel", 1974, 1974),
    ("Helmut Schmidt", 1974, 1982), ("Kohl", 1982, 1998), ("Schröder", 1998, 2005),
    ("Merkel", 2005, 2021), ("Scholz", 2021, 2025), ("Merz", 2025, 2029),
]

FRANCE_PRESIDENT = [
    ("Coty", 1954, 1959), ("de Gaulle", 1959, 1969), ("Poher", 1969, 1969), ("Pompidou", 1969, 1974), ("Poher", 1974, 1974),
    ("Giscard", 1974, 1981), ("Mitterrand", 1981, 1995), ("Chirac", 1995, 2007),
    ("Sarkozy", 2007, 2012), ("Hollande", 2012, 2017), ("Macron", 2017, 2029),
]

# state chain (as named in leaders.json), role, the years the list covers, the list.
CHECKED = [
    (["United States"], "head_of_state", (1801, 2025), US_PRESIDENT),
    (["United Kingdom", "United Kingdom of Great Britain and Ireland"], "head_of_state", (1801, 2025), UK_MONARCH),
    (["United Kingdom", "United Kingdom of Great Britain and Ireland"], "head_of_government", (1801, 2025), UK_PRIME_MINISTER),
    (["Canada"], "head_of_government", (1867, 2025), CANADA_PRIME_MINISTER),
    (["Germany", "West Germany"], "head_of_government", (1949, 2025), GERMANY_CHANCELLOR),
    (["France", "French Fifth Republic"], "head_of_state", (1959, 2025), FRANCE_PRESIDENT),
]
