# =============================================================================
# PSE-KALI — audit JSONL -> monitor timeline
# The live monitor reads the real audit log the engagement writes. This maps an
# audit record to the shape the simplex/table expect. (Produced findings aren't
# in the audit, so the live findings panel is a per-unit action tally instead.)
# =============================================================================
import json


def record_from_audit(rec):
    st = rec.get("state", {})
    iv = rec.get("intervention") or {}
    kind = iv.get("kind")
    reason = (iv.get("reason") or "")
    return {
        "engagement": rec.get("engagement", "—"),
        "unit": rec.get("unit", "?"),
        "tool": rec.get("tool", ""),
        "target": rec.get("target", ""),
        "w": [st.get("w_s", 0.0), st.get("w_o", 0.0), st.get("w_f", 0.0)],
        "auth": rec.get("auth_level", 0.0),
        "allowed": bool(rec.get("allowed")),
        "kind": kind,
        "floor": kind == "unauthorized",
        "why": (reason[:70] + "…") if len(reason) > 71 else reason,
        "produces": [],
    }


def records_from_audit(lines):
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(record_from_audit(json.loads(line)))
        except (ValueError, KeyError):
            continue
    return out
