from __future__ import annotations

import csv
import hashlib
import io
from difflib import get_close_matches
import re

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
    counts = {
        ",": first.count(","),
        ";": first.count(";"),
        "\t": first.count("\t"),
        "|": first.count("|"),
    }
    best = max(counts, key=counts.get)  # type: ignore[arg-type]
    return best if counts[best] > 0 else ","


def _normalize_headers(headers: list[str]) -> list[str]:
    return [normalize_key(h).lower() for h in headers]


def _canonical_label(value: str | None) -> str:
    text = normalize_key(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _header_aliases(template_key: str) -> dict[str, str]:
    if template_key == "usuarios":
        return {
            "nombre": "nombre completo",
            "nombres": "nombre completo",
            "correo": "email",
            "nit": "compania (nit)",
            "compania nit": "compania (nit)",
            "compania": "compania (nit)",
            "cargo": "rol de usuario",
            "contrasena": "contrasena",
            "contrase a": "contrasena",
        }
    if template_key == "plan_padrino":
        return {
            "identificacion": "padrino identificacion",
            "estado": "activo",
        }
    return {}


def _resolve_headers(headers: list[str], expected_cols: list[str], template_key: str) -> list[str]:
    expected_canonical: dict[str, str] = {_canonical_label(column): column for column in expected_cols}
    aliases = _header_aliases(template_key)
    resolved: list[str] = []
    expected_keys = list(expected_canonical.keys())

    for header in headers:
        if header in expected_cols:
            resolved.append(header)
            continue

        canonical = _canonical_label(header)
        alias_target = aliases.get(canonical)
        if alias_target:
            resolved.append(alias_target)
            continue

        direct = expected_canonical.get(canonical)
        if direct:
            resolved.append(direct)
            continue

        match = get_close_matches(canonical, expected_keys, n=1, cutoff=0.72)
        resolved.append(expected_canonical[match[0]] if match else header)

    return resolved


def _missing_columns_for_template(headers: list[str], template_key: str) -> list[str]:
    expected_cols = TEMPLATE_COLUMNS[template_key]
    resolved_headers = _resolve_headers(headers, expected_cols, template_key)
    missing = [column for column in expected_cols if column not in resolved_headers]
    if template_key == "plan_padrino" and missing == ["tecnico identificacion"]:
        return []
    return missing


def _suggest_template(headers: list[str], selected_template: str) -> str | None:
    suggestion: str | None = None
    best_score = -1
    for candidate in TEMPLATE_COLUMNS.keys():
        if candidate == selected_template:
            continue
        missing = _missing_columns_for_template(headers, candidate)
        if missing:
            continue
        score = len(TEMPLATE_COLUMNS[candidate])
        if score > best_score:
            best_score = score
            suggestion = candidate
    return suggestion


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


def _normalize_identifier(value: str | None) -> str:
    text = "" if value is None else str(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or normalize_key(text)


def _decode_content(content: bytes) -> str:
    """Decode raw bytes trying UTF-8 first, then common fallback encodings."""
    # UTF-16 with BOM
    if content[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return content.decode("utf-16")
    # UTF-16 LE without BOM heuristic (NUL bytes interleaved)
    if len(content) >= 4 and content[1:2] == b"\x00" and content[3:4] == b"\x00":
        return content.decode("utf-16-le")
    # UTF-8 BOM
    if content[:3] == b"\xef\xbb\xbf":
        return content[3:].decode("utf-8", errors="replace")
    # Try strict UTF-8 first
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # Fallback to latin-1 (covers windows-1252 superset)
    return content.decode("latin-1")


def validate_csv(
    template: str,
    content: bytes,
    catalogs: Catalogs,
) -> ValidationResult:
    template_key = normalize_key(template).lower().replace(" ", "_")
    if template_key not in TEMPLATE_COLUMNS:
        raise ValueError(f"Plantilla no soportada: {template}")

    text = _decode_content(content)
    delimiter = _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    expected_cols = TEMPLATE_COLUMNS[template_key]
    headers = reader.fieldnames or []
    normalized_headers = _normalize_headers(headers)
    resolved_headers = _resolve_headers(normalized_headers, expected_cols, template_key)

    missing = [col for col in expected_cols if col not in resolved_headers]
    infer_tecnico_from_padrino = False
    if template_key == "plan_padrino" and missing == ["tecnico identificacion"]:
        infer_tecnico_from_padrino = True
        missing = []

    if missing:
        issues: list[ValidationIssue] = [
            ValidationIssue(
                row=1,
                field="headers",
                severity="error",
                code="MISSING_COLUMNS",
                message=f"Faltan columnas requeridas: {', '.join(missing)}",
            )
        ]

        suggested_template = _suggest_template(normalized_headers, template_key)
        if suggested_template:
            issues.append(
                ValidationIssue(
                    row=1,
                    field="template",
                    severity="warning",
                    code="TEMPLATE_MISMATCH_SUGGESTION",
                    message=(
                        "La estructura del archivo parece corresponder a otra plantilla. "
                        f"Prueba con: {suggested_template}."
                    ),
                    current_value=template_key,
                    suggested_value=suggested_template,
                )
            )

        error_count = sum(1 for item in issues if item.severity == "error")
        warning_count = sum(1 for item in issues if item.severity == "warning")
        suspicious_count = sum(1 for item in issues if item.severity == "suspicious")
        summary = ValidationSummary(
            template=template_key,
            total_rows=0,
            error_count=error_count,
            warning_count=warning_count,
            suspicious_count=suspicious_count,
            correction_count=0,
            can_continue=False,
            delimiter=delimiter,
            file_hash=hashlib.sha256(content).hexdigest(),
        )
        return ValidationResult(summary=summary, issues=issues, corrections=[], corrected_csv="")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        mapped: dict[str, str] = {}
        for original, normalized in zip(headers, resolved_headers):
            mapped[normalized] = "" if raw_row.get(original) is None else str(raw_row.get(original)).strip()
        if infer_tecnico_from_padrino and not mapped.get("tecnico identificacion", "").strip():
            mapped["tecnico identificacion"] = mapped.get("padrino identificacion", "")
        if not any(value.strip() for value in mapped.values()):
            continue
        rows.append(mapped)

    issues: list[ValidationIssue] = []
    corrections: list[CorrectionLog] = []

    if template_key == "tecnicos":
        _validate_tecnicos(rows, catalogs, issues, corrections)
    elif template_key == "usuarios":
        _validate_usuarios(rows, catalogs, issues, corrections)
    elif template_key == "plan_padrino":
        _validate_plan_padrino(rows, catalogs, issues)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=expected_cols, delimiter=",")
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
    if template_key == "usuarios":
        company_nit_labels: dict[str, str] = {}
        for nit in sorted(catalogs.companias_nit):
            name = catalogs.compania_nit_to_name.get(nit)
            company_nit_labels[nit] = f"{name} - {nit}" if name else nit

        return {
            "company_nit_labels": company_nit_labels,
        }

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
    seen_phones: set[str] = set()

    if catalogs.existing_tecnicos_snapshot_date:
        _add_issue(
            issues,
            1,
            "tecnicos_exportados",
            "warning",
            "EXTERNAL_TECHNICIANS_SNAPSHOT",
            (
                "La validación de duplicidad contra técnicos cargados usa snapshot con fecha "
                f"{catalogs.existing_tecnicos_snapshot_date}. "
                "Registros actualizados posteriormente podrían no detectarse."
            ),
        )

    for index, row in enumerate(rows, start=2):
        required = ["identificacion", "nombre_completo", "correo", "trabajo", "ciudad"]
        for field in required:
            if not row.get(field, "").strip():
                _add_issue(issues, index, field, "error", "REQUIRED", f"El campo {field} es obligatorio")

        if row.get("identificacion"):
            key = _normalize_identifier(row["identificacion"])
            if key in seen_ids:
                _add_issue(issues, index, "identificacion", "error", "DUPLICATE_ID", "Identificación duplicada")
            seen_ids.add(key)

            if key in catalogs.existing_tecnicos_ids:
                _add_issue(
                    issues,
                    index,
                    "identificacion",
                    "warning",
                    "ALREADY_LOADED_DUPLICATE_ID",
                    "Posible duplicado: la identificación ya existe en técnicos cargados al sistema",
                    row.get("identificacion"),
                    "ELIMINAR_FILA",
                )

        if row.get("correo"):
            mail_raw = row["correo"].strip()
            if not is_valid_email(mail_raw):
                _add_issue(issues, index, "correo", "error", "INVALID_EMAIL", "Correo con formato inválido", mail_raw)
            mail = mail_raw.lower()
            if mail in seen_emails:
                _add_issue(issues, index, "correo", "error", "DUPLICATE_EMAIL", "Correo duplicado", mail_raw)
            seen_emails.add(mail)

        full_name = normalize_key(row.get("nombre_completo"))
        email = row.get("correo", "").strip().lower()
        phone = "".join(ch for ch in row.get("telefono", "") if ch.isdigit())

        # Duplicate phone within the file
        if phone:
            if phone in seen_phones:
                _add_issue(issues, index, "telefono", "error", "DUPLICATE_PHONE", "Teléfono duplicado en el archivo", row.get("telefono"))
            seen_phones.add(phone)

            if phone in catalogs.existing_tecnicos_phones:
                _add_issue(
                    issues,
                    index,
                    "telefono",
                    "warning",
                    "ALREADY_LOADED_DUPLICATE_PHONE",
                    "El número de celular ya está registrado para otro usuario en técnicos cargados",
                    row.get("telefono"),
                    "ELIMINAR_FILA",
                )

        if full_name and email and (full_name, email) in catalogs.existing_tecnicos_name_email:
            _add_issue(
                issues,
                index,
                "nombre_completo",
                "warning",
                "ALREADY_LOADED_DUPLICATE_NAME_EMAIL",
                "Posible duplicado: nombre y correo ya existen en técnicos cargados al sistema",
                row.get("nombre_completo"),
                "ELIMINAR_FILA",
            )
        elif full_name and phone and (full_name, phone) in catalogs.existing_tecnicos_name_phone:
            _add_issue(
                issues,
                index,
                "nombre_completo",
                "warning",
                "ALREADY_LOADED_DUPLICATE_NAME_PHONE",
                "Posible duplicado: nombre y teléfono ya existen en técnicos cargados al sistema",
                row.get("nombre_completo"),
                "ELIMINAR_FILA",
            )

        # Area se limpia siempre: el portal EOP no requiere este campo
        old_area = row.get("area", "")
        if old_area.strip():
            _set_value(row, "area", "", index, "clear_area", corrections)
        area = ""

        trabajo = normalize_key(row.get("trabajo"))
        if trabajo and trabajo not in catalogs.trabajos:
            _add_issue(issues, index, "trabajo", "error", "INVALID_WORK", "Trabajo no parametrizado", row.get("trabajo"))

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

    if catalogs.existing_tecnicos_snapshot_date:
        _add_issue(
            issues,
            1,
            "tecnicos_exportados",
            "warning",
            "EXTERNAL_USERS_SNAPSHOT",
            (
                "La validación de duplicidad de usuarios usa snapshot con fecha "
                f"{catalogs.existing_tecnicos_snapshot_date}. "
                "Registros actualizados posteriormente podrían no detectarse."
            ),
        )

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
            if lower in catalogs.existing_tecnicos_emails:
                _add_issue(
                    issues,
                    index,
                    "email",
                    "warning",
                    "ALREADY_LOADED_USER_DUPLICATE_EMAIL",
                    "Posible duplicado: el email ya existe en usuarios cargados al sistema",
                    email,
                    "ELIMINAR_FILA",
                )

        identifier = row.get("identificacion", "").strip()
        if identifier:
            norm = _normalize_identifier(identifier)
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
            if norm in catalogs.existing_tecnicos_ids:
                _add_issue(
                    issues,
                    index,
                    "identificacion",
                    "warning",
                    "ALREADY_LOADED_USER_DUPLICATE_ID",
                    "Posible duplicado: la identificación ya existe en usuarios cargados al sistema",
                    identifier,
                    "ELIMINAR_FILA",
                )

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
            _add_issue(issues, index, "regional", "error", "INVALID_REGIONAL", "Regional (ID) no parametrizada", row.get("regional"))

        nit = normalize_key(row.get("compania (nit)"))
        if nit and nit not in catalogs.companias_nit:
            original_company_value = row.get("compania (nit)")
            mapped_nit = catalogs.compania_name_to_nit.get(nit)
            if mapped_nit:
                _set_value(row, "compania (nit)", mapped_nit, index, "map_company_name_to_nit", corrections)
                _add_issue(
                    issues,
                    index,
                    "compania (nit)",
                    "warning",
                    "COMPANY_NAME_MAPPED_TO_NIT",
                    "Compañía convertida automáticamente de nombre a NIT",
                    original_company_value,
                    mapped_nit,
                )
            else:
                _add_issue(issues, index, "compania (nit)", "error", "INVALID_NIT", "NIT no parametrizado", row.get("compania (nit)"))


def _validate_plan_padrino(rows: list[dict[str, str]], catalogs: Catalogs, issues: list[ValidationIssue]) -> None:
    if catalogs.existing_tecnicos_snapshot_date:
        _add_issue(
            issues,
            1,
            "tecnicos_exportados",
            "warning",
            "EXTERNAL_PLAN_PADRINO_SNAPSHOT",
            (
                "La validación de supervisor/técnico en Plan Padrino usa snapshot con fecha "
                f"{catalogs.existing_tecnicos_snapshot_date}. "
                "Registros actualizados posteriormente podrían no detectarse."
            ),
        )

    for index, row in enumerate(rows, start=2):
        padrino = row.get("padrino identificacion", "").strip()
        tecnico = row.get("tecnico identificacion", "").strip()
        activo_raw = row.get("activo", "").strip()
        activo_norm = normalize_key(activo_raw)
        if activo_norm in {"OPERATIVO", "ACTIVO", "1"}:
            activo = "1"
        elif activo_norm in {"NO OPERATIVO", "INACTIVO", "0"}:
            activo = "0"
        else:
            activo = activo_raw

        if not padrino:
            _add_issue(issues, index, "padrino identificacion", "error", "REQUIRED", "Padrino identificación es obligatorio")
        if not tecnico:
            _add_issue(issues, index, "tecnico identificacion", "error", "REQUIRED", "Técnico identificación es obligatorio")
        if activo not in {"0", "1"}:
            _add_issue(issues, index, "activo", "error", "INVALID_ACTIVE", "Activo debe ser 1 o 0", activo)

        padrino_norm = _normalize_identifier(padrino) if padrino else ""
        tecnico_norm = _normalize_identifier(tecnico) if tecnico else ""

        if padrino and padrino_norm not in catalogs.existing_tecnicos_ids:
            _add_issue(
                issues,
                index,
                "padrino identificacion",
                "error",
                "SUPERVISOR_NOT_FOUND",
                "Supervisor no existe en técnicos exportados",
                padrino,
            )

        if tecnico and tecnico_norm not in catalogs.existing_tecnicos_ids:
            _add_issue(
                issues,
                index,
                "tecnico identificacion",
                "error",
                "TECHNICIAN_NOT_FOUND",
                "Técnico no existe en técnicos exportados",
                tecnico,
            )
