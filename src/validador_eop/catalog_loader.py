from __future__ import annotations

from pathlib import Path

import openpyxl

from .normalization import normalize_key


class Catalogs:
    def __init__(
        self,
        roles: set[str],
        areas: set[str],
        trabajos: set[str],
        trabajos_por_area: dict[str, set[str]],
        ciudades: set[str],
        ciudad_to_base: dict[str, str],
        ciudad_to_regional: dict[str, str],
        bases: set[str],
        regionales: set[str],
        companias_nit: set[str],
    ) -> None:
        self.roles = roles
        self.areas = areas
        self.trabajos = trabajos
        self.trabajos_por_area = trabajos_por_area
        self.ciudades = ciudades
        self.ciudad_to_base = ciudad_to_base
        self.ciudad_to_regional = ciudad_to_regional
        self.bases = bases
        self.regionales = regionales
        self.companias_nit = companias_nit


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_catalogs_from_excel(excel_path: str | Path) -> Catalogs:
    workbook = openpyxl.load_workbook(excel_path, data_only=True)

    roles: set[str] = set()
    areas: set[str] = set()
    trabajos: set[str] = set()
    trabajos_por_area: dict[str, set[str]] = {}
    ciudades: set[str] = set()
    ciudad_to_base: dict[str, str] = {}
    ciudad_to_regional: dict[str, str] = {}
    bases: set[str] = set()
    regionales: set[str] = set()
    companias_nit: set[str] = set()

    if "Roles" in workbook.sheetnames:
        sheet = workbook["Roles"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            role = normalize_key(_safe_text(row[1] if len(row) > 1 else None))
            if role:
                roles.add(role)

    if "Areas" in workbook.sheetnames:
        sheet = workbook["Areas"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            area = normalize_key(_safe_text(row[1] if len(row) > 1 else None))
            if area:
                areas.add(area)

    if "Tipo Trabajos" in workbook.sheetnames:
        sheet = workbook["Tipo Trabajos"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            trabajo = normalize_key(_safe_text(row[1] if len(row) > 1 else None))
            area = normalize_key(_safe_text(row[2] if len(row) > 2 else None))
            if trabajo:
                trabajos.add(trabajo)
                if area:
                    trabajos_por_area.setdefault(area, set()).add(trabajo)

    if "Ciudades" in workbook.sheetnames:
        sheet = workbook["Ciudades"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            ciudad = normalize_key(_safe_text(row[1] if len(row) > 1 else None))
            base = normalize_key(_safe_text(row[3] if len(row) > 3 else None))
            regional = normalize_key(_safe_text(row[4] if len(row) > 4 else None))
            if ciudad:
                ciudades.add(ciudad)
                if base:
                    ciudad_to_base[ciudad] = base
                if regional:
                    ciudad_to_regional[ciudad] = regional

    if "Bases Operativas" in workbook.sheetnames:
        sheet = workbook["Bases Operativas"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            base = normalize_key(_safe_text(row[1] if len(row) > 1 else None))
            regional = normalize_key(_safe_text(row[4] if len(row) > 4 else None))
            if base:
                bases.add(base)
            if regional:
                regionales.add(regional)

    if "Regionales" in workbook.sheetnames:
        sheet = workbook["Regionales"]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            regional = normalize_key(_safe_text(row[1] if len(row) > 1 else None))
            if regional:
                regionales.add(regional)

    if "Compa�ias" in workbook.sheetnames:
        sheet = workbook["Compa�ias"]
    elif "Compañias" in workbook.sheetnames:
        sheet = workbook["Compañias"]
    else:
        sheet = None

    if sheet is not None:
        for row in sheet.iter_rows(min_row=2, values_only=True):
            nit = normalize_key(_safe_text(row[0] if len(row) > 0 else None))
            if nit:
                companias_nit.add(nit)

    return Catalogs(
        roles=roles,
        areas=areas,
        trabajos=trabajos,
        trabajos_por_area=trabajos_por_area,
        ciudades=ciudades,
        ciudad_to_base=ciudad_to_base,
        ciudad_to_regional=ciudad_to_regional,
        bases=bases,
        regionales=regionales,
        companias_nit=companias_nit,
    )
