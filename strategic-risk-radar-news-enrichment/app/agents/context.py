COUNTRIES = {
    "united arab emirates": ("United Arab Emirates", "ARE"),
    "uae": ("United Arab Emirates", "ARE"),
    "iran": ("Iran", "IRN"),
    "egypt": ("Egypt", "EGY"),
    "russia": ("Russia", "RUS"),
    "ukraine": ("Ukraine", "UKR"),
    "china": ("China", "CHN"),
    "india": ("India", "IND"),
    "saudi arabia": ("Saudi Arabia", "SAU"),
    "qatar": ("Qatar", "QAT"),
    "oman": ("Oman", "OMN"),
    "iraq": ("Iraq", "IRQ"),
    "israel": ("Israel", "ISR"),
    "yemen": ("Yemen", "YEM"),
}

AIRPORTS = {
    "dubai international airport": ("Dubai International Airport", "DXB", "ARE"),
    "dxb": ("Dubai International Airport", "DXB", "ARE"),
    "abu dhabi international airport": ("Zayed International Airport", "AUH", "ARE"),
    "zayed international airport": ("Zayed International Airport", "AUH", "ARE"),
    "cairo international airport": ("Cairo International Airport", "CAI", "EGY"),
}

PORTS = {
    "jebel ali": ("Jebel Ali Port", "AEJEA", "ARE"),
    "port rashid": ("Port Rashid", "AEPRA", "ARE"),
    "fujairah": ("Port of Fujairah", "AEFJR", "ARE"),
    "suez canal": ("Suez Canal", "EGSUZ", "EGY"),
    "strait of hormuz": ("Strait of Hormuz", "IRHOM", "IRN"),
}

RISK_TERMS = {
    "blocked": 90,
    "closure": 80,
    "closed": 80,
    "attack": 75,
    "war": 75,
    "missile": 75,
    "sanctions": 65,
    "disruption": 60,
    "delay": 45,
    "fraud": 55,
    "trafficking": 70,
    "visa": 40,
    "refugee": 55,
}

TRANSPORT_TERMS = (
    "cargo",
    "shipping",
    "port",
    "vessel",
    "airport",
    "airspace",
    "flight",
    "airline",
    "customs",
    "border",
    "visa",
    "passport",
    "migration",
    "refugee",
    "trafficking",
    "smuggling",
)

ICP_KPIS = (
    "Airport Operations",
    "Passenger Flow",
    "Port Operations",
    "Cargo Clearance",
    "Maritime Route Continuity",
    "Border Security",
    "Visa and Residency Compliance",
    "Identity and Document Fraud",
    "Migration Pressure",
    "Government Service Continuity",
)
