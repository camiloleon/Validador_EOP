from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import httpx


@dataclass
class SubmissionResult:
    mode: str
    accepted: bool
    message: str
    external_id: str


def submit_to_eop(template: str, corrected_csv: str) -> SubmissionResult:
    api_url = os.getenv("EOP_API_URL", "").strip()
    api_key = os.getenv("EOP_API_KEY", "").strip()

    payload_hash = hashlib.sha256(corrected_csv.encode("utf-8")).hexdigest()

    if not api_url:
        return SubmissionResult(
            mode="simulated",
            accepted=True,
            message="Envío simulado: configure EOP_API_URL para activar integración real.",
            external_id=f"SIM-{payload_hash[:12]}",
        )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "template": template,
        "file_hash": payload_hash,
        "csv_content": corrected_csv,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json() if response.content else {}

    return SubmissionResult(
        mode="real",
        accepted=bool(body.get("accepted", True)),
        message=str(body.get("message", "Archivo enviado correctamente a EOP")),
        external_id=str(body.get("external_id", f"EOP-{payload_hash[:12]}")),
    )
