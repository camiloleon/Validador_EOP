from __future__ import annotations

from src.validador_eop.catalog_loader import Catalogs
from src.validador_eop.validator import validate_csv


def _catalogs() -> Catalogs:
    return Catalogs(
        roles={"TECNICO", "OWNER", "JEFE"},
        areas={"MINTIC CENTROS DIGITALES", "UMM"},
        trabajos={"MANTENIMIENTO", "SUPERVISOR"},
        trabajos_por_area={"MINTIC CENTROS DIGITALES": {"MANTENIMIENTO", "SUPERVISOR"}},
        ciudades={"MEDELLIN", "APARTADO", "IBAGUE"},
        ciudad_to_base={"MEDELLIN": "ITAGUI", "APARTADO": "ITAGUI", "IBAGUE": "TOLIMA"},
        ciudad_to_regional={"MEDELLIN": "R2 NORORIENTE"},
        bases={"ITAGUI", "TOLIMA"},
        regionales={"R2 NORORIENTE", "R1 COSTA"},
        companias_nit={"900123456-7"},
    )


def test_tecnicos_valid_and_autofix_base() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n123;NOMBRE UNO;uno@mail.com;;Mintic Centros Digitales;Mantenimiento;MEDELLIN;;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert result.summary.error_count == 0
    assert result.summary.correction_count >= 1
    assert "ITAGUI" in result.corrected_csv


def test_tecnicos_duplicate_email_error() -> None:
    content = b"identificacion, nombre_completo, correo, telefono, area, trabajo, ciudad, base_operativa, estado_operativo\n1,AAA,a@mail.com,,Mintic Centros Digitales,Mantenimiento,MEDELLIN,ITAGUI,ACTIVO\n2,BBB,a@mail.com,,Mintic Centros Digitales,Mantenimiento,MEDELLIN,ITAGUI,ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert result.summary.error_count >= 1
    assert any(issue.code == "DUPLICATE_EMAIL" for issue in result.issues)


def test_usuarios_invalid_role_error() -> None:
    content = "nombre completo;email;identificación;celular;contraseña;rol de usuario;regional;compañía (nit)\nUser Uno;u1@mail.com;100;; ;NoExiste;R2 NORORIENTE;900123456-7\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert any(issue.code == "INVALID_ROLE" for issue in result.issues)


def test_plan_padrino_invalid_activo() -> None:
    content = "Padrino Identificación,Tecnico Identificación,Activo\n100,200,2\n".encode("utf-8")
    result = validate_csv("plan_padrino", content, _catalogs())
    assert any(issue.code == "INVALID_ACTIVE" for issue in result.issues)


def test_missing_column_error() -> None:
    content = b"identificacion;nombre_completo\n123;x\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert result.summary.error_count == 1
    assert result.issues[0].code == "MISSING_COLUMNS"


def test_tecnicos_returns_correction_options() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n1;A;a@mail.com;;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert "area" in result.correction_options
    assert "trabajo" in result.correction_options
    assert "base_operativa" in result.correction_options
    assert len(result.correction_options["area"]) > 0


def test_tecnicos_city_base_inconsistency_is_error() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n1;A;a@mail.com;;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;TOLIMA;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    mismatch = [issue for issue in result.issues if issue.code == "CITY_BASE_INCONSISTENT"]
    assert mismatch
    assert mismatch[0].severity == "error"


def test_tecnicos_base_without_city_is_error() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n1;A;a@mail.com;;MINTIC CENTROS DIGITALES;MANTENIMIENTO;;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    missing_city = [issue for issue in result.issues if issue.code == "MISSING_CITY_FOR_BASE"]
    assert missing_city
    assert missing_city[0].severity == "error"
