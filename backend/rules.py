"""
Deterministic rule engine for GeM bid compliance.

Evaluates authoritative, deterministic requirements against verified government portal records
(e.g., Udyam, GSTN, PAN, EPFO/ESIC, Startup India, NSIC, Blacklist).
Resolves straightforward lookups deterministically so that the AI / reviewer cannot contradict them,
and returns the remaining unresolved requirements for document and contextual analysis.
"""
import re
from typing import Optional


def evaluate_deterministic_rules(checklist: list, portal_record: Optional[dict]):
    """
    Evaluates checklist items deterministically against the bidder's portal record.

    Args:
        checklist: List of dicts with keys 'requirement', 'category', 'detail'
        portal_record: Dict of verified portal data from mock_portal_data.json or None

    Returns:
        tuple (rule_results, unresolved_items)
            - rule_results: List of dicts with 'requirement', 'status', 'evidence', 'category'
            - unresolved_items: Items left for document inspection / LLM judgment
    """
    rule_results = []
    unresolved_items = []

    # If no portal record is found, all items must be evaluated via documents / AI
    if not portal_record:
        return rule_results, list(checklist)

    # Check for debarment / blacklist first
    if portal_record.get("blacklisted", False):
        rule_results.append({
            "requirement": "Debarment & Blacklisting Status",
            "status": "FAIL",
            "evidence": "Central Procurement Database flag: Bidder is currently blacklisted/debarred from public procurement.",
            "category": "Other",
        })

    for item in checklist:
        req_text = item.get("requirement", "")
        category = (item.get("category") or "Other").strip()
        detail = (item.get("detail") or "").strip()
        req_lower = req_text.lower()
        detail_lower = detail.lower()

        resolved = False

        # 1. Udyam / MSME Registration
        if category == "Udyam" or "udyam" in req_lower or "msme" in req_lower:
            is_udyam = portal_record.get("udyam_registered", False)
            udyam_num = portal_record.get("udyam_number", "N/A")
            if is_udyam:
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": f"Portal verified: Active Udyam MSME registration ({udyam_num}).",
                    "category": "Udyam",
                })
            else:
                rule_results.append({
                    "requirement": req_text,
                    "status": "FAIL",
                    "evidence": "Portal verified: Entity is not registered under Udyam / MSME portal.",
                    "category": "Udyam",
                })
            resolved = True

        # 2. GST Registration & Return Filing
        elif category == "GST" or "gst" in req_lower or "goods and services" in req_lower:
            gst_reg = portal_record.get("gst_registered", False)
            gst_status = portal_record.get("gst_status", "Inactive")
            last_return = portal_record.get("gst_last_return_filed", "N/A")
            if gst_reg and gst_status == "Active":
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": f"Portal verified: GST status is Active. Last return filed on {last_return}.",
                    "category": "GST",
                })
            else:
                rule_results.append({
                    "requirement": req_text,
                    "status": "FAIL",
                    "evidence": f"Portal verified: GST status is {gst_status} (registered: {gst_reg}).",
                    "category": "GST",
                })
            resolved = True

        # 3. PAN / Tax Compliance
        elif category == "PAN" or "pan" in req_lower or "income tax" in req_lower:
            pan_status = portal_record.get("pan_status", "Invalid")
            if pan_status.lower() == "valid":
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": "Portal verified: PAN status is Valid with Income Tax Department records.",
                    "category": "PAN",
                })
            else:
                rule_results.append({
                    "requirement": req_text,
                    "status": "FAIL",
                    "evidence": f"Portal verified: PAN status is {pan_status}.",
                    "category": "PAN",
                })
            resolved = True

        # 4. Make in India / Local Content
        elif category == "MakeInIndia" or "make in india" in req_lower or "local content" in req_lower:
            pct = portal_record.get("make_in_india_local_content_pct")
            if pct is not None:
                # Check for explicit threshold in detail (e.g. 50%, 60%)
                threshold = 50
                m = re.search(r"(\d+)\s*%", detail)
                if m:
                    try:
                        threshold = int(m.group(1))
                    except ValueError:
                        threshold = 50

                if pct >= threshold:
                    supplier_class = "Class-I" if pct >= 50 else "Class-II"
                    rule_results.append({
                        "requirement": req_text,
                        "status": "PASS",
                        "evidence": f"Portal verified: Declared local content is {pct}% ({supplier_class} local supplier; threshold is {threshold}%).",
                        "category": "MakeInIndia",
                    })
                else:
                    rule_results.append({
                        "requirement": req_text,
                        "status": "FAIL",
                        "evidence": f"Portal verified: Local content is {pct}%, which is below the required {threshold}%.",
                        "category": "MakeInIndia",
                    })
                resolved = True

        # 5. EPFO / ESIC Statutory Welfare
        elif category == "EPFO_ESIC" or "epfo" in req_lower or "esic" in req_lower or "provident fund" in req_lower:
            epfo = portal_record.get("epfo_registered", False)
            esic = portal_record.get("esic_registered", False)
            if epfo and esic:
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": "Portal verified: Both EPFO and ESIC employee welfare registrations are active.",
                    "category": "EPFO_ESIC",
                })
            elif epfo or esic:
                rule_results.append({
                    "requirement": req_text,
                    "status": "INCONSISTENT",
                    "evidence": f"Portal records show partial statutory compliance (EPFO: {epfo}, ESIC: {esic}).",
                    "category": "EPFO_ESIC",
                })
            else:
                rule_results.append({
                    "requirement": req_text,
                    "status": "FAIL",
                    "evidence": "Portal verified: Neither EPFO nor ESIC statutory registration was found.",
                    "category": "EPFO_ESIC",
                })
            resolved = True

        # 6. NSIC Registration
        elif category == "NSIC" or "nsic" in req_lower:
            nsic = portal_record.get("nsic_registered", False)
            if nsic:
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": "Portal verified: Active NSIC small industries certificate on file.",
                    "category": "NSIC",
                })
            else:
                rule_results.append({
                    "requirement": req_text,
                    "status": "FAIL",
                    "evidence": "Portal verified: No NSIC registration found on file.",
                    "category": "NSIC",
                })
            resolved = True

        # 7. Startup India
        elif category == "StartupIndia" or "startup" in req_lower:
            startup = portal_record.get("startup_india_recognized", False)
            if startup:
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": "Portal verified: Entity is recognized by DPIIT under Startup India.",
                    "category": "StartupIndia",
                })
            else:
                rule_results.append({
                    "requirement": req_text,
                    "status": "FAIL",
                    "evidence": "Portal verified: Entity is not recognized as a DPIIT Startup India entity.",
                    "category": "StartupIndia",
                })
            resolved = True

        # 8. OEM Authorization Letter
        elif category == "OEM" or "oem" in req_lower:
            if portal_record.get("oem_authorization_on_file"):
                rule_results.append({
                    "requirement": req_text,
                    "status": "PASS",
                    "evidence": "Portal verified: Direct OEM manufacturer authorization certificate is on file.",
                    "category": "OEM",
                })
                resolved = True

        if not resolved:
            unresolved_items.append(item)

    return rule_results, unresolved_items
