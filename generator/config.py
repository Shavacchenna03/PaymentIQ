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
OUTAGE_BANK = "Ridgeway"               # P1
OUTAGE_WINDOWS = [
    ("2026-05-14 11:00", "2026-05-14 13:30"),
    ("2026-07-22 19:00", "2026-07-22 22:00"),
    ("2026-09-09 08:00", "2026-09-09 10:00"),
]
BAD_DEPLOY_PSP = "Clearwave"           # P7
BAD_DEPLOY_START = "2026-08-03"
BAD_DEPLOY_END = "2026-08-16"
UTC_TIMESTAMP_PSP = "QuickRail"        # data-quality issue
DEVICE_TRUE_EFFECT = 0.0               # P9: device has no effect on failure
