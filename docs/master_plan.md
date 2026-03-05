# Master Plan — Validador EOP

Fecha de corte: 2026-03-05  
Estado general: **MVP robusto en producción técnica** (pendiente hardening de operación)

## 1) Objetivo maestro
Construir y operar un validador EOP confiable para carga masiva, que:
- reciba archivos reales en formatos heterogéneos,
- convierta y valide contra reglas de negocio,
- aplique autocorrecciones seguras,
- facilite corrección manual guiada,
- y entregue CSV final listo para envío al EOP.

## 2) Alcance base comprometido (Plan inicial)
- Plantillas: `tecnicos`, `usuarios`, `plan_padrino`.
- Ingesta: `csv`, `json`, `xlsx`, `xls`.
- Conversión a CSV previa a validación.
- Validaciones de obligatoriedad, tipo, unicidad, catálogos.
- Autocorrecciones auditadas.
- Flujo web wizard con resumen y descarga.
- Pruebas automatizadas con `pytest`.

## 3) Estado de cumplimiento vs plan maestro

### A. Cumplido y validado
1. **Motor de validación multi-plantilla operativo**.
2. **Conversión de entrada** para los formatos definidos.
3. **Autocorrecciones con bitácora** (`corrections`).
4. **UI de operación** con flujo de selección → validación → corrección → descarga.
5. **Revalidación iterativa** vía API (`/api/revalidate`).
6. **Pruebas unitarias activas**, incluyendo casos reales no triviales.

### B. Mejoras implementadas que no estaban claras al inicio (y hoy son clave)
1. **Detección de delimitador extendida**: `,`, `;`, `\t`, `|`.
2. **Decodificación robusta de bytes**: UTF-8, UTF-8 BOM, UTF-16 BOM, heurística UTF-16 LE, fallback latin-1.
3. **Alias de cabeceras por plantilla** (ej. `Nombre`, `NIT`, `CORREO`, `CARGO`, etc.).
4. **Tolerancia de estructura alterna en plan padrino**:
   - mapeo `Identificacion -> padrino identificacion`,
   - mapeo `Estado -> activo`,
   - inferencia de `tecnico identificacion` cuando aplica.
5. **Normalización de estados de activo** desde texto (`Operativo/Activo`, `No Operativo/Inactivo`).
6. **Sugerencia de cambio de plantilla** cuando la estructura no corresponde (`TEMPLATE_MISMATCH_SUGGESTION`).
7. **Filtro de filas totalmente vacías** para eliminar ruido de errores falsos.
8. **Cobertura de regresión agregada** para separadores, encoding, alias y estructura alterna.

### C. Estado global
- **Cobertura funcional del objetivo**: Alta.
- **Robustez de ingesta real-world**: Alta.
- **Madurez operativa (observabilidad/seguridad/rendimiento)**: Media.

## 4) Brechas actuales (priorizadas)

### P0 (crítico operativo)
1. **Observabilidad productiva**: métricas y trazas por plantilla, errores por código, tiempos por etapa.
2. **Control formal de errores del runtime**: manejo homogéneo y logs estructurados en API/UI.
3. **Contrato de compatibilidad de catálogos**: validación de versión/estructura de Excel de parámetros.

### P1 (impacto usuario)
1. **Acción UI para sugerencia de plantilla**: botón “Cambiar a plantilla sugerida”.
2. **Normalización de dominios frecuentes** (roles/regionales/NIT de proveedores reales) para reducir falsos negativos funcionales.
3. **Reporte de calidad de datos por lote** (top errores + recomendaciones de remediación).

### P2 (escalamiento)
1. **RBAC y auditoría de usuario/acción**.
2. **Pruebas de carga y sizing** para lotes grandes.
3. **Versionado formal de reglas** y estrategia de rollback.

## 5) Roadmap de ejecución recomendado

## Fase 1 — Cierre de robustez operativa (1-2 semanas)
- Instrumentar métricas clave y logs estructurados.
- Normalizar manejo de excepciones API/UI.
- Definir y validar contrato de catálogos.

**Criterio de salida**:
- Dashboard básico de salud y métricas.
- 0 errores no controlados en flujo principal bajo pruebas.

## Fase 2 — UX de precisión y reducción de fricción (1 semana)
- Implementar CTA para aplicar plantilla sugerida.
- Reglas de normalización de dominio para usuarios/tecnicos según datos reales.
- Mensajes de hallazgo más accionables.

**Criterio de salida**:
- Disminución medible de rechazos por estructura/alias en pruebas con archivos reales.

## Fase 3 — Gobierno y escalabilidad (2-3 semanas)
- RBAC básico + auditoría de cambios/correcciones.
- Pruebas de volumen y umbrales de performance.
- Versionado de reglas + changelog operativo.

**Criterio de salida**:
- Trazabilidad completa por ejecución.
- Aprobación de readiness para operación continua.

## 6) KPIs de control del Master Plan
1. **Tasa de reconocimiento estructural** por plantilla (objetivo > 98%).
2. **Errores críticos por carga** (objetivo tendencia descendente semanal).
3. **Tiempo medio de validación por archivo** (SLA definido por tamaño).
4. **% de cargas resueltas sin intervención manual**.
5. **% de correcciones manuales por campo dominante** (para guiar nuevas reglas).

## 7) Riesgos y mitigaciones
1. **Variabilidad de archivos fuente** → ampliar alias y pruebas de regresión por proveedor.
2. **Deriva de catálogo Excel** → validación de esquema y versión antes de procesar.
3. **Escalamiento sin observabilidad** → prioridad P0 para métricas y alertas.

## 8) Decisión ejecutiva actual
El proyecto **sí cumple el objetivo funcional principal** y ya incorpora mejoras de resiliencia que no estaban completamente definidas al inicio.  
La siguiente etapa debe enfocarse en **operación y gobernanza** (P0/P1), no en reescribir el núcleo de validación.
