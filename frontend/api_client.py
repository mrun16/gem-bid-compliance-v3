import requests

class APIError(RuntimeError):
    pass

class SendaAPI:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

    def headers(self):
        return {"x-officer-token": self.token} if self.token else {}

    def get(self, path, **kwargs):
        r = self.session.get(self.base_url + path, headers=self.headers(), timeout=60, **kwargs)
        if r.status_code >= 400:
            raise APIError(f"{r.status_code}: {r.text}")
        return r

    def post(self, path, **kwargs):
        r = self.session.post(self.base_url + path, headers=self.headers(), timeout=900, **kwargs)
        if r.status_code >= 400:
            raise APIError(f"{r.status_code}: {r.text}")
        return r

    def login(self, officer_id, password):
        r = requests.post(
            self.base_url + "/auth/login",
            json={"officer_id": officer_id, "password": password},
            timeout=30,
        )
        if r.status_code >= 400:
            raise APIError("Invalid officer credentials.")
        return r.json()

    def dashboard(self):
        return self.get("/dashboard").json()

    def batch_verify(self, tender_file, vendor_files, pans, names):
        files = [
            ("tender_file", (tender_file.name, tender_file.getvalue(), "application/pdf"))
        ]
        for f in vendor_files:
            files.append(("vendor_files", (f.name, f.getvalue(), "application/pdf")))
        data = {
            "vendor_pans": __import__("json").dumps(pans),
            "vendor_names": __import__("json").dumps(names),
        }
        return self.post("/verify/batch", files=files, data=data).json()

    def verification(self, verification_id):
        return self.get(f"/verification/{verification_id}").json()

    def document(self, verification_id, kind):
        return self.get(f"/verification/{verification_id}/document/{kind}").content

    def decision(self, verification_id, decision, notes):
        return self.post(
            f"/verification/{verification_id}/decision",
            json={"decision": decision, "notes": notes, "officer_id": ""},
        ).json()

    def report(self, verification_id):
        return self.get(f"/verification/{verification_id}/report").content

    def history(self):
        return self.get("/history").json()

    def bidders(self):
        return self.get("/bidder-directory").json()

    def bidder(self, pan):
        return self.get(f"/bidder/{pan}").json()

    def audit(self):
        return self.get("/audit").json()
