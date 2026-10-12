# =============================================================================
# PSE-KALI — SHARED ENGAGEMENT CONTEXT (the minimal SHARED_LIB)
# One shared object the three concurrent units read and write. Holds the rules
# of engagement (authorized scope + tokens) and a findings store through which
# units feed each other in tandem. Read-safe and write-safe under threads.
# =============================================================================
import ipaddress
import threading


class EngagementContext:
    def __init__(self, engagement_id, scope, authorizations):
        """
        scope           : list of CIDR strings / hostnames authorized for testing
        authorizations  : list of dicts, each granting a (target, tool) pair.
                          A grant matches if the action's target falls in
                          `target_scope` and the tool is in `tools` (or "*").
        """
        self.engagement_id = engagement_id
        self._scope = list(scope)
        self._auth = list(authorizations)
        self._findings = []            # shared intel: hosts, hashes, services...
        self._lock = threading.Lock()

    @property
    def scope(self):
        return list(self._scope)

    def add_scope(self, cidr, tools):
        """Widen the authorized scope live. Reassigns (never mutates in place) so
        concurrent readers never see a half-changed list. This is the ONLY way
        the floor lifts for a new target — a deliberate, human, logged act."""
        self._scope = self._scope + [cidr]
        self._auth = self._auth + [{"target_scope": [cidr], "tools": list(tools)}]

    # ---- scope / authorization checks (read-only, no lock needed) ----------
    def _match(self, target, entry):
        if target is None:
            return False
        try:
            net = ipaddress.ip_network(entry, strict=False)
            return ipaddress.ip_address(target) in net
        except ValueError:
            return str(target) == str(entry)   # hostname exact match

    def in_scope(self, target):
        return any(self._match(target, e) for e in self._scope)

    def authorized(self, target, tool):
        for grant in self._auth:
            tgt_ok = any(self._match(target, s) for s in grant.get("target_scope", []))
            tool_ok = ("*" in grant.get("tools", [])) or (tool in grant.get("tools", []))
            if tgt_ok and tool_ok:
                return True
        return False

    def has_provenance(self, artifact):
        """An artifact (e.g. a hash) is usable only if a prior in-scope finding
        introduced it. This is what stops the cracker from cracking a hash the
        user just pasted from nowhere."""
        with self._lock:
            return any(f.get("artifact") == artifact and f.get("in_scope")
                       for f in self._findings)

    # ---- findings store (units feed each other through here) ---------------
    def add_finding(self, finding):
        """A unit publishes intel. Stamped with whether it is in scope so
        downstream consumers inherit the scope decision."""
        finding = dict(finding)
        finding["in_scope"] = self.in_scope(finding.get("target"))
        with self._lock:
            self._findings.append(finding)
        return finding

    def findings(self, kind=None):
        with self._lock:
            return [dict(f) for f in self._findings
                    if kind is None or f.get("kind") == kind]
