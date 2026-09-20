"""
Plain-English "why does this matter" explanations, keyed by the same category
labels the tender-checklist extraction prompt already produces (see
verification_service.extract_tender_checklist). Shown as a hover tooltip next
to each requirement card in the frontend, so a judge who doesn't know GeM
jargon can follow the demo without a side explanation.
"""

CATEGORY_HELP = {
    "Udyam": (
        "Udyam registration is the government's official record that a business "
        "qualifies as a Micro, Small or Medium Enterprise (MSME). Many GeM tenders "
        "reserve a share of purchases for MSMEs, so this status can affect eligibility "
        "and pricing preference."
    ),
    "GST": (
        "GST (Goods and Services Tax) registration and up-to-date return filing show "
        "the bidder is a tax-compliant, currently operating business. Lapsed filings "
        "are a common red flag in procurement fraud."
    ),
    "PAN": (
        "PAN (Permanent Account Number) is the bidder's tax identity with the Income "
        "Tax Department. It's the key used to cross-check the bidder against every "
        "other government database in this pipeline."
    ),
    "MakeInIndia": (
        "Make in India / local content rules set a minimum percentage of a product "
        "that must be manufactured domestically. Many tenders make this mandatory to "
        "qualify, not just a scoring bonus."
    ),
    "EPFO_ESIC": (
        "EPFO (retirement fund) and ESIC (health insurance) compliance show the bidder "
        "is correctly registering and paying into its employees' statutory benefits — "
        "a labour-law compliance signal, not just a financial one."
    ),
    "StartupIndia": (
        "Startup India recognition can unlock relaxed eligibility criteria (e.g. "
        "waived turnover or prior-experience requirements) for young, recognized "
        "startups bidding on government tenders."
    ),
    "NSIC": (
        "NSIC (National Small Industries Corporation) registration is a separate "
        "small-industry certification that can qualify a bidder for tender fee "
        "waivers or reserved categories, similar in spirit to Udyam."
    ),
    "OEM": (
        "An OEM (Original Equipment Manufacturer) authorization letter proves the "
        "bidder is actually allowed to sell/service that manufacturer's product — "
        "without it, a reseller could bid on hardware they have no right to supply."
    ),
    "Other": (
        "A requirement stated explicitly in the tender text that doesn't fall into one "
        "of the standard GeM compliance categories above — read the evidence field for "
        "specifics."
    ),
}

DEFAULT_HELP = (
    "No category-specific guidance available for this requirement — read the "
    "evidence field for the specific condition being checked."
)


def get_category_help(category: str) -> str:
    return CATEGORY_HELP.get(category, DEFAULT_HELP)
