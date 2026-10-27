# -*- coding: utf-8 -*-
"""Rattache un pays ou une région (nom anglais) à une piste du registre.

Utilisé par recolter_sources.py pour Wikidata, les chronologies Wikipédia et
PeriodO. Les clés sont celles de la colonne « Nom (clé) » de l'onglet
« Lignes du temps » ; generer_donnees.py écarte toute clé absente du registre.
"""
import re
import unicodedata

EGYPTE = "Egypt"
MESO_LEVANT = "Mesopotamia & Levant – Mesopotamia and the Levant"
ROME = "Rome And Persia – Roman Era"
PERSE = "Rome And Persia – PERSIA (Iran)"
ANATOLIE = "Anatolia & Turkey – Anatolia (modern Turkey)"
INDE = "India – India, Pakistan & Bangladesh"
CHINE = "China"
GRECE = "Greece"
ITALIE_RENAISSANCE = "European Monarchies – RENAISSANCE ITALY"
YOUGOSLAVIE = "Southern Europe – former Yugoslavia"
TCHECOSLOVAQUIE = "Eastern Europe – Czechoslovakia"
RU = "Uk & Ireland"
IRLANDE = "Uk & Ireland – IRELAND"
USA = "Uk & Ireland – UNITED STATES OF AMERICA"
CARAIBES = "Caribbean – Caribbean Region"
MESOAMERIQUE = "Mesoamerica"
AMSUD = "South America"
OCEANIE = "Australia – Australia, New Zealand and Oceania"
GUERRES = "Wars And Battles"
AUTRES = "Other Events – Other Events and Developments"

# Pistes « Période » : PeriodO y range ses périodes quand le pays en a une.
PISTE_PERIODE = {
    EGYPTE: "Egypt – Period",
    CHINE: "China – Chinese Period",
    GRECE: "Greece – Greek Period",
}

_PAYS = {
    "Egypt": EGYPTE, "Ancient Egypt": EGYPTE,
    "Iraq": "Mesopotamia & Levant – Iraq",
    "Syria": "Mesopotamia & Levant – Syria",
    "Jordan": "Mesopotamia & Levant – Jordan",
    "Lebanon": "Mesopotamia & Levant – Lebanon",
    "Israel": "Mesopotamia & Levant – Israel",
    "State of Palestine": "Mesopotamia & Levant – Palestine",
    "Palestine": "Mesopotamia & Levant – Palestine",
    "Gaza Strip": "Mesopotamia & Levant – Palestine",
    "West Bank": "Mesopotamia & Levant – Palestine",
    "Palestinian territories": "Mesopotamia & Levant – Palestine",
    "Cyprus": "Mesopotamia & Levant – Cyprus",
    "Armenia": "West Asia – Armenia",
    "Azerbaijan": "West Asia – Azerbaijan",
    "Georgia": "West Asia – Georgia",
    "Saudi Arabia": "Arabian Peninsula – Central",
    "Yemen": "Arabian Peninsula – South",
    "Oman": "Arabian Peninsula – East",
    "United Arab Emirates": "Arabian Peninsula – East",
    "Qatar": "Arabian Peninsula – East",
    "Bahrain": "Arabian Peninsula – East",
    "Kuwait": "Arabian Peninsula – North",
    "Turkey": ANATOLIE, "Türkiye": ANATOLIE,
    "Kazakhstan": "Central Asia – Kazakhstan",
    "Kyrgyzstan": "Central Asia – Kyrgyzstan",
    "Tajikistan": "Central Asia – Tajikistan",
    "Turkmenistan": "Central Asia – Turkmenistan",
    "Uzbekistan": "Central Asia – Uzbekistan",
    "Afghanistan": "South Asia – Afghanistan",
    "Bhutan": "South Asia – Bhutan",
    "Maldives": "South Asia – Maldives",
    "Nepal": "South Asia – Nepal",
    "Sri Lanka": "South Asia – Sri Lanka",
    "India": INDE, "Pakistan": INDE, "Bangladesh": INDE,
    "Brunei": "Southeast Asia – Brunei",
    "Cambodia": "Southeast Asia – Cambodia",
    "East Timor": "Southeast Asia – East Timor",
    "Timor-Leste": "Southeast Asia – East Timor",
    "Indonesia": "Southeast Asia – Indonesia",
    "Laos": "Southeast Asia – Laos",
    "Malaysia": "Southeast Asia – Malaysia",
    "Myanmar": "Southeast Asia – Myanmar",
    "Philippines": "Southeast Asia – The Philippines",
    "Singapore": "Southeast Asia – Singapore",
    "Thailand": "Southeast Asia – Thailand",
    "Vietnam": "Southeast Asia – Vietnam",
    "Mongolia": "East Asia – Mongolia",
    "North Korea": "East Asia – Korea", "South Korea": "East Asia – Korea",
    "Korea": "East Asia – Korea",
    "Japan": "East Asia – Japan",
    "China": CHINE, "People's Republic of China": CHINE, "Taiwan": CHINE,
    "Hong Kong": CHINE, "Macau": CHINE, "Tibet": CHINE,
    "Iran": PERSE,
    "Greece": GRECE, "Crete": GRECE,
    "Denmark": "Northern Europe – Denmark",
    "Norway": "Northern Europe – Norway",
    "Sweden": "Northern Europe – Sweden",
    "Finland": "Northern Europe – Finland",
    "Iceland": "Northern Europe – Iceland",
    "Estonia": "Northern Europe – Estonia",
    "Latvia": "Northern Europe – Latvia",
    "Lithuania": "Northern Europe – Lithuania",
    "Albania": "Southern Europe – Albania",
    "Andorra": "Southern Europe – Andorra",
    "Malta": "Southern Europe – Malta",
    "Portugal": "Southern Europe – Portugal",
    "Spain": "Southern Europe – Spain",
    "San Marino": "Southern Europe – San Marino",
    "Serbia": YOUGOSLAVIE, "Croatia": YOUGOSLAVIE,
    "Bosnia and Herzegovina": YOUGOSLAVIE, "Slovenia": YOUGOSLAVIE,
    "Montenegro": YOUGOSLAVIE, "North Macedonia": YOUGOSLAVIE,
    "Kosovo": YOUGOSLAVIE, "Yugoslavia": YOUGOSLAVIE,
    "Belarus": "Eastern Europe – Belarus",
    "Bulgaria": "Eastern Europe – Bulgaria",
    "Czech Republic": TCHECOSLOVAQUIE, "Czechia": TCHECOSLOVAQUIE,
    "Slovakia": TCHECOSLOVAQUIE, "Czechoslovakia": TCHECOSLOVAQUIE,
    "Hungary": "Eastern Europe – Hungary",
    "Moldova": "Eastern Europe – Moldova",
    "Poland": "Eastern Europe – Poland",
    "Romania": "Eastern Europe – Romania",
    "Russia": "Eastern Europe – Russia", "Soviet Union": "Eastern Europe – Russia",
    "Russian Empire": "Eastern Europe – Russia",
    "Ukraine": "Eastern Europe – Ukraine",
    "Netherlands": "Western Europe – The Netherlands",
    "Kingdom of the Netherlands": "Western Europe – The Netherlands",
    "Belgium": "Western Europe – Belgium",
    "Luxembourg": "Western Europe – Luxembourg",
    "Austria": "Western Europe – Austria",
    "Liechtenstein": "Western Europe – Liechtenstein",
    "Monaco": "Western Europe – Monaco",
    "Switzerland": "Western Europe – Switzerland",
    "France": "France",
    "Germany": "Germany",
    "United Kingdom": RU, "England": RU, "Scotland": RU, "Wales": RU,
    "Northern Ireland": RU, "Great Britain": RU,
    "Ireland": IRLANDE, "Republic of Ireland": IRLANDE,
    "United States": USA, "United States of America": USA,
    "Canada": "Canada",
    "Mexico": MESOAMERIQUE, "Guatemala": MESOAMERIQUE, "Belize": MESOAMERIQUE,
    "Honduras": MESOAMERIQUE, "El Salvador": MESOAMERIQUE,
    "Nicaragua": MESOAMERIQUE, "Costa Rica": MESOAMERIQUE,
    "Panama": MESOAMERIQUE,
    "Algeria": "Africa – Algeria",
    "Libya": "Africa – Libya",
    "Morocco": "Africa – Morocco",
    "Sudan": "Africa – Sudan", "South Sudan": "Africa – Sudan",
    "Tunisia": "Africa – Tunisia",
    "Western Sahara": "Africa – Western Sahara",
    "Burundi": "Africa – Burundi",
    "Comoros": "Africa – Comoros",
    "Djibouti": "Africa – Djibouti",
    "Ethiopia": "Africa – Ethiopia",
    "Eritrea": "Africa – Eritrea",
    "Kenya": "Africa – Kenya",
    "Madagascar": "Africa – Madagascar",
    "Malawi": "Africa – Malawi",
    "Mauritius": "Africa – Mauritius",
    "Mozambique": "Africa – Mozambique",
    "Réunion": "Africa – Réunion",
    "Rwanda": "Africa – Rwanda",
    "Seychelles": "Africa – Seychelles",
    "Somalia": "Africa – Somalia",
    "Somaliland": "Africa – Somaliland",
    "Tanzania": "Africa – Tanzania",
    "Uganda": "Africa – Uganda",
    "Zambia": "Africa – Zambia",
    "Zimbabwe": "Africa – Zimbabwe",
    "Benin": "Africa – Benin",
    "Burkina Faso": "Africa – Burkina Faso",
    "Cape Verde": "Africa – Cape Verde",
    "Ivory Coast": "Africa – Côte D'Ivoire", "Côte d'Ivoire": "Africa – Côte D'Ivoire",
    "The Gambia": "Africa – Gambia", "Gambia": "Africa – Gambia",
    "Ghana": "Africa – Ghana",
    "Guinea": "Africa – Guinea",
    "Guinea-Bissau": "Africa – Guinea-Bissau",
    "Liberia": "Africa – Liberia",
    "Mali": "Africa – Mali",
    "Mauritania": "Africa – Mauritania",
    "Niger": "Africa – Niger",
    "Nigeria": "Africa – Nigeria",
    "Senegal": "Africa – Senegal",
    "Sierra Leone": "Africa – Sierra Leone",
    "Togo": "Africa – Togo",
    "Angola": "Africa – Angola",
    "Cameroon": "Africa – Cameroon",
    "Central African Republic": "Africa – Central African",
    "Chad": "Africa – Chad",
    "Republic of the Congo": "Africa – Republic of the Congo",
    "Democratic Republic of the Congo": "Africa – Democratic Republic",
    "Equatorial Guinea": "Africa – Equatorial Guinea",
    "Gabon": "Africa – Gabon",
    "São Tomé and Príncipe": "Africa – São Tomé & Principe",
    "Botswana": "Africa – Botswana",
    "Lesotho": "Africa – Lesotho",
    "Namibia": "Africa – Namibia",
    "South Africa": "Africa – South Africa",
    "Eswatini": "Africa – Swaziland", "Swaziland": "Africa – Swaziland",
}
for _p in ("Cuba", "Haiti", "Dominican Republic", "Jamaica", "The Bahamas",
           "Bahamas", "Barbados", "Trinidad and Tobago", "Puerto Rico",
           "Grenada", "Saint Lucia", "Dominica", "Antigua and Barbuda",
           "Saint Vincent and the Grenadines", "Saint Kitts and Nevis",
           "Guadeloupe", "Martinique", "Curaçao", "Aruba"):
    _PAYS[_p] = CARAIBES
for _p in ("Brazil", "Argentina", "Chile", "Peru", "Colombia", "Venezuela",
           "Ecuador", "Bolivia", "Paraguay", "Uruguay", "Guyana", "Suriname",
           "French Guiana"):
    _PAYS[_p] = AMSUD
for _p in ("Australia", "New Zealand", "Papua New Guinea", "Fiji", "Samoa",
           "Tonga", "Vanuatu", "Solomon Islands", "Kiribati", "Tuvalu",
           "Nauru", "Palau", "Marshall Islands", "Federated States of Micronesia",
           "New Caledonia", "French Polynesia", "Hawaii", "Easter Island"):
    _PAYS[_p] = OCEANIE
for _p in ("Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
           "Connecticut", "Delaware", "Florida", "Idaho", "Illinois", "Indiana",
           "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
           "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
           "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
           "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
           "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
           "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
           "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin",
           "Wyoming"):
    _PAYS[_p] = USA
for _p in ("Quebec", "Ontario", "British Columbia", "Alberta", "Manitoba",
           "Saskatchewan", "Nova Scotia", "New Brunswick", "Newfoundland and Labrador",
           "Prince Edward Island", "Acadia", "New France"):
    _PAYS[_p] = "Canada"

ITALIE = "@italie"     # piste choisie selon l'époque, voir piste_pour()
for _p in ("Italy", "Vatican City", "Sicily", "Sardinia"):
    _PAYS[_p] = ITALIE

# États historiques et dynasties : mot repéré dans le nom anglais. L'ordre
# compte (« Holy Roman » avant « Roman », « Córdoba » avant « Umayyad »).
_MOTS = [
    ("holy roman", "Germany"), ("romania", "Eastern Europe – Romania"),
    ("byzantin", ROME), ("eastern roman", ROME),
    ("roman", ROME), ("rome", ROME),
    ("ottoman", ANATOLIE), ("seljuk", ANATOLIE), ("hittite", ANATOLIE),
    ("lydia", ANATOLIE), ("phrygia", ANATOLIE), ("anatolia", ANATOLIE),
    ("achaemenid", PERSE), ("sasanian", PERSE), ("sassanid", PERSE),
    ("parthia", PERSE), ("safavid", PERSE), ("qajar", PERSE), ("persia", PERSE),
    ("afsharid", PERSE), ("medes", PERSE), ("elam", PERSE),
    ("mughal", INDE), ("maratha", INDE), ("delhi", INDE), ("maurya", INDE),
    ("gupta", INDE), ("chola", INDE), ("vijayanagara", INDE),
    ("british raj", INDE), ("sikh", INDE), ("bengal", INDE),
    ("qing", CHINE), ("ming dynasty", CHINE), ("yuan dynasty", CHINE),
    ("song dynasty", CHINE), ("tang dynasty", CHINE), ("han dynasty", CHINE),
    ("zhou dynasty", CHINE), ("shang dynasty", CHINE), ("jin dynasty", CHINE),
    ("republic of china", CHINE), ("manchukuo", CHINE), ("chinese", CHINE),
    ("japan", "East Asia – Japan"), ("shogunate", "East Asia – Japan"),
    ("joseon", "East Asia – Korea"), ("goryeo", "East Asia – Korea"),
    ("silla", "East Asia – Korea"), ("baekje", "East Asia – Korea"),
    ("goguryeo", "East Asia – Korea"), ("korea", "East Asia – Korea"),
    ("golden horde", "Eastern Europe – Russia"), ("mongol", "East Asia – Mongolia"),
    ("kievan", "Eastern Europe – Ukraine"), ("cossack", "Eastern Europe – Ukraine"),
    ("russia", "Eastern Europe – Russia"), ("muscovy", "Eastern Europe – Russia"),
    ("moscow", "Eastern Europe – Russia"), ("novgorod", "Eastern Europe – Russia"),
    ("soviet", "Eastern Europe – Russia"),
    ("francia", "France"), ("frankish", "France"), ("franks", "France"), ("carolingian", "France"),
    ("merovingian", "France"), ("france", "France"), ("french", "France"),
    ("gaul", "France"),
    ("prussia", "Germany"), ("german", "Germany"), ("bavaria", "Germany"),
    ("saxony", "Germany"), ("hanover", "Germany"), ("nazi", "Germany"),
    ("weimar", "Germany"), ("rhine", "Germany"),
    ("irish", IRLANDE), ("ireland", IRLANDE),
    ("england", RU), ("english", RU), ("britain", RU), ("british", RU),
    ("scotland", RU), ("scottish", RU), ("wales", RU), ("anglo-saxon", RU),
    ("mercia", RU), ("wessex", RU), ("northumbria", RU),
    ("córdoba", "Southern Europe – Spain"), ("cordoba", "Southern Europe – Spain"),
    ("al-andalus", "Southern Europe – Spain"), ("castile", "Southern Europe – Spain"),
    ("aragon", "Southern Europe – Spain"), ("navarre", "Southern Europe – Spain"),
    ("granada", "Southern Europe – Spain"), ("spain", "Southern Europe – Spain"),
    ("spanish", "Southern Europe – Spain"), ("visigoth", "Southern Europe – Spain"),
    ("umayyad", "Mesopotamia & Levant – Syria"),
    ("abbasid", "Mesopotamia & Levant – Iraq"),
    ("fatimid", EGYPTE), ("mamluk", EGYPTE), ("ptolemaic", EGYPTE),
    ("ayyubid", EGYPTE), ("egypt", EGYPTE),
    ("rashidun", "Arabian Peninsula – Central"),
    ("portug", "Southern Europe – Portugal"),
    ("poland", "Eastern Europe – Poland"), ("polish", "Eastern Europe – Poland"),
    ("lithuania", "Northern Europe – Lithuania"),
    ("habsburg", "Western Europe – Austria"), ("austria", "Western Europe – Austria"),
    ("hungar", "Eastern Europe – Hungary"),
    ("bohemia", TCHECOSLOVAQUIE), ("moravia", TCHECOSLOVAQUIE),
    ("serbia", YOUGOSLAVIE), ("croatia", YOUGOSLAVIE), ("bosnia", YOUGOSLAVIE),
    ("yugoslav", YOUGOSLAVIE),
    ("bulgaria", "Eastern Europe – Bulgaria"),
    ("wallachia", "Eastern Europe – Romania"), ("moldavia", "Eastern Europe – Romania"),
    ("dacia", "Eastern Europe – Romania"),
    ("venice", ITALIE), ("venetian", ITALIE), ("genoa", ITALIE),
    ("florence", ITALIE), ("milan", ITALIE), ("naples", ITALIE),
    ("papal", ITALIE), ("savoy", ITALIE), ("lombard", ITALIE),
    ("ostrogoth", ITALIE), ("tuscany", ITALIE), ("italy", ITALIE), ("italian", ITALIE),
    ("dutch", "Western Europe – The Netherlands"),
    ("netherlands", "Western Europe – The Netherlands"),
    ("swed", "Northern Europe – Sweden"), ("danish", "Northern Europe – Denmark"),
    ("denmark", "Northern Europe – Denmark"), ("norw", "Northern Europe – Norway"),
    ("seleucid", "Mesopotamia & Levant – Syria"),
    ("athen", GRECE), ("sparta", GRECE), ("macedon", GRECE), ("greek", GRECE),
    ("hellenic", GRECE), ("mycenae", GRECE), ("minoan", GRECE),
    ("assyria", MESO_LEVANT), ("babylon", MESO_LEVANT), ("akkad", MESO_LEVANT),
    ("sumer", MESO_LEVANT), ("mesopotamia", MESO_LEVANT), ("mitanni", MESO_LEVANT),
    ("carthag", "Africa – Tunisia"), ("hafsid", "Africa – Tunisia"),
    ("aghlabid", "Africa – Tunisia"),
    ("almohad", "Africa – Morocco"), ("almoravid", "Africa – Morocco"),
    ("marinid", "Africa – Morocco"),
    ("aztec", MESOAMERIQUE), ("maya", MESOAMERIQUE), ("mexic", MESOAMERIQUE),
    ("olmec", MESOAMERIQUE), ("inca", AMSUD),
    ("confederate states", USA), ("united states", USA),
    ("aksum", "Africa – Ethiopia"), ("ethiopia", "Africa – Ethiopia"),
    ("mali empire", "Africa – Mali"), ("songhai", "Africa – Mali"),
    ("ghana empire", "Africa – Ghana"), ("zulu", "Africa – South Africa"),
    ("kush", "Africa – Sudan"), ("nubia", "Africa – Sudan"),
    ("khmer", "Southeast Asia – Cambodia"), ("siam", "Southeast Asia – Thailand"),
    ("ayutthaya", "Southeast Asia – Thailand"), ("sukhothai", "Southeast Asia – Thailand"),
    ("đại việt", "Southeast Asia – Vietnam"), ("champa", "Southeast Asia – Vietnam"),
    ("burm", "Southeast Asia – Myanmar"), ("majapahit", "Southeast Asia – Indonesia"),
    ("srivijaya", "Southeast Asia – Indonesia"), ("mataram", "Southeast Asia – Indonesia"),
    ("timurid", "Central Asia – Uzbekistan"),
    ("urartu", "West Asia – Armenia"), ("armenia", "West Asia – Armenia"),
    ("georgia", "West Asia – Georgia"),
    ("israel", "Mesopotamia & Levant – Israel"), ("judah", "Mesopotamia & Levant – Israel"),
    ("judea", "Mesopotamia & Levant – Israel"), ("hasmonean", "Mesopotamia & Levant – Israel"),
    ("phoenicia", "Mesopotamia & Levant – Phoenicia"),
    ("nabataea", "Mesopotamia & Levant – Jordan"),
]


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def piste_pour(nom, annee=None):
    """Nom anglais d'un pays, d'une région ou d'un État → clé de piste, ou None."""
    if not nom:
        return None
    nom = nom.strip()
    cle = _PAYS.get(nom)
    if cle is None:
        bas = nom.lower()
        for mot, c in _MOTS:
            if mot in bas:
                cle = c
                break
    if cle == ITALIE:
        # Pas de piste « Italie » : Rome jusqu'à la chute de l'Empire
        # d'Occident, l'Italie de la Renaissance ensuite.
        return ROME if annee is not None and annee < 476 else ITALIE_RENAISSANCE
    return cle


def cle_titre(s):
    """Forme normalisée d'un intitulé, pour rapprocher les doublons."""
    s = sans_accents(str(s or "")).lower()
    s = re.sub(r"\([^)]*\)", " ", s)              # « (1066) », « (AD 192 - 1832) »
    s = re.sub(r"[’'`]", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    mots = [m for m in s.split() if m not in
            {"the", "a", "an", "of", "la", "le", "les", "l", "de", "du", "des", "d",
             "et", "and", "en", "in"}]
    # années isolées en fin d'intitulé : « Battle of X 1066 »
    while mots and re.fullmatch(r"\d{3,4}", mots[-1]):
        mots.pop()
    return " ".join(mots)
