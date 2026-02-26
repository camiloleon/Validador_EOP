from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


class UnsupportedInputFormatError(ValueError):
    pass


def convert_to_csv_bytes(filename: str, content: bytes) -> bytes:
    extension = Path(filename or "").suffix.lower()

    if extension in {"", ".csv", ".txt"}:
        return content
    if extension == ".json":
        return _json_to_csv(content).encode("utf-8")
    if extension in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return _xlsx_to_csv(content).encode("utf-8")
    if extension == ".xls":
        return _xls_to_csv(content).encode("utf-8")

    raise UnsupportedInputFormatError(
        "Formato no soportado. Usa csv, json, xlsx o xls."
    )


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _safe_header(value: Any, index: int) -> str:
    text = _to_text(value)
    return text if text else f"col_{index}"


def _xlsx_to_csv(content: bytes) -> str:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise UnsupportedInputFormatError("El archivo Excel no contiene datos.")

    headers = [_safe_header(value, index + 1) for index, value in enumerate(rows[0])]
    output = io.StringIO()
    writer = csv.writer(output, delimiter=",", lineterminator="\n")
    writer.writerow(headers)

    for row in rows[1:]:
        values = [_to_text(value) for value in row[: len(headers)]]
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        writer.writerow(values)

    return output.getvalue()


def _xls_to_csv(content: bytes) -> str:
    try:
        import xlrd
    except ModuleNotFoundError as exc:
        raise UnsupportedInputFormatError(
            "Para archivos .xls instala 'xlrd' o convierte a xlsx/csv."
        ) from exc

    workbook = xlrd.open_workbook(file_contents=content)
    if workbook.nsheets == 0:
        raise UnsupportedInputFormatError("El archivo XLS no contiene hojas.")

    sheet = workbook.sheet_by_index(0)
    if sheet.nrows == 0:
        raise UnsupportedInputFormatError("El archivo XLS no contiene datos.")

    headers = [_safe_header(sheet.cell_value(0, col), col + 1) for col in range(sheet.ncols)]

    output = io.StringIO()
    writer = csv.writer(output, delimiter=",", lineterminator="\n")
    writer.writerow(headers)

    for row_idx in range(1, sheet.nrows):
        values = [_to_text(sheet.cell_value(row_idx, col)) for col in range(sheet.ncols)]
        writer.writerow(values)

    return output.getvalue()


def _json_to_csv(content: bytes) -> str:
    try:
        parsed = json.loads(content.decode("utf-8-sig", errors="replace"))
    except json.JSONDecodeError as exc:
        raise UnsupportedInputFormatError("JSON inválido.") from exc

    records: list[dict[str, Any]]
    if isinstance(parsed, list):
        records = [item for item in parsed if isinstance(item, dict)]
    elif isinstance(parsed, dict):
        payload = parsed.get("rows") or parsed.get("data") or parsed.get("items")
        if isinstance(payload, list):
            records = [item for item in payload if isinstance(item, dict)]
        else:
            records = [parsed]
    else:
        raise UnsupportedInputFormatError("JSON no compatible. Usa lista de objetos.")

    if not records:
        raise UnsupportedInputFormatError("JSON sin registros.")

    headers: list[str] = []
    for record in records:
        for key in record.keys():
            normalized = str(key)
            if normalized not in headers:
                headers.append(normalized)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, delimiter=",", lineterminator="\n")
    writer.writeheader()

    for record in records:
        writer.writerow({header: _to_text(record.get(header)) for header in headers})

    return output.getvalue()
