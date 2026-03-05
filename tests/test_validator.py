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
        regionales={"R2", "R1"},
        companias_nit={"900123456-7"},
        compania_nit_to_name={"900123456-7": "CLARO COLOMBIA"},
        compania_name_to_nit={"CLARO COLOMBIA": "900123456-7"},
    )


def _catalogs_with_existing_tecnicos() -> Catalogs:
    return Catalogs(
        roles={"TECNICO", "OWNER", "JEFE"},
        areas={"MINTIC CENTROS DIGITALES", "UMM"},
        trabajos={"MANTENIMIENTO", "SUPERVISOR"},
        trabajos_por_area={"MINTIC CENTROS DIGITALES": {"MANTENIMIENTO", "SUPERVISOR"}},
        ciudades={"MEDELLIN", "APARTADO", "IBAGUE"},
        ciudad_to_base={"MEDELLIN": "ITAGUI", "APARTADO": "ITAGUI", "IBAGUE": "TOLIMA"},
        ciudad_to_regional={"MEDELLIN": "R2 NORORIENTE"},
        bases={"ITAGUI", "TOLIMA"},
        regionales={"R2", "R1"},
        companias_nit={"900123456-7"},
        compania_nit_to_name={"900123456-7": "CLARO COLOMBIA"},
        compania_name_to_nit={"CLARO COLOMBIA": "900123456-7"},
        existing_tecnicos_ids={"123456", "777777"},
        existing_tecnicos_emails={"juan@mail.com"},
        existing_tecnicos_name_email={("JUAN PEREZ", "juan@mail.com")},
        existing_tecnicos_name_phone={("ANA GOMEZ", "3001234567")},
        existing_tecnicos_phones={"3001234567"},
        existing_tecnicos_snapshot_date="2026-03-01 09:30",
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
    content = "nombre completo;email;identificación;celular;contraseña;rol de usuario;regional;compañía (nit)\nUser Uno;u1@mail.com;100;; ;NoExiste;R2;900123456-7\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert any(issue.code == "INVALID_ROLE" for issue in result.issues)


def test_usuarios_invalid_regional_id_error() -> None:
    content = "nombre completo;email;identificación;celular;contraseña;rol de usuario;regional;compañía (nit)\nUser Uno;u1@mail.com;100;; ;TECNICO;R2 NORORIENTE;900123456-7\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert any(issue.code == "INVALID_REGIONAL" for issue in result.issues)


def test_usuarios_warn_duplicate_against_existing_by_id_and_email() -> None:
    content = "nombre completo;email;identificación;celular;contraseña;rol de usuario;regional;compañía (nit)\nUser Uno;juan@mail.com;123456;3001234567;123456;TECNICO;R2;900123456-7\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs_with_existing_tecnicos())
    assert any(issue.code == "ALREADY_LOADED_USER_DUPLICATE_ID" for issue in result.issues)
    assert any(issue.code == "ALREADY_LOADED_USER_DUPLICATE_EMAIL" for issue in result.issues)
    assert any(issue.code == "EXTERNAL_USERS_SNAPSHOT" for issue in result.issues)


def test_usuarios_mojibake_headers_are_matched() -> None:
    content = (
        "Nombre Completo,Email,Identificacia�n,Celular,Contrasea�a,Rol de Usuario,Regional,Compaa�a�a (NIT)\n"
        "User Uno,u1@mail.com,100,3001112222,100,TECNICO,R2,900123456-7\n"
    ).encode("utf-8", errors="replace")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)


def test_usuarios_correlation_map_exposes_company_nit_labels() -> None:
    content = "nombre completo;email;identificación;celular;contraseña;rol de usuario;regional;compañía (nit)\nUser Uno;u1@mail.com;100;3001112222;100;TECNICO;R2;900123456-7\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    labels = result.correlation_maps.get("company_nit_labels")
    assert isinstance(labels, dict)
    assert labels.get("900123456-7") == "CLARO COLOMBIA - 900123456-7"


def test_usuarios_tab_separated_file() -> None:
    hdr = "Nombre Completo\tEmail\tIdentificación\tCelular\tContraseña\tRol de Usuario\tRegional\tCompañía (NIT)"
    row = "User Uno\tu1@mail.com\t100\t3001112222\t100\tTECNICO\tR2\t900123456-7"
    content = f"{hdr}\n{row}\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)


def test_usuarios_utf16_with_bom() -> None:
    hdr = "Nombre Completo,Email,Identificación,Celular,Contraseña,Rol de Usuario,Regional,Compañía (NIT)"
    row = "User Uno,u1@mail.com,100,3001112222,100,TECNICO,R2,900123456-7"
    content = f"{hdr}\n{row}\n".encode("utf-16")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)


def test_usuarios_pipe_separated_file() -> None:
    hdr = "Nombre Completo|Email|Identificación|Celular|Contraseña|Rol de Usuario|Regional|Compañía (NIT)"
    row = "User Uno|u1@mail.com|100|3001112222|100|TECNICO|R2|900123456-7"
    content = f"{hdr}\n{row}\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)


def test_usuarios_accepts_nombre_and_nit_headers() -> None:
    content = (
        "Nombre;Email;Identificacion;Celular;Contrase\uFFFDa;Rol de Usuario;Regional;NIT\n"
        "SILVIO GIRONZA HOYOS;Silvio.gironza@gmail.com;94504033;3144481388;94504033;supervisor;R3;8301349713\n"
    ).encode("utf-8", errors="replace")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)


def test_usuarios_accepts_correo_and_cargo_headers() -> None:
    content = (
        "NOMBRE COMPLETO;CORREO;IDENTIFICACION;CELULAR;CONTRASE\u00d1A;CARGO;REGIONAL;NIT\n"
        "USER UNO;u1@mail.com;100;3001112222;;TECNICO;R2;900123456-7\n"
    ).encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)


def test_usuarios_skips_fully_empty_rows() -> None:
    content = (
        "NOMBRE COMPLETO;CORREO;IDENTIFICACION;CELULAR;CONTRASENA;CARGO;REGIONAL;NIT\n"
        "USER UNO;u1@mail.com;100;3001112222;;TECNICO;R2;900123456-7\n"
        ";;;;;;;\n"
        " ; ; ; ; ; ; ; \n"
    ).encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert result.summary.total_rows == 1


def test_usuarios_maps_company_name_to_nit() -> None:
    content = "nombre completo;email;identificación;celular;contraseña;rol de usuario;regional;compañía (nit)\nUser Uno;u1@mail.com;100;3001112222;100;TECNICO;R2;CLARO COLOMBIA\n".encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    assert any(issue.code == "COMPANY_NAME_MAPPED_TO_NIT" for issue in result.issues)
    assert "900123456-7" in result.corrected_csv


def test_plan_padrino_invalid_activo() -> None:
    content = "Padrino Identificación,Tecnico Identificación,Activo\n100,200,2\n".encode("utf-8")
    result = validate_csv("plan_padrino", content, _catalogs())
    assert any(issue.code == "INVALID_ACTIVE" for issue in result.issues)


def test_plan_padrino_requires_supervisor_and_technician_existing() -> None:
    content = "Padrino Identificación,Tecnico Identificación,Activo\n123456,999999,1\n".encode("utf-8")
    result = validate_csv("plan_padrino", content, _catalogs_with_existing_tecnicos())
    assert any(issue.code == "TECHNICIAN_NOT_FOUND" for issue in result.issues)
    assert not any(issue.code == "SUPERVISOR_NOT_FOUND" for issue in result.issues)


def test_plan_padrino_accepts_existing_supervisor_and_technician() -> None:
    content = "Padrino Identificación,Tecnico Identificación,Activo\n123456,777777,1\n".encode("utf-8")
    result = validate_csv("plan_padrino", content, _catalogs_with_existing_tecnicos())
    assert not any(issue.code == "SUPERVISOR_NOT_FOUND" for issue in result.issues)
    assert not any(issue.code == "TECHNICIAN_NOT_FOUND" for issue in result.issues)
    assert any(issue.code == "EXTERNAL_PLAN_PADRINO_SNAPSHOT" for issue in result.issues)


def test_plan_padrino_accepts_alternative_structure() -> None:
    content = (
        "Nombre;Identificacion;Cargo;Estado;Celular;Correo\n"
        "Jennifer Salazar Vergara;1143841118;Padrino;Operativo;3103865355;j.salazarve@tabascooc.com\n"
    ).encode("utf-8")
    result = validate_csv("plan_padrino", content, _catalogs_with_existing_tecnicos())
    assert result.summary.total_rows == 1
    assert not any(issue.code == "MISSING_COLUMNS" for issue in result.issues)
    assert not any(issue.code == "INVALID_ACTIVE" for issue in result.issues)


def test_missing_column_error() -> None:
    content = b"identificacion;nombre_completo\n123;x\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert result.summary.error_count == 1
    assert result.issues[0].code == "MISSING_COLUMNS"


def test_suggests_usuarios_when_plan_padrino_selected() -> None:
    content = (
        "Nombre;Email;Identificacion;Celular;Contrase\u00f1a;Rol de Usuario;Regional;NIT\n"
        "User Uno;u1@mail.com;100;3001112222;100;TECNICO;R2;900123456-7\n"
    ).encode("utf-8")
    result = validate_csv("plan_padrino", content, _catalogs())
    suggestion = [issue for issue in result.issues if issue.code == "TEMPLATE_MISMATCH_SUGGESTION"]
    assert suggestion
    assert suggestion[0].suggested_value == "usuarios"


def test_suggests_plan_padrino_when_usuarios_selected() -> None:
    content = (
        "Nombre;Identificacion;Cargo;Estado;Celular;Correo\n"
        "Jennifer Salazar Vergara;1143841118;Padrino;Operativo;3103865355;j.salazarve@tabascooc.com\n"
    ).encode("utf-8")
    result = validate_csv("usuarios", content, _catalogs())
    suggestion = [issue for issue in result.issues if issue.code == "TEMPLATE_MISMATCH_SUGGESTION"]
    assert suggestion
    assert suggestion[0].suggested_value == "plan_padrino"


def test_tecnicos_returns_correction_options() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n1;A;a@mail.com;;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert "area" not in result.correction_options
    assert "trabajo" in result.correction_options
    assert "base_operativa" in result.correction_options
    # area debe limpiarse automáticamente
    clear_area = [c for c in result.corrections if c.field == "area" and c.rule == "clear_area"]
    assert clear_area


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


def test_tecnicos_warns_duplicate_against_existing_by_id() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n123456;JUAN PEREZ;otro@mail.com;3000000000;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs_with_existing_tecnicos())
    issues = [issue for issue in result.issues if issue.code == "ALREADY_LOADED_DUPLICATE_ID"]
    assert issues
    assert issues[0].suggested_value == "ELIMINAR_FILA"


def test_tecnicos_warns_duplicate_against_existing_by_name_email() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n999999;JUAN PEREZ;juan@mail.com;3111111111;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs_with_existing_tecnicos())
    assert any(issue.code == "ALREADY_LOADED_DUPLICATE_NAME_EMAIL" for issue in result.issues)


def test_tecnicos_duplicate_phone_in_file() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n1;AAA;a@mail.com;3009999999;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n2;BBB;b@mail.com;3009999999;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs())
    assert any(issue.code == "DUPLICATE_PHONE" for issue in result.issues)


def test_tecnicos_warns_duplicate_phone_against_existing() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n999997;OTRO TECNICO;otro@mail.com;3001234567;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs_with_existing_tecnicos())
    assert any(issue.code == "ALREADY_LOADED_DUPLICATE_PHONE" for issue in result.issues)


def test_tecnicos_warns_snapshot_date_limitation() -> None:
    content = b"identificacion;nombre_completo;correo;telefono;area;trabajo;ciudad;base_operativa;estado_operativo\n999998;ANA GOMEZ;ana.otra@mail.com;3001234567;MINTIC CENTROS DIGITALES;MANTENIMIENTO;MEDELLIN;ITAGUI;ACTIVO\n"
    result = validate_csv("tecnicos", content, _catalogs_with_existing_tecnicos())
    assert any(issue.code == "EXTERNAL_TECHNICIANS_SNAPSHOT" for issue in result.issues)
