# Validador EOP

Sistema web tipo wizard para validar plantillas del sistema de Excelencia Operativa (EOP), aplicar autocorrecciones seguras, corregir errores uno a uno y descargar el CSV final.

## Alcance implementado
- Validación de plantillas: `tecnicos`, `usuarios`, `plan_padrino`.
- Carga de archivos fuente: `csv`, `json`, `xlsx`, `xls`.
- Conversión automática del archivo fuente a CSV antes de validar.
- Detección de delimitador CSV (`,`, `;`, tab, `|`).
- Validaciones por tipo, obligatoriedad, unicidad y catálogos.
- Autocorrecciones seguras con auditoría por campo.
- Resumen de errores, advertencias y datos sospechosos.
- Corrección manual por fila de error en el paso final del wizard.
- Descarga del CSV corregido final.
- Pruebas automatizadas con `pytest`.

## Ejecutar
1. Activar entorno virtual.
2. Instalar dependencias (si falta alguna):
   - `pip install -r requirements.txt`
3. Levantar API:
   - `python -m uvicorn src.validador_eop.app:app --reload`
4. Abrir:
   - `http://127.0.0.1:8000`

## Pruebas
- `pytest -q`

## Despliegue con Docker
1. Copiar variables de entorno:
   - `cp .env.example .env`
2. Construir y levantar:
   - `docker compose up -d --build`
3. Verificar salud:
   - `curl -f http://127.0.0.1:8000/api/health`
4. Ver logs:
   - `docker compose logs -f validador-eop`

Guía completa: `docs/deploy_produccion.md`.

## Notas
- Catálogos cargados desde `Parametros/Parametrizacion EOP.xlsx`.
- Envío al sistema EOP disponible vía `/api/submit`.
- Si `EOP_API_URL` no está configurada, el envío opera en modo simulado seguro.
- Para integración real, configure:
   - `EOP_API_URL=https://...`
   - `EOP_API_KEY=...` (opcional, bearer token)
