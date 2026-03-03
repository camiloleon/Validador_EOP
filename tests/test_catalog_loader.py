from __future__ import annotations

from pathlib import Path

from src.validador_eop.catalog_loader import load_catalogs_from_excel


def test_catalog_loader_reads_excel() -> None:
    path = Path("Parametros/Parametrizacion EOP.xlsx")
    catalogs = load_catalogs_from_excel(path)
    assert len(catalogs.roles) > 0
    assert len(catalogs.areas) > 0
    assert len(catalogs.ciudades) > 0
    assert len(catalogs.regionales) > 0
    assert len(catalogs.existing_tecnicos_ids) > 0
