SEED = 42
START_DATE = "2026-04-01"
END_DATE = "2026-09-30"
N_CUSTOMERS = 30000

# (bank_id, bank_name, bank_type, size_tier). All names are fictional.
BANKS = [
    (1, "Aurex National", "Public", "Large"),
    (2, "Vantara", "Private", "Large"),
    (3, "Solace", "Private", "Large"),
    (4, "Kestrel Commercial", "Private", "Large"),
    (5, "Meridian Union", "Public", "Large"),
    (6, "Zenora", "Private", "Large"),
    (7, "Halcyon Federal", "Private", "Large"),
    (8, "Tarang National", "Public", "Large"),
    (9, "Ridgeway", "Private", "Medium"),
    (10, "Lumora", "Private", "Medium"),
    (11, "Orchid Trust", "Private", "Medium"),
    (12, "Sagar Mercantile", "Public", "Medium"),
    (13, "Nexora", "Private", "Medium"),
    (14, "Cedarline", "Private", "Medium"),
    (15, "Prismatic", "Private", "Medium"),
    (16, "Kiran Finance", "Private", "Medium"),
    (17, "Banyan", "Public", "Medium"),
    (18, "Quillon", "Private", "Medium"),
    (19, "Harbor Crest", "Private", "Medium"),
    (20, "Ambera", "Private", "Medium"),
    (21, "Vela Small Finance", "Small Finance", "Medium"),
    (22, "Tidewater", "Private", "Medium"),
    (23, "Gram Vikas", "Co-operative", "Small"),
    (24, "Nagar Seva", "Co-operative", "Small"),
    (25, "Lokmitra", "Co-operative", "Small"),
    (26, "Janta Pragati", "Co-operative", "Small"),
    (27, "Shree Anand", "Co-operative", "Small"),
    (28, "Rajhans", "Co-operative", "Small"),
    (29, "Ekta Nagarik", "Co-operative", "Small"),
    (30, "Kaveri Grameen", "Regional Rural", "Small"),
    (31, "Sundarbans Grameen", "Regional Rural", "Small"),
    (32, "Malwa Kshetriya Gramin", "Regional Rural", "Small"),
    (33, "Deccan Gramin", "Regional Rural", "Small"),
    (34, "Himal Gramin", "Regional Rural", "Small"),
    (35, "Udaan", "Small Finance", "Small"),
    (36, "Pragati", "Small Finance", "Small"),
    (37, "Swift Wallet", "Payments Bank", "Small"),
    (38, "Dhan Pay", "Payments Bank", "Small"),
    (39, "Instapay", "Payments Bank", "Small"),
    (40, "Rupee Link", "Payments Bank", "Small"),
]

# Share of total volume per tier. Within a tier, banks share volume equally.
TIER_VOLUME_SHARE = {"Large": 0.70, "Medium": 0.22, "Small": 0.08}
# Base bank-side failure rate per tier (calibrated against the overall target in step 2C).
BANK_BASE_FAIL = {"Large": 0.08, "Medium": 0.11, "Small": 0.16}

# (psp_id, psp_name, provider_type, volume_share). All names are fictional.
PSPS = [
    (1, "PayNova", "Sponsor bank", 0.28),
    (2, "Rapidix", "Aggregator", 0.22),
    (3, "TransactLink", "Aggregator", 0.18),
    (4, "Clearwave", "Sponsor bank", 0.14),
    (5, "Finbridge", "Direct", 0.09),
    (6, "QuickRail", "Aggregator", 0.06),
    (7, "Zenith Gateway", "Direct", 0.03),
]

# (error_code, category, description, retry_class)
FAILURE_CODES = [
    ("BNK_01", "Bank-side", "Issuer bank unavailable", "Safe retry"),
    ("BNK_02", "Bank-side", "Issuer technical decline", "Verify status first"),
    ("BNK_03", "Bank-side", "Insufficient funds", "Customer action"),
    ("BNK_04", "Bank-side", "Issuer response delayed", "Verify status first"),
    ("BNK_05", "Bank-side", "Account inactive or frozen", "Customer action"),
    ("BNK_06", "Bank-side", "Issuer under maintenance", "Safe retry"),
    ("PSP_01", "PSP-side", "PSP processing error", "Safe retry"),
    ("PSP_02", "PSP-side", "PSP service unavailable", "Safe retry"),
    ("PSP_03", "PSP-side", "PSP rate limit hit", "Safe retry"),
    ("PSP_04", "PSP-side", "PSP routing error", "Safe retry"),
    ("NET_01", "Network", "Request timeout", "Verify status first"),
    ("NET_02", "Network", "Connectivity lost mid-request", "Verify status first"),
    ("NET_03", "Network", "Gateway timeout", "Verify status first"),
    ("CUS_01", "Customer", "Incorrect UPI PIN", "Customer action"),
    ("CUS_02", "Customer", "PIN attempts exceeded", "Customer action"),
    ("CUS_03", "Customer", "Customer cancelled", "Do not retry"),
    ("CUS_04", "Customer", "Invalid UPI ID or payee", "Customer action"),
    ("CUS_05", "Customer", "Collect request expired", "Customer action"),
    ("LIM_01", "Limit", "Daily transaction limit exceeded", "Customer action"),
    ("LIM_02", "Limit", "Per-transaction limit exceeded", "Customer action"),
    ("LIM_03", "Limit", "Merchant limit exceeded", "Customer action"),
    ("TEC_01", "Technical", "Invalid request format", "Do not retry"),
    ("TEC_02", "Technical", "Duplicate request id", "Verify status first"),
    ("TEC_03", "Technical", "Auth token expired", "Safe retry"),
    ("RSK_01", "Risk", "Blocked by security controls", "Do not retry"),
    ("RSK_02", "Risk", "Velocity check triggered", "Escalate"),
    ("UNK_01", "Unknown", "Unclassified error", "Escalate"),
    ("UNK_02", "Unknown", "Status unknown after response", "Escalate"),
]

# Customer attributes
SIGNUP_SHARE_OLD = 0.60
SIGNUP_OLD_START = "2025-01-01"
SIGNUP_OLD_END = "2026-03-31"
SIGNUP_NEW_START = "2026-04-01"
SIGNUP_NEW_END = "2026-09-30"
CITY_TIER_SHARE = {"Tier1": 0.35, "Tier2": 0.40, "Tier3": 0.25}
DEVICE_SHARE = {"Android": 0.70, "iOS": 0.22, "Web": 0.08}
CHANNEL_SHARE = {"Organic": 0.40, "Referral": 0.25, "Paid ads": 0.20, "Partner merchant": 0.15}
SEGMENT_SHARE = {
    "Reliable": 0.45,
    "Retry-dependent": 0.20,
    "Failure-prone": 0.12,
    "Abandoning": 0.13,
    "High-value": 0.10,
}

# Planted roles (used in step 2C onwards)
TRAP_BANK = "Tarang National"          # looks bad raw, fine after controls (P4)
HIDDEN_BAD_BANK = "Zenora"             # looks average raw, truly bad (P4)
HIDDEN_BAD_BANK_LOGODDS_PENALTY = 0.35
OUTAGE_BANK = "Kestrel Commercial"     # P1
OUTAGE_WINDOWS = [
    ("2026-05-14 11:00", "2026-05-14 15:00"),
    ("2026-07-22 18:00", "2026-07-22 23:00"),
    ("2026-09-09 08:00", "2026-09-09 12:00"),
]
BAD_DEPLOY_PSP = "Clearwave"           # P7
BAD_DEPLOY_START = "2026-08-03"
BAD_DEPLOY_END = "2026-08-16"
UTC_TIMESTAMP_PSP = "QuickRail"        # data-quality issue
DEVICE_TRUE_EFFECT = 0.0               # P9: device has no effect on failure


# ---- 2C-1: intent generation ----
N_INTENTS = 280000
N_REPEAT_INTENTS = 8400
N_BASE_INTENTS = N_INTENTS - N_REPEAT_INTENTS
GROWTH_TOTAL = 0.35
WEEKDAY_WEIGHT = [1.00, 0.98, 0.98, 1.00, 1.08, 1.12, 0.95]   # Monday=0
MONTH_END_BUMP = 1.15
HOUR_WEIGHT = [0.4, 0.25, 0.2, 0.15, 0.15, 0.25, 0.5, 1.0, 2.0, 2.8, 3.0, 3.2,
               3.8, 3.6, 3.0, 2.8, 3.0, 3.4, 3.8, 4.4, 5.6, 5.4, 4.0, 1.8]
ACTIVITY_SIGMA = 0.6
SEGMENT_ACTIVITY = {"Reliable": 1.0, "Retry-dependent": 1.0, "Failure-prone": 1.0,
                    "Abandoning": 0.8, "High-value": 1.3}
PRIMARY_BANK_SHARE = 0.85
CITY_TILT = {
    "Tarang National": {"Tier1": 0.3, "Tier2": 1.0, "Tier3": 4.0},
    "Zenora": {"Tier1": 3.0, "Tier2": 1.0, "Tier3": 0.3},
    "_small_default": {"Tier1": 0.6, "Tier2": 1.0, "Tier3": 1.5},
}
NETWORK_PROBS = {
    "Tier1": {"WiFi": 0.35, "5G": 0.30, "4G": 0.32, "3G": 0.025, "2G": 0.005},
    "Tier2": {"WiFi": 0.25, "5G": 0.12, "4G": 0.50, "3G": 0.10, "2G": 0.03},
    "Tier3": {"WiFi": 0.12, "5G": 0.03, "4G": 0.50, "3G": 0.25, "2G": 0.10},
}
# category: (weight, median amount in rupees, lognormal sigma)
PAYEE_CATEGORIES = {
    "Food & Beverage": (0.22, 180, 0.7),
    "Grocery": (0.18, 450, 0.8),
    "Transport": (0.15, 120, 0.6),
    "Utilities & Bills": (0.12, 1200, 0.9),
    "Shopping": (0.12, 900, 1.0),
    "Peer transfer": (0.12, 800, 1.1),
    "Education": (0.04, 3000, 0.9),
    "Travel": (0.05, 2500, 1.0),
}
PAYEES_PER_CATEGORY = 250
AMOUNT_SEGMENT_MULT = {"Reliable": 1.0, "Retry-dependent": 1.0, "Failure-prone": 1.0,
                       "Abandoning": 1.0, "High-value": 2.5}
ZENORA_AMOUNT_FACTOR = 0.6
CHANNEL_MIX = {"In-app": 0.45, "QR scan": 0.35, "Collect request": 0.10, "Intent link": 0.10}

# ---- 2C-2: failure model ----
# Mean failure probability per family, solved by calibration (non-incident, non-fixed families)
FAMILY_TARGET = {"bank": 0.020, "network": 0.040, "customer": 0.018, "psp": 0.010}
NET_LOGODDS = {"WiFi": 0.0, "5G": 0.0, "4G": 0.15, "3G": 1.2, "2G": 1.5}
SEGMENT_CUSTOMER_LOGODDS = {"Reliable": 0.0, "Retry-dependent": 0.2, "Failure-prone": 0.5,
                            "Abandoning": 0.0, "High-value": 0.0}
PEAK_HOURS = [20, 21]
PEAK_LOGODDS = {"Large": 0.0, "Medium": 0.25, "Small": 0.8}   # P2: peak hurts Small banks most
TREND_LOGODDS = -0.15          # P13: failures fall over the period (bank, network, psp)
MONTH_END_LOGODDS = 0.12       # month-end seasonality (bank, psp)
FAMILY_CODES = {
    "bank": {"BNK_01": 0.25, "BNK_02": 0.30, "BNK_04": 0.20, "BNK_05": 0.05, "BNK_06": 0.20},
    "network": {"NET_01": 0.55, "NET_02": 0.25, "NET_03": 0.20},
    "customer": {"CUS_01": 0.40, "BNK_03": 0.27, "CUS_02": 0.04, "CUS_03": 0.12,
                 "CUS_04": 0.10, "CUS_05": 0.07},
    "psp": {"PSP_01": 0.35, "PSP_02": 0.25, "PSP_03": 0.15, "PSP_04": 0.25},
    "risk": {"RSK_01": 0.6, "RSK_02": 0.4},
    "technical": {"TEC_01": 0.33, "TEC_02": 0.17, "TEC_03": 0.50},
    "unknown": {"UNK_01": 0.6, "UNK_02": 0.4},
    "limit_02": {"LIM_02": 1.0},
    "limit_01": {"LIM_01": 1.0},
    "limit_03": {"LIM_03": 1.0},
    "outage": {"BNK_01": 0.9, "BNK_04": 0.1},
    "deploy": {"PSP_01": 1.0},
}
FIXED_FAMILY_P = {"risk": 0.002, "technical": 0.003, "unknown": 0.001}
RISK_AMOUNT_THRESHOLD = 10000   # P6: risk blocks rise mildly above this
RISK_AMOUNT_ODDS_MULT = 2.0
PER_TXN_LIMIT = {"Large": 100000, "Medium": 50000, "Small": 10000}
DAILY_LIMIT = 100000
P_LIM02 = 0.92
P_LIM01 = 0.90
P_LIM03 = 0.03
LIM03_CATEGORIES = ["Shopping", "Education", "Travel"]
LIM03_AMOUNT = 20000
OUTAGE_P = 0.85
DEPLOY_P = 0.12
