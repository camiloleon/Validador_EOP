from __future__ import annotations

import csv
import hashlib
import io
from difflib import get_close_matches

from .catalog_loader import Catalogs
from .models import CorrectionLog, ValidationIssue, ValidationResult, ValidationSummary
from .normalization import is_valid_email, normalize_key, normalize_state

TEMPLATE_COLUMNS: dict[str, list[str]] = {
    "tecnicos": [
        "identificacion",
        "nombre_completo",
        "correo",
        "telefono",
        "area",
        "trabajo",
        "ciudad",
        "base_operativa",
        "estado_operativo",
    ],
    "usuarios": [
        "nombre completo",
        "email",
        "identificacion",
        "celular",
        "contrasena",
        "rol de usuario",
        "regional",
        "compania (nit)",
    ],
    "plan_padrino": [
        "padrino identificacion",
        "tecnico identificacion",
        "activo",
    ],
}


def _detect_delimiter(text: str) -> str:
    first = text.splitlines()[0] if text.splitlines() else ""
    if first.count(";") > first.count(","):
        return ";"
    return ","


def _normalize_headers(headers: list[str]) -> list[str]:
    return [normalize_key(h).lower() for h in headers]


def _best_match(value: str, candidates: set[str]) -> str | None:
    normalized_candidates = {candidate: candidate for candidate in candidates}
    options = list(normalized_candidates.keys())
    match = get_close_matches(value, options, n=1, cutoff=0.88)
    if not match:
        return None
    return normalized_candidates[match[0]]


def _add_issue(
    issues: list[ValidationIssue],
    row: int,
    field: str,
    severity: str,
    code: str,
    message: str,
    current_value: str | None = None,
    suggested_value: str | None = None,
) -> None:
    issues.append(
        ValidationIssue(
            row=row,
            field=field,
            severity=severity,
            code=code,
            message=message,
            current_value=current_value,
            suggested_value=suggested_value,
        )
    )


def _set_value(
    row_data: dict[str, str],
    field: str,
    new_value: str,
    row_number: int,
    rule: str,
    corrections: list[CorrectionLog],
) -> None:
    old = row_data.get(field)
    if old == new_value:
        return
    row_data[field] = new_value
    corrections.append(
        CorrectionLog(
            row=row_number,
            field=field,
            old_value=old,
            new_value=new_value,
            rule=rule,
        )
    )


def validate_csv(
    template: str,
    content: bytes,
    catalogs: Catalogs,
) -> ValidationResult:
    template_key = normalize_key(template).lower().replace(" ", "_")
    if template_key not in TEMPLATE_COLUMNS:
        raise ValueError(f"Plantilla no soportada: {template}")

    text = content.decode("utf-8-sig", errors="replace")
    delimiter = _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    expected_cols = TEMPLATE_COLUMNS[template_key]
    headers = reader.fieldnames or []
    normalized_headers = _normalize_headers(headers)

    missing = [col for col in expected_cols if col not in normalized_headers]
    if missing:
        issues = [
            ValidationIssue(
                row=1,
                field="headers",
                severity="error",
                code="MISSING_COLUMNS",
                message=f"Faltan columnas requeridas: {', '.join(missing)}",
            )
        ]
        summary = ValidationSummary(
            template=template_key,
            total_rows=0,
            error_count=1,
            warning_count=0,
            suspicious_count=0,
            correction_count=0,
            can_continue=False,
            delimiter=delimiter,
            file_hash=hashlib.sha256(content).hexdigest(),
        )
        return ValidationResult(summary=summary, issues=issues, corrections=[], corrected_csv="")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        mapped: dict[str, str] = {}
        for original, normalized in zip(headers, normalized_headers):
            mapped[normalized] = "" if raw_row.get(original) is None else str(raw_row.get(original)).strip()
        rows.append(mapped)

    issues: list[ValidationIssue] = []
    corrections: list[CorrectionLog] = []

    if template_key == "tecnicos":
        _validate_tecnicos(rows, catalogs, issues, corrections)
    elif template_key == "usuarios":
        _validate_usuarios(rows, catalogs, issues, corrections)
    elif template_key == "plan_padrino":
        _validate_plan_padrino(rows, issues)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=expected_cols, delimiter=delimiter)
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in expected_cols})

    error_count = sum(1 for item in issues if item.severity == "error")
    warning_count = sum(1 for item in issues if item.severity == "warning")
    suspicious_count = sum(1 for item in issues if item.severity == "suspicious")

    summary = ValidationSummary(
        template=template_key,
        total_rows=len(rows),
        error_count=error_count,
        warning_count=warning_count,
        suspicious_count=suspicious_count,
        correction_count=len(corrections),
        can_continue=error_count == 0,
        delimiter=delimiter,
        file_hash=hashlib.sha256(content).hexdigest(),
    )
    return ValidationResult(
        summary=summary,
        issues=issues,
        corrections=corrections,
        corrected_csv=output.getvalue(),
        correction_options=_build_correction_options(template_key, catalogs),
        correlation_maps=_build_correlation_maps(template_key, catalogs),
    )


def _build_correction_options(template_key: str, catalogs: Catalogs) -> dict[str, list[str]]:
    if template_key == "tecnicos":
        return {
            "area": sorted(catalogs.areas),
            "trabajo": sorted(catalogs.trabajos),
            "ciudad": sorted(catalogs.ciudades),
            "base_operativa": sorted(catalogs.bases),
            "estado_operativo": ["ACTIVO", "INACTIVO"],
        }

    if template_key == "usuarios":
        return {
            "rol de usuario": sorted(catalogs.roles),
            "regional": sorted(catalogs.regionales),
            "compania (nit)": sorted(catalogs.companias_nit),
        }

    if template_key == "plan_padrino":
        return {
            "activo": ["1", "0"],
        }

    return {}


def _build_correlation_maps(template_key: str, catalogs: Catalogs) -> dict[str, object]:
    if template_key != "tecnicos":
        return {}

    base_to_cities: dict[str, list[str]] = {}
    for city, base in catalogs.ciudad_to_base.items():
        if not base:
            continue
        base_to_cities.setdefault(base, []).append(city)

    for base in list(base_to_cities.keys()):
        base_to_cities[base] = sorted(set(base_to_cities[base]))

    return {
        "city_to_base": dict(sorted(catalogs.ciudad_to_base.items())),
        "base_to_cities": dict(sorted(base_to_cities.items())),
    }


def _validate_tecnicos(
    rows: list[dict[str, str]],
    catalogs: Catalogs,
    issues: list[ValidationIssue],
    corrections: list[CorrectionLog],
) -> None:
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()

    for index, row in enumerate(rows, start=2):
        required = ["identificacion", "nombre_completo", "correo", "trabajo", "ciudad"]
        for field in required:
            if not row.get(field, "").strip():
                _add_issue(issues, index, field, "error", "REQUIRED", f"El campo {field} es obligatorio")

        if row.get("identificacion"):
            key = normalize_key(row["identificacion"])
            if key in seen_ids:
                _add_issue(issues, index, "identificacion", "error", "DUPLICATE_ID", "Identificación duplicada")
            seen_ids.add(key)

        if row.get("correo"):
            mail_raw = row["correo"].strip()
            if not is_valid_email(mail_raw):
                _add_issue(issues, index, "correo", "error", "INVALID_EMAIL", "Correo con formato inválido", mail_raw)
            mail = mail_raw.lower()
            if mail in seen_emails:
                _add_issue(issues, index, "correo", "error", "DUPLICATE_EMAIL", "Correo duplicado", mail_raw)
            seen_emails.add(mail)

        area = normalize_key(row.get("area"))
        if area and area not in catalogs.areas:
            _add_issue(issues, index, "area", "error", "INVALID_AREA", "Área no parametrizada", row.get("area"))

        trabajo = normalize_key(row.get("trabajo"))
        if trabajo and trabajo not in catalogs.trabajos:
            _add_issue(issues, index, "trabajo", "error", "INVALID_WORK", "Trabajo no parametrizado", row.get("trabajo"))
        elif trabajo and area and area in catalogs.trabajos_por_area and trabajo not in catalogs.trabajos_por_area[area]:
            _add_issue(
                issues,
                index,
                "trabajo",
                "warning",
                "WORK_AREA_MISMATCH",
                "Trabajo válido pero no corresponde al área",
                row.get("trabajo"),
            )

        city_raw = row.get("ciudad", "")
        city = normalize_key(city_raw)
        if city and city not in catalogs.ciudades:
            candidate = _best_match(city, catalogs.ciudades)
            if candidate:
                _set_value(row, "ciudad", candidate.title(), index, "city_typo_autofix", corrections)
                _add_issue(
                    issues,
                    index,
                    "ciudad",
                    "warning",
                    "CITY_AUTOCORRECTED",
                    "Ciudad autocorregida por similitud",
                    city_raw,
                    candidate,
                )
                city = candidate
            else:
                _add_issue(issues, index, "ciudad", "error", "INVALID_CITY", "Ciudad no parametrizada", city_raw)

        base_raw = row.get("base_operativa", "")
        base = normalize_key(base_raw)
        expected_base = catalogs.ciudad_to_base.get(city)
        if not base and expected_base:
            _set_value(row, "base_operativa", expected_base, index, "infer_base_from_city", corrections)
        elif not city and base:
            suggested_city = next((city_name for city_name, mapped_base in catalogs.ciudad_to_base.items() if mapped_base == base), None)
            _add_issue(
                issues,
                index,
                "ciudad",
                "error",
                "MISSING_CITY_FOR_BASE",
                "Debe informar ciudad para validar correlación con base operativa",
                row.get("ciudad"),
                suggested_city,
            )
        elif base and base not in catalogs.bases:
            _add_issue(
                issues,
                index,
                "base_operativa",
                "error",
                "INVALID_BASE",
                "Base operativa no parametrizada",
                base_raw,
            )
        elif base and expected_base and base != expected_base:
            _add_issue(
                issues,
                index,
                "base_operativa",
                "error",
                "CITY_BASE_INCONSISTENT",
                "Base operativa no coincide con la ciudad",
                base_raw,
                expected_base,
            )

        state = normalize_state(row.get("estado_operativo"))
        if not row.get("estado_operativo"):
            _set_value(row, "estado_operativo", "ACTIVO", index, "default_estado_operativo", corrections)
        elif state not in {"ACTIVO", "INACTIVO"}:
            _add_issue(
                issues,
                index,
                "estado_operativo",
                "error",
                "INVALID_STATE",
                "Estado operativo inválido",
                row.get("estado_operativo"),
            )


def _validate_usuarios(
    rows: list[dict[str, str]],
    catalogs: Catalogs,
    issues: list[ValidationIssue],
    corrections: list[CorrectionLog],
) -> None:
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()

    required = [
        "nombre completo",
        "email",
        "rol de usuario",
        "regional",
        "compania (nit)",
    ]

    for index, row in enumerate(rows, start=2):
        for field in required:
            if not row.get(field, "").strip():
                _add_issue(issues, index, field, "error", "REQUIRED", f"El campo {field} es obligatorio")

        email = row.get("email", "").strip()
        if email and not is_valid_email(email):
            _add_issue(issues, index, "email", "error", "INVALID_EMAIL", "Email con formato inválido", email)
        if email:
            lower = email.lower()
            if lower in seen_emails:
                _add_issue(issues, index, "email", "error", "DUPLICATE_EMAIL", "Email duplicado", email)
            seen_emails.add(lower)

        identifier = row.get("identificacion", "").strip()
        if identifier:
            norm = normalize_key(identifier)
            if norm in seen_ids:
                _add_issue(
                    issues,
                    index,
                    "identificacion",
                    "error",
                    "DUPLICATE_IDENTIFIER",
                    "Identificación duplicada",
                    identifier,
                )
            seen_ids.add(norm)

        if not row.get("contrasena", "").strip() and identifier:
            _set_value(row, "contrasena", identifier, index, "default_password_from_identifier", corrections)
            _add_issue(
                issues,
                index,
                "contrasena",
                "warning",
                "PASSWORD_DEFAULTED",
                "Contraseña vacía, se asigna identificación por defecto",
                "",
                identifier,
            )

        role = normalize_key(row.get("rol de usuario"))
        if role and role not in catalogs.roles:
            _add_issue(issues, index, "rol de usuario", "error", "INVALID_ROLE", "Rol no parametrizado", row.get("rol de usuario"))

        regional = normalize_key(row.get("regional"))
        if regional and regional not in catalogs.regionales:
            _add_issue(issues, index, "regional", "error", "INVALID_REGIONAL", "Regional no parametrizada", row.get("regional"))

        nit = normalize_key(row.get("compania (nit)"))
        if nit and nit not in catalogs.companias_nit:
            _add_issue(issues, index, "compania (nit)", "error", "INVALID_NIT", "NIT no parametrizado", row.get("compania (nit)"))


def _validate_plan_padrino(rows: list[dict[str, str]], issues: list[ValidationIssue]) -> None:
    for index, row in enumerate(rows, start=2):
        padrino = row.get("padrino identificacion", "").strip()
        tecnico = row.get("tecnico identificacion", "").strip()
        activo = row.get("activo", "").strip()

        if not padrino:
            _add_issue(issues, index, "padrino identificacion", "error", "REQUIRED", "Padrino identificación es obligatorio")
        if not tecnico:
            _add_issue(issues, index, "tecnico identificacion", "error", "REQUIRED", "Técnico identificación es obligatorio")
        if activo not in {"0", "1"}:
            _add_issue(issues, index, "activo", "error", "INVALID_ACTIVE", "Activo debe ser 1 o 0", activo)
