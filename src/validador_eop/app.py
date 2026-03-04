from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .catalog_loader import Catalogs, load_catalogs_from_excel
from .eop_client import submit_to_eop
from .file_ingest import UnsupportedInputFormatError, convert_to_csv_bytes
from .models import ValidationResult
from .validator import validate_csv

BASE_DIR = Path(__file__).resolve().parents[2]
CATALOG_PATH = BASE_DIR / "Parametros" / "Parametrizacion EOP.xlsx"

app = FastAPI(title="Validador EOP", version="1.0.0")

_catalogs_cache: Catalogs | None = None


class SubmitRequest(BaseModel):
    template: str
    corrected_csv: str


class RevalidateRequest(BaseModel):
  template: str
  corrected_csv: str


class SubmitResponse(BaseModel):
    accepted: bool
    mode: str
    message: str
    external_id: str


def get_catalogs() -> Catalogs:
    global _catalogs_cache
    if _catalogs_cache is None:
        _catalogs_cache = load_catalogs_from_excel(CATALOG_PATH)
    return _catalogs_cache


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/validate", response_model=ValidationResult)
async def validate_endpoint(
    template: str = Form(...),
    csv_file: UploadFile = File(...),
) -> ValidationResult:
    content = await csv_file.read()
    try:
        csv_content = convert_to_csv_bytes(csv_file.filename or "", content)
    except UnsupportedInputFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    catalogs = get_catalogs()
    return validate_csv(template=template, content=csv_content, catalogs=catalogs)


@app.post("/api/submit", response_model=SubmitResponse)
def submit_endpoint(request: SubmitRequest) -> SubmitResponse:
    result = submit_to_eop(template=request.template, corrected_csv=request.corrected_csv)
    return SubmitResponse(
        accepted=result.accepted,
        mode=result.mode,
        message=result.message,
        external_id=result.external_id,
    )


@app.post("/api/revalidate", response_model=ValidationResult)
def revalidate_endpoint(request: RevalidateRequest) -> ValidationResult:
    catalogs = get_catalogs()
    content = request.corrected_csv.encode("utf-8")
    return validate_csv(template=request.template, content=content, catalogs=catalogs)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!doctype html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Validador EOP · Wizard</title>
  <style>
    :root {
      --brand: #DF3346;
      --bg: #ECECEC;
      --text: #101828;
      --muted: #475467;
      --line: #D0D5DD;
      --soft: #FFF1F3;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, Arial, sans-serif; background: var(--bg); color: var(--text); }
    .topbar { height: 68px; background: var(--brand); color: white; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; }
    .brand { font-size: 32px; font-weight: 700; }
    .admin { font-size: 14px; color: #FFD9DE; }
    .page { max-width: 1120px; margin: 22px auto; padding: 0 16px; }
    h1 { margin: 0 0 14px 0; font-size: 44px; }
    .steps { display: flex; gap: 8px; margin-bottom: 14px; }
    .pill { border: 1px solid var(--line); border-radius: 999px; background: white; color: #344054; font-size: 12px; font-weight: 600; padding: 7px 13px; }
    .pill.active { background: var(--brand); color: white; border-color: var(--brand); }
    .card { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 22px; }
    .subtitle { color: var(--muted); margin-top: 4px; }
    .template-list { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
    .template-option { border: 1px solid var(--line); border-radius: 12px; background: #F9FAFB; padding: 14px 16px; cursor: pointer; }
    .template-option.active { border-color: var(--brand); background: var(--soft); color: #B42318; font-weight: 600; }
    .actions { margin-top: 14px; display: flex; justify-content: space-between; gap: 10px; }
    .btn { border: 1px solid var(--line); background: white; color: #344054; border-radius: 8px; padding: 9px 14px; cursor: pointer; font-weight: 600; }
    .btn.primary { background: var(--brand); border-color: var(--brand); color: white; }
    .btn:disabled { opacity: 0.45; cursor: not-allowed; }
    .dropzone { margin-top: 14px; border: 1px solid var(--brand); border-radius: 12px; background: var(--soft); padding: 18px; text-align: center; }
    .dropzone.dragover { outline: 2px dashed var(--brand); outline-offset: -4px; }
    .drop-title { color: #B42318; font-size: 18px; font-weight: 600; }
    .drop-types { margin-top: 6px; color: #912018; }
    .drop-file { margin-top: 8px; color: var(--muted); font-size: 13px; }
    .hidden { display: none; }
    .tabs { margin-top: 12px; display: flex; gap: 8px; }
    .tab-btn { border: 1px solid var(--line); border-radius: 999px; background: white; color: #344054; padding: 7px 13px; font-size: 12px; font-weight: 600; cursor: pointer; }
    .tab-btn.active { background: var(--brand); color: white; border-color: var(--brand); }
    .panel { margin-top: 10px; border: 1px solid #FDA29B; border-radius: 12px; background: #FEF3F2; padding: 12px; }
    .panel.ok { border-color: #ABEFC6; background: #ECFDF3; }
    .panel.warn { border-color: #FECDCA; background: #FFF4ED; }
    table { width: 100%; border-collapse: separate; border-spacing: 0 6px; margin-top: 8px; font-size: 12px; }
    thead th { text-align: left; background: #F9FAFB; border: 1px solid #FECACA; padding: 7px 8px; color: #344054; }
    tbody td { background: white; border: 1px solid #FECACA; padding: 6px 8px; }
    .field-error { color: #B42318; font-weight: 600; }
    .row-context { font-size: 11px; color: #475467; line-height: 1.35; }
    .inline-input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; font-size: 12px; }
    select.inline-input { appearance: auto; background: #fff; cursor: pointer; }
    select.inline-input:disabled { background: #F2F4F7; color: #98A2B3; cursor: not-allowed; }
    .summary-line { margin-top: 8px; color: #912018; font-size: 12px; }
    .note { margin-top: 8px; color: #667085; font-size: 13px; }
    .findings { margin-top: 8px; padding: 10px 12px; border: 1px solid #FECACA; border-radius: 8px; background: #FFFFFF; overflow: hidden; }
    .findings-title { font-size: 13px; font-weight: 700; color: #912018; margin-bottom: 6px; }
    .findings-scroll { width: 100%; overflow-x: auto; overflow-y: hidden; padding-bottom: 2px; }
    .findings-grid { display: grid; grid-template-columns: max-content repeat(var(--findings-col-count, 1), max-content); gap: 6px; width: max-content; min-width: 100%; }
    .findings-cell { border: 1px solid #FECACA; border-radius: 6px; background: #fff; padding: 6px 8px; font-size: 11px; color: #7A271A; width: fit-content; max-width: 320px; }
    .findings-cell.header { background: #F9FAFB; color: #344054; font-weight: 600; }
    .findings-cell.rowlabel { background: #F9FAFB; color: #344054; font-weight: 600; }
    .findings-cell.muted { color: #98A2B3; }
    .findings-rule { font-weight: 600; color: #B42318; margin-bottom: 2px; }
    .findings-meta { color: #7A271A; margin-bottom: 4px; }
    .findings-detail-btn { border: 1px solid #DF3346; background: #FFF1F3; color: #B42318; border-radius: 6px; font-size: 10px; font-weight: 600; padding: 3px 6px; cursor: pointer; }
    .findings-detail { margin-top: 8px; border: 1px solid #FECACA; border-radius: 6px; background: #F9FAFB; padding: 8px; font-size: 11px; color: #7A271A; }
    .findings-detail-title { color: #912018; font-weight: 700; margin-bottom: 4px; }
    .findings-actions { margin-top: 6px; display: flex; gap: 6px; }
    .findings-action-btn { border: 1px solid #D0D5DD; background: #fff; color: #344054; border-radius: 6px; font-size: 10px; font-weight: 600; padding: 4px 8px; cursor: pointer; }
    .findings-action-btn.primary { border-color: #DF3346; background: #FFF1F3; color: #B42318; }
    .result-top { margin-top: 10px; display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 10px; align-items: stretch; }
    .kpi-board { margin-top: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }
    .kpi-card { border: 1px solid #FECACA; border-radius: 8px; background: #fff; padding: 8px; }
    .kpi-label { font-size: 10px; color: #667085; text-transform: uppercase; letter-spacing: .04em; }
    .kpi-value { margin-top: 2px; font-size: 18px; font-weight: 700; color: #912018; }
    .kpi-sub { margin-top: 2px; font-size: 10px; color: #7A271A; }
    .csv-context-frame { border: 1px solid #FECACA; border-radius: 10px; background: #fff; padding: 10px; font-size: 12px; color: #7A271A; }
    .csv-context-title { font-size: 11px; font-weight: 700; color: #912018; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }
    .csv-context-row { display: flex; justify-content: space-between; gap: 8px; padding: 2px 0; }
    .csv-context-row strong { color: #B42318; }
    @media (max-width: 1100px) {
      .result-top { grid-template-columns: 1fr; }
    }
    .dup-check { margin-top: 8px; border: 1px solid #FECACA; border-radius: 8px; background: #FFF7F7; padding: 8px 10px; font-size: 11px; color: #7A271A; }
    .dup-check-title { font-weight: 700; color: #912018; margin-bottom: 4px; }
    .dup-check.ok { border-color: #ABEFC6; background: #ECFDF3; color: #067647; }
    .findings-modal { position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45); display: flex; align-items: center; justify-content: center; z-index: 50; }
    .findings-modal.hidden { display: none; }
    .findings-modal-card { width: min(680px, calc(100vw - 32px)); max-height: calc(100vh - 32px); overflow: auto; border: 1px solid #FECACA; border-radius: 12px; background: #fff; padding: 14px; box-shadow: 0 12px 28px rgba(16, 24, 40, 0.2); }
    .findings-modal-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
    .findings-modal-close { border: 1px solid #D0D5DD; background: #fff; color: #344054; border-radius: 8px; padding: 4px 8px; cursor: pointer; font-size: 11px; font-weight: 600; }
  </style>
</head>
<body>
  <div class=\"topbar\">
    <div class=\"brand\">Excelencia OTC</div>
    <div class=\"admin\">Admin General</div>
  </div>

  <div class=\"page\">
    <h1>Validador EOP · Wizard simple</h1>
    <div class=\"steps\">
      <div id=\"step-pill-1\" class=\"pill active\">1. Plantilla + Carga</div>
      <div id=\"step-pill-2\" class=\"pill\">2. Resultado</div>
    </div>

    <div id=\"step-1\" class=\"card\">
      <div id=\"step1-title\" style=\"font-size: 24px; font-weight: 600;\">Paso 1: Elige la plantilla y carga el archivo</div>
      <div class="subtitle">El sistema recibe cualquier formato y lo convierte a CSV para validar</div>
      <div class=\"template-list\">
          <div class="template-option" data-template="tecnicos" onclick="setTemplate('tecnicos')">Plantilla Técnicos (recomendada)</div>
          <div class="template-option" data-template="usuarios" onclick="setTemplate('usuarios')">Plantilla Usuarios</div>
          <div class="template-option" data-template="plan_padrino" onclick="setTemplate('plan_padrino')">Plantilla Plan Padrino</div>
      </div>
      <div id=\"dropzone\" class=\"dropzone\">
        <div class=\"drop-title\">Arrastra y suelta tu archivo aquí</div>
        <div class=\"drop-types\">CSV, XLS, XLSX, JSON</div>
        <div style=\"margin: 8px 0 10px; color: #667085;\">o</div>
        <button id=\"pick-file\" class=\"btn\" type=\"button\">Seleccionar archivo</button>
        <input id=\"source-file\" type=\"file\" accept=\".csv,.txt,.json,.xlsx,.xls,.xlsm,.xltx,.xltm\" class=\"hidden\" />
        <div id=\"file-label\" class=\"drop-file\">Sin archivo cargado</div>
      </div>
      <div class=\"note\">Debes seleccionar una plantilla y cargar un archivo para continuar.</div>
      <div class=\"actions\" style=\"justify-content: end;\">
        <button id=\"validate-btn\" class=\"btn primary\" disabled>Validar y ver resumen</button>
      </div>
      <div id=\"api-error\" class=\"summary-line hidden\"></div>
    </div>

    <div id=\"step-3\" class=\"card hidden\">
      <div id=\"step3-title\" style=\"font-size: 24px; font-weight: 600;\">Paso 2: Resultado de validación · Plantilla: Técnicos</div>
      <div class="result-top">
        <div id="manual-kpi-board" class="kpi-board"></div>
        <div id="csv-context-frame" class="csv-context-frame"></div>
      </div>
      <div class=\"tabs\">
        <button class=\"tab-btn\" data-tab=\"A\">A. Archivo OK</button>
        <button class=\"tab-btn\" data-tab=\"B\">B. Corrección automática</button>
        <button class=\"tab-btn active\" data-tab=\"C\">C. Corrección manual</button>
      </div>

      <div id=\"panel-a\" class=\"panel ok hidden\">
        <div style=\"font-weight: 600; color: #027A48;\">Archivo validado sin errores críticos.</div>
        <div style=\"margin-top: 4px; color: #067647;\">Puedes descargar el CSV corregido final.</div>
      </div>

      <div id=\"panel-b\" class=\"panel warn hidden\">
        <div style=\"font-weight: 600; color: #B42318;\">Se aplicaron correcciones automáticas seguras.</div>
        <div id=\"panel-b-text\" style=\"margin-top: 4px; color: #912018;\">Listo para descargar CSV.</div>
      </div>

      <div id=\"panel-c\" class=\"panel\">
        <div style=\"font-weight: 600; color: #B42318;\">Resultado C: corrige errores uno a uno</div>
        <div id="manual-dup-check" class="dup-check hidden"></div>
        <div id="manual-findings" class="findings hidden">
          <div class="findings-title">Resumen de hallazgos</div>
          <div class="findings-scroll">
            <div id="manual-findings-matrix" class="findings-grid"></div>
          </div>
        </div>
        <div id="manual-findings-modal" class="findings-modal hidden" role="dialog" aria-modal="true" aria-labelledby="manual-findings-modal-title">
          <div class="findings-modal-card">
            <div class="findings-modal-head">
              <div id="manual-findings-modal-title" class="findings-detail-title">Detalle de hallazgo</div>
              <button id="manual-findings-close" type="button" class="findings-modal-close">Cerrar</button>
            </div>
            <div id="manual-findings-detail" class="findings-detail"></div>
          </div>
        </div>
        <div style="margin-top: 8px; font-size: 12px; font-weight: 700; color: #912018;">Opciones de corrección</div>
        <table>
          <thead>
            <tr>
              <th style=\"width: 70px;\">Fila</th>
              <th style=\"width: 150px;\">Campo</th>
              <th style=\"width: 280px;\">Contexto de registro</th>
              <th style=\"width: 180px;\">Valor actual</th>
              <th>Corrección sugerida / acción</th>
              <th style=\"width: 90px;\">Aplicar</th>
            </tr>
          </thead>
          <tbody id=\"manual-table-body\"></tbody>
        </table>
        <div id=\"manual-summary\" class=\"summary-line\">Se muestra una fila por cada error detectado en el validador.</div>
        <div class=\"actions\" style=\"justify-content: end; margin-top: 8px;\">
          <button id=\"apply-all\" class=\"btn\">Aplicar todas y regenerar CSV</button>
        </div>
      </div>

      <div class=\"actions\" style=\"margin-top: 12px;\">
        <button id=\"back-to-1\" class=\"btn\">Volver</button>
        <button id=\"download-final\" class=\"btn primary\" onclick=\"window.__downloadCsv && window.__downloadCsv()\">Descargar CSV corregido</button>
      </div>
    </div>
  </div>

  <script>
    const templateLabels = {
      tecnicos: 'Técnicos',
      usuarios: 'Usuarios',
      plan_padrino: 'Plan Padrino',
    };

    const state = {
      step: 1,
      template: null,
      sourceFile: null,
      validation: null,
      correctionOptions: {},
      correlationMaps: {},
      headers: [],
      rows: [],
      delimiter: ',',
      manualErrors: [],
      correctedCsv: '',
      suggestedDeletionRows: [],
      correctedRows: [],
      initialErrorCount: 0,
      originalRowsCount: 0,
      pendingModalRevalidation: false,
      revalidating: false,
    };

    function markRowsAsCorrected(csvRowNumbers) {
      if (!Array.isArray(csvRowNumbers) || !csvRowNumbers.length) return;
      const merged = new Set([...(state.correctedRows || []), ...csvRowNumbers.filter((n) => Number.isInteger(n) && n > 1)]);
      state.correctedRows = Array.from(merged).sort((a, b) => a - b);
      updateCorrectedRowsSummaryCounter();
    }

    function updateCorrectedRowsSummaryCounter() {
      const correctedCountEl = document.getElementById('csv-corrected-count');
      if (!correctedCountEl) return;
      const originalRows = Math.max(Number(state.originalRowsCount || 0), Array.isArray(state.rows) ? state.rows.length : 0);
      const correctedRowsCount = Math.min(Array.isArray(state.correctedRows) ? state.correctedRows.length : 0, originalRows);
      correctedCountEl.textContent = String(correctedRowsCount);
    }

    function renderCsvContextSummary() {
      const csvContextFrame = document.getElementById('csv-context-frame');
      if (!csvContextFrame) return;

      const totalRows = Array.isArray(state.rows) ? state.rows.length : 0;
      const totalColumns = Array.isArray(state.headers) ? state.headers.length : 0;
      const originalRows = Math.max(Number(state.originalRowsCount || 0), totalRows);
      const deletedRows = Math.max(originalRows - totalRows, 0);
      const correctedRows = Math.min(Array.isArray(state.correctedRows) ? state.correctedRows.length : 0, originalRows);

      csvContextFrame.innerHTML = `
        <div class="csv-context-title">Resumen CSV</div>
        <div class="csv-context-row"><span>Filas originales</span><strong>${originalRows}</strong></div>
        <div class="csv-context-row"><span>Filas eliminadas</span><strong>${deletedRows}</strong></div>
        <div class="csv-context-row"><span>Filas corregidas</span><strong id="csv-corrected-count">${correctedRows}</strong></div>
        <div class="csv-context-row"><span>Columnas</span><strong>${totalColumns}</strong></div>
      `;
    }

    function setStep(step) {
      state.step = step;
      document.getElementById('step-1').classList.toggle('hidden', step !== 1);
      document.getElementById('step-3').classList.toggle('hidden', step !== 2);

      for (let i = 1; i <= 2; i++) {
        document.getElementById(`step-pill-${i}`).classList.toggle('active', i === step);
      }
    }

    function updateValidateButtonState() {
      const canContinue = Boolean(state.template) && Boolean(state.sourceFile);
      document.getElementById('validate-btn').disabled = !canContinue;
    }

    function setTemplate(template) {
      state.template = template;
      document.querySelectorAll('.template-option').forEach((el) => {
        el.classList.toggle('active', el.dataset.template === template);
      });
      const label = templateLabels[template] || template;
      document.getElementById('step1-title').textContent = `Paso 1: Elige la plantilla y carga el archivo · Plantilla: ${label}`;
      document.getElementById('step3-title').textContent = `Paso 2: Resultado de validación · Plantilla: ${label}`;
      updateValidateButtonState();
    }

    window.setTemplate = setTemplate;

    function setSourceFile(file) {
      state.sourceFile = file;
      document.getElementById('file-label').textContent = file ? `Archivo cargado: ${file.name}` : 'Sin archivo cargado';
      updateValidateButtonState();
      document.getElementById('api-error').classList.add('hidden');
      document.getElementById('api-error').textContent = '';
    }

    function parseCsv(text, delimiter) {
      const rows = [];
      let row = [];
      let value = '';
      let quoted = false;

      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        const next = text[i + 1];
        if (ch === '"') {
          if (quoted && next === '"') {
            value += '"';
            i++;
          } else {
            quoted = !quoted;
          }
        } else if (ch === delimiter && !quoted) {
          row.push(value);
          value = '';
        } else if ((ch === '\\n' || ch === '\\r') && !quoted) {
          if (ch === '\\r' && next === '\\n') i++;
          row.push(value);
          rows.push(row);
          row = [];
          value = '';
        } else {
          value += ch;
        }
      }

      if (value.length > 0 || row.length > 0) {
        row.push(value);
        rows.push(row);
      }

      const headers = (rows.shift() || []).map((h) => (h || '').trim());
      const objects = rows
        .filter((values) => values.some((cell) => String(cell || '').trim() !== ''))
        .map((values) => {
          const obj = {};
          headers.forEach((header, index) => {
            obj[header] = values[index] ?? '';
          });
          return obj;
        });

      return { headers, rows: objects };
    }

    function escapeCsv(value, delimiter) {
      const text = String(value ?? '');
      if (text.includes('"') || text.includes('\\n') || text.includes('\\r') || text.includes(delimiter)) {
        return '"' + text.replace(/"/g, '""') + '"';
      }
      return text;
    }

    function buildCsv(headers, rows, delimiter) {
      const lines = [];
      lines.push(headers.map((header) => escapeCsv(header, delimiter)).join(delimiter));
      for (const row of rows) {
        lines.push(headers.map((header) => escapeCsv(row[header] ?? '', delimiter)).join(delimiter));
      }
      return lines.join('\\n');
    }

    function applyValidationPayload(payload, resetProgress = false) {
      state.validation = payload;
      state.correctionOptions = payload.correction_options || {};
      state.correlationMaps = payload.correlation_maps || {};
      state.delimiter = payload.summary.delimiter || ',';
      const parsed = parseCsv(payload.corrected_csv || '', state.delimiter);
      state.headers = parsed.headers;
      state.rows = parsed.rows;
      state.correctedCsv = payload.corrected_csv || '';

      if (resetProgress) {
        state.initialErrorCount = Math.max(payload.summary.error_count || 0, 0);
        state.originalRowsCount = Math.max(Number(payload.summary.total_rows || 0), parsed.rows.length || 0);
        state.suggestedDeletionRows = [];
        state.correctedRows = [];
        updateCorrectedRowsSummaryCounter();
      }

      renderCsvContextSummary();

      const errors = (payload.issues || []).filter((issue) => issue.severity === 'error' && issue.row > 1);
      state.manualErrors = errors
        .map((issue) => ({
          row: issue.row,
          field: issue.field,
          current: issue.current_value ?? '',
          proposed: issue.suggested_value ?? issue.current_value ?? '',
        }))
        .sort((a, b) => a.row - b.row || String(a.field).localeCompare(String(b.field)));

      document.getElementById('panel-b-text').textContent =
        `Correcciones automáticas aplicadas: ${payload.summary.correction_count}.`;
    }

    async function revalidateCurrentCsv() {
      if (state.revalidating || !state.template || !state.correctedCsv) {
        return;
      }

      state.revalidating = true;
      try {
        const res = await fetch('/api/revalidate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ template: state.template, corrected_csv: state.correctedCsv }),
        });

        const payload = await res.json();
        if (!res.ok) {
          document.getElementById('api-error').classList.remove('hidden');
          document.getElementById('api-error').textContent = payload.detail || 'No fue posible revalidar el archivo actualizado.';
          return;
        }

        applyValidationPayload(payload, false);
        renderManualTable();
        renderManualFindings();
      } finally {
        state.revalidating = false;
      }
    }

    function enforceTecnicosRowCorrelation(rowData) {
      if (!rowData || state.template !== 'tecnicos') {
        return;
      }

      const city = rowData['ciudad'] || '';
      const base = rowData['base_operativa'] || '';

      const mappedBase = findMappedValue(state.correlationMaps.city_to_base, city);
      if (mappedBase) {
        rowData['base_operativa'] = String(mappedBase);
        return;
      }

      const mappedCities = findMappedValue(state.correlationMaps.base_to_cities, base);
      if (Array.isArray(mappedCities) && mappedCities.length) {
        const currentCityNormalized = normalizeCatalogValue(city);
        const validCity = mappedCities.find((value) => normalizeCatalogValue(value) === currentCityNormalized);
        rowData['ciudad'] = validCity ? String(validCity) : String(mappedCities[0]);
      }
    }

    async function applyCorrection(index, skipRevalidate = false) {
      const item = state.manualErrors[index];
      if (!item) return;
      const targetRow = item.row - 2;
      if (targetRow < 0 || targetRow >= state.rows.length) return;

      state.rows[targetRow][item.field] = item.proposed;
      enforceTecnicosRowCorrelation(state.rows[targetRow]);
      item.applied = true;
      markRowsAsCorrected([item.row]);
      state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
      renderManualTable();
      if (!skipRevalidate) {
        await revalidateCurrentCsv();
      }
    }

    async function applyPairCorrection(rowNumber, cityValue, baseValue, skipRevalidate = false) {
      const targetRow = rowNumber - 2;
      if (targetRow < 0 || targetRow >= state.rows.length) return;

      const rowData = state.rows[targetRow];
      rowData['ciudad'] = cityValue || rowData['ciudad'] || '';
      rowData['base_operativa'] = baseValue || rowData['base_operativa'] || '';
      enforceTecnicosRowCorrelation(rowData);

      const cityError = findManualErrorByRowField(rowNumber, 'ciudad');
      if (cityError) {
        cityError.proposed = rowData['ciudad'] || cityValue || '';
        cityError.applied = true;
      }

      const baseError = findManualErrorByRowField(rowNumber, 'base_operativa');
      if (baseError) {
        baseError.proposed = rowData['base_operativa'] || baseValue || '';
        baseError.applied = true;
      }

      markRowsAsCorrected([rowNumber]);
      state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
      renderManualTable();
      if (!skipRevalidate) {
        await revalidateCurrentCsv();
      }
    }

    async function applyAllCorrections() {
      const processedPairRows = new Set();
      state.manualErrors.forEach((item, index) => {
        if (state.template === 'tecnicos' && isCityBasePairField(item.field)) {
          if (processedPairRows.has(item.row)) {
            return;
          }

          const cityError = findManualErrorByRowField(item.row, 'ciudad');
          const baseError = findManualErrorByRowField(item.row, 'base_operativa');
          applyPairCorrection(item.row, cityError?.proposed || '', baseError?.proposed || '', true);
          processedPairRows.add(item.row);
          return;
        }

        applyCorrection(index, true);
      });

      state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
      await revalidateCurrentCsv();
    }

    function normalizeFieldKey(field) {
      return String(field || '')
        .toLowerCase()
        .replace(/[()]/g, '')
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
    }

    function isManualTextEditableField(field) {
      const key = normalizeFieldKey(field);
      return ['correo', 'email', 'celular', 'telefono'].includes(key);
    }

    function normalizeCatalogValue(value) {
      return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toUpperCase()
        .trim()
        .replace(/\\s+/g, ' ');
    }

    function findMappedValue(mapObj, keyValue) {
      if (!mapObj || typeof mapObj !== 'object') return null;
      const target = normalizeCatalogValue(keyValue);
      if (!target) return null;
      for (const [key, value] of Object.entries(mapObj)) {
        if (normalizeCatalogValue(key) === target) {
          return value;
        }
      }
      return null;
    }

    function isCityField(field) {
      return normalizeFieldKey(field) === 'ciudad';
    }

    function isBaseField(field) {
      return normalizeFieldKey(field) === 'base_operativa';
    }

    function isCityBasePairField(field) {
      return isCityField(field) || isBaseField(field);
    }

    function findManualErrorByRowField(rowNumber, normalizedField) {
      return state.manualErrors.find(
        (entry) => entry.row === rowNumber && normalizeFieldKey(entry.field) === normalizedField
      ) || null;
    }

    function uniqueValues(values) {
      const result = [];
      const seen = new Set();

      values.forEach((value) => {
        const text = String(value || '').trim();
        if (!text) return;
        const key = normalizeCatalogValue(text);
        if (seen.has(key)) return;
        seen.add(key);
        result.push(text);
      });

      return result;
    }

    function getCityOptionsForRow(rowData) {
      const catalogCities = getOptionsForField('ciudad');
      const mapCities = Object.keys(state.correlationMaps?.city_to_base || {});
      const currentCity = rowData?.['ciudad'] || '';
      return uniqueValues([...catalogCities, ...mapCities, currentCity]);
    }

    function getBaseOptionsForCity(cityValue, rowData) {
      const cityToBase = state.correlationMaps?.city_to_base || {};
      const directBase = findMappedValue(cityToBase, cityValue);
      if (directBase) {
        return uniqueValues([String(directBase), rowData?.['base_operativa'] || '']);
      }

      const basesFromReverseMap = [];
      const normalizedCity = normalizeCatalogValue(cityValue);
      Object.entries(state.correlationMaps?.base_to_cities || {}).forEach(([base, cities]) => {
        if (!Array.isArray(cities)) return;
        const hasCity = cities.some((entry) => normalizeCatalogValue(entry) === normalizedCity);
        if (hasCity) {
          basesFromReverseMap.push(String(base));
        }
      });

      const catalogBases = getOptionsForField('base_operativa');
      return uniqueValues([...basesFromReverseMap, ...catalogBases, rowData?.['base_operativa'] || '']);
    }

    function getCorrelatedOptions(field, rowData) {
      const fieldKey = normalizeFieldKey(field);
      if (!rowData || typeof rowData !== 'object') return [];

      if (fieldKey === 'base_operativa') {
        const city = rowData['ciudad'] || '';
        const mappedBase = findMappedValue(state.correlationMaps.city_to_base, city);
        return mappedBase ? [String(mappedBase)] : [];
      }

      if (fieldKey === 'ciudad') {
        const base = rowData['base_operativa'] || '';
        const mappedCities = findMappedValue(state.correlationMaps.base_to_cities, base);
        if (Array.isArray(mappedCities) && mappedCities.length) {
          return mappedCities.map((value) => String(value));
        }
      }

      return [];
    }

    function getOptionsForField(field) {
      const direct = state.correctionOptions[field];
      if (Array.isArray(direct) && direct.length > 0) {
        return Array.from(new Set(direct.map((value) => String(value))));
      }

      const normalizedTarget = normalizeFieldKey(field);
      for (const [key, values] of Object.entries(state.correctionOptions || {})) {
        if (normalizeFieldKey(key) === normalizedTarget && Array.isArray(values) && values.length > 0) {
          return Array.from(new Set(values.map((value) => String(value))));
        }
      }

      return [];
    }

    function escapeCellHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function buildRowContextHtml(rowData, focusField) {
      if (!rowData || typeof rowData !== 'object') {
        return '<span class="row-context">Sin contexto adicional</span>';
      }

      const preferredKeys = [
        'nombre_completo',
        'nombre',
        'tecnico',
        'usuario',
        'documento',
        'cedula',
        'identificacion',
        'correo',
        'email',
        'telefono',
        'celular',
        'cargo',
        'ciudad',
        'base_operativa',
      ];

      const focusedKey = normalizeFieldKey(focusField);
      const entries = Object.entries(rowData)
        .map(([key, value]) => ({
          key,
          normalized: normalizeFieldKey(key),
          value: String(value ?? '').trim(),
        }))
        .filter((entry) => entry.value)
        .filter((entry) => !focusedKey || entry.normalized !== focusedKey)
        .sort((a, b) => {
          const aPriority = preferredKeys.indexOf(a.normalized);
          const bPriority = preferredKeys.indexOf(b.normalized);
          const aScore = aPriority === -1 ? 999 : aPriority;
          const bScore = bPriority === -1 ? 999 : bPriority;
          if (aScore !== bScore) return aScore - bScore;
          return a.key.localeCompare(b.key);
        })
        .slice(0, 4);

      if (!entries.length) {
        return '<span class="row-context">Sin contexto adicional</span>';
      }

      return `<div class="row-context">${entries
        .map((entry) => `<div><strong>${escapeCellHtml(entry.key)}:</strong> ${escapeCellHtml(entry.value)}</div>`)
        .join('')}</div>`;
    }

    function renderManualTable() {
      const body = document.getElementById('manual-table-body');
      body.innerHTML = '';
      const errors = state.manualErrors;
      const renderedPairRows = new Set();

      errors.forEach((item, index) => {
        const targetRow = item.row - 2;
        const rowData = targetRow >= 0 && targetRow < state.rows.length ? state.rows[targetRow] : {};

        if (state.template === 'tecnicos' && isCityBasePairField(item.field)) {
          if (renderedPairRows.has(item.row)) {
            return;
          }

          renderedPairRows.add(item.row);
          const cityError = findManualErrorByRowField(item.row, 'ciudad');
          const baseError = findManualErrorByRowField(item.row, 'base_operativa');

          const cityOptions = getCityOptionsForRow(rowData);
          const preferredCity = String(cityError?.proposed || rowData?.['ciudad'] || '').trim();
          const selectedCity = cityOptions.includes(preferredCity) ? preferredCity : '';

          const baseOptions = selectedCity ? getBaseOptionsForCity(selectedCity, rowData) : [];
          const preferredBase = String(baseError?.proposed || rowData?.['base_operativa'] || '').trim();
          const selectedBase = baseOptions.includes(preferredBase) ? preferredBase : '';

          if (cityError) cityError.proposed = selectedCity;
          if (baseError) baseError.proposed = selectedBase;

          const cityOptionsHtml = [`<option value="">Selecciona ciudad</option>`, ...cityOptions]
            .map((option) => {
              const selected = option === selectedCity ? ' selected' : '';
              const label = option || 'Selecciona ciudad';
              return `<option value="${option.replace(/"/g, '&quot;')}"${selected}>${label}</option>`;
            })
            .join('');

          const baseOptionsHtml = [`<option value="">${selectedCity ? 'Selecciona base operativa' : 'Selecciona ciudad primero'}</option>`, ...baseOptions]
            .map((option) => {
              const selected = option === selectedBase ? ' selected' : '';
              const label = option || (selectedCity ? 'Selecciona base operativa' : 'Selecciona ciudad primero');
              return `<option value="${option.replace(/"/g, '&quot;')}"${selected}>${label}</option>`;
            })
            .join('');

          const currentCity = rowData?.['ciudad'] || cityError?.current || '';
          const currentBase = rowData?.['base_operativa'] || baseError?.current || '';
          const contextHtml = buildRowContextHtml(rowData, '');

          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${item.row}</td>
            <td>ciudad + base_operativa</td>
            <td>${contextHtml}</td>
            <td class="field-error">${currentCity || '(vacío)'} | ${currentBase || '(vacío)'}</td>
            <td>
              <div style="display:flex; flex-direction:column; gap:6px;">
                <select class="inline-input" data-pair-city="${item.row}">${cityOptionsHtml}</select>
                <select class="inline-input" data-pair-base="${item.row}" ${selectedCity ? '' : 'disabled'}>${baseOptionsHtml}</select>
              </div>
            </td>
            <td><button class="btn" data-apply-pair="${item.row}" ${selectedCity && selectedBase ? '' : 'disabled'}>Aplicar par</button></td>
          `;
          body.appendChild(tr);
          return;
        }

        const correlatedOptions = getCorrelatedOptions(item.field, rowData);
        const catalogOptions = correlatedOptions.length ? correlatedOptions : getOptionsForField(item.field);
        const isTextEditableField = isManualTextEditableField(item.field);
        const hasCatalogOptions = catalogOptions.length > 0;
        if (isTextEditableField) {
          item.proposed = String(item.proposed || item.current || rowData?.[item.field] || '').trim();
        } else {
          const selectedValue = hasCatalogOptions
            ? (catalogOptions.includes(item.proposed) ? item.proposed : catalogOptions[0])
            : '';
          item.proposed = selectedValue;
        }

        const optionsHtml = (hasCatalogOptions ? catalogOptions : ['Sin opción de catálogo'])
          .map((opt) => {
            const textValue = String(opt);
            const value = hasCatalogOptions ? textValue : '';
            const selected = value === item.proposed ? ' selected' : '';
            return `<option value="${value.replace(/"/g, '&quot;')}"${selected}>${textValue}</option>`;
          })
          .join('');

        const actionControlHtml = isTextEditableField
          ? `<input type="text" class="inline-input" data-index-text="${index}" value="${escapeCellHtml(item.proposed)}" placeholder="Escribe el valor corregido" />`
          : `<select class="inline-input" data-index="${index}" ${hasCatalogOptions ? '' : 'disabled'}>${optionsHtml}</select>`;

        const canApply = isTextEditableField || hasCatalogOptions;

        const tr = document.createElement('tr');
        const contextHtml = buildRowContextHtml(rowData, item.field);
        tr.innerHTML = `
          <td>${item.row}</td>
          <td>${item.field}</td>
          <td>${contextHtml}</td>
          <td class="field-error">${item.current || ''}</td>
          <td>${actionControlHtml}</td>
          <td><button class="btn" data-apply="${index}" ${canApply ? '' : 'disabled'}>Aplicar</button></td>
        `;
        body.appendChild(tr);
      });

      body.querySelectorAll('select[data-index]').forEach((select) => {
        select.addEventListener('change', (event) => {
          const idx = Number(event.target.dataset.index);
          state.manualErrors[idx].proposed = event.target.value;
        });
      });

      body.querySelectorAll('input[data-index-text]').forEach((input) => {
        input.addEventListener('input', (event) => {
          const idx = Number(event.target.dataset.indexText);
          state.manualErrors[idx].proposed = event.target.value;
        });
      });

      body.querySelectorAll('select[data-pair-city]').forEach((select) => {
        select.addEventListener('change', (event) => {
          const rowNumber = Number(event.target.dataset.pairCity);
          const cityValue = event.target.value;
          const targetRow = rowNumber - 2;
          const rowData = targetRow >= 0 && targetRow < state.rows.length ? state.rows[targetRow] : {};
          const baseSelect = body.querySelector(`select[data-pair-base="${rowNumber}"]`);
          const baseOptions = getBaseOptionsForCity(cityValue, rowData);

          const cityError = findManualErrorByRowField(rowNumber, 'ciudad');
          if (cityError) {
            cityError.proposed = cityValue;
          }

          if (baseSelect) {
            const currentBase = baseSelect.value;
            baseSelect.disabled = !cityValue;
            baseSelect.innerHTML = [`<option value="">${cityValue ? 'Selecciona base operativa' : 'Selecciona ciudad primero'}</option>`, ...baseOptions]
              .map((option) => {
                const label = option || (cityValue ? 'Selecciona base operativa' : 'Selecciona ciudad primero');
                return `<option value="${option.replace(/"/g, '&quot;')}">${label}</option>`;
              })
              .join('');
            const nextBase = baseOptions.includes(currentBase) ? currentBase : (baseOptions[0] || '');
            baseSelect.value = nextBase;

            const baseError = findManualErrorByRowField(rowNumber, 'base_operativa');
            if (baseError) {
              baseError.proposed = nextBase;
            }

            const pairButton = body.querySelector(`button[data-apply-pair="${rowNumber}"]`);
            if (pairButton) {
              pairButton.disabled = !(cityValue && nextBase);
            }
          }
        });
      });

      body.querySelectorAll('select[data-pair-base]').forEach((select) => {
        select.addEventListener('change', (event) => {
          const rowNumber = Number(event.target.dataset.pairBase);
          const citySelect = body.querySelector(`select[data-pair-city="${rowNumber}"]`);
          const baseError = findManualErrorByRowField(rowNumber, 'base_operativa');
          if (baseError) {
            baseError.proposed = event.target.value;
          }

          const pairButton = body.querySelector(`button[data-apply-pair="${rowNumber}"]`);
          if (pairButton) {
            pairButton.disabled = !(citySelect?.value && event.target.value);
          }
        });
      });

      body.querySelectorAll('button[data-apply]').forEach((button) => {
        button.addEventListener('click', () => applyCorrection(Number(button.dataset.apply)));
      });

      body.querySelectorAll('button[data-apply-pair]').forEach((button) => {
        button.addEventListener('click', () => {
          const rowNumber = Number(button.dataset.applyPair);
          const citySelect = body.querySelector(`select[data-pair-city="${rowNumber}"]`);
          const baseSelect = body.querySelector(`select[data-pair-base="${rowNumber}"]`);
          applyPairCorrection(rowNumber, citySelect?.value || '', baseSelect?.value || '');
        });
      });

      document.getElementById('manual-summary').textContent =
        `Se muestran ${errors.length} filas de error con contexto del registro para facilitar la corrección.`;
    }

    function renderManualFindings() {
      const kpiBoard = document.getElementById('manual-kpi-board');
      const duplicateCheck = document.getElementById('manual-dup-check');
      const findingsContainer = document.getElementById('manual-findings');
      const findingsMatrix = document.getElementById('manual-findings-matrix');
      const findingsDetail = document.getElementById('manual-findings-detail');
      const findingsModal = document.getElementById('manual-findings-modal');
      const findingsModalClose = document.getElementById('manual-findings-close');
      findingsMatrix.innerHTML = '';
      findingsDetail.innerHTML = '';
      findingsModal.classList.add('hidden');

      function closeFindingsModal() {
        const shouldRevalidate = state.pendingModalRevalidation === true;
        state.pendingModalRevalidation = false;
        findingsModal.classList.add('hidden');
        findingsDetail.innerHTML = '';
        if (shouldRevalidate) {
          revalidateCurrentCsv();
        }
      }

      if (findingsModalClose) {
        findingsModalClose.onclick = closeFindingsModal;
      }

      findingsModal.onclick = (event) => {
        if (event.target === findingsModal) {
          closeFindingsModal();
        }
      };

      const allIssues = (state.validation?.issues || []).filter(
        (issue) => ['error', 'warning', 'suspicious'].includes(issue.severity)
      );
      const matrixIssues = allIssues.filter((issue) => issue.row > 1);
      const errors = matrixIssues.filter((issue) => issue.severity === 'error');
      const warnings = matrixIssues.filter((issue) => issue.severity === 'warning');
      const suspicious = matrixIssues.filter((issue) => issue.severity === 'suspicious');

      const externalDuplicateIssues = allIssues.filter((issue) => [
        'ALREADY_LOADED_DUPLICATE_ID',
        'ALREADY_LOADED_DUPLICATE_NAME_EMAIL',
        'ALREADY_LOADED_DUPLICATE_NAME_PHONE',
        'ALREADY_LOADED_USER_DUPLICATE_ID',
        'ALREADY_LOADED_USER_DUPLICATE_EMAIL',
      ].includes(String(issue.code || '').toUpperCase()));
      const snapshotIssue = allIssues.find((issue) => String(issue.code || '').toUpperCase() === 'EXTERNAL_TECHNICIANS_SNAPSHOT');

      const currentErrorCount = errors.length;
      const baselineErrors = Math.max(state.initialErrorCount || currentErrorCount, 0);
      const progress = baselineErrors > 0
        ? Math.round(((baselineErrors - Math.min(currentErrorCount, baselineErrors)) / baselineErrors) * 100)
        : 100;
      const totalRows = Array.isArray(state.rows) ? state.rows.length : 0;
      const totalColumns = Array.isArray(state.headers) ? state.headers.length : 0;
      const originalRows = Math.max(Number(state.originalRowsCount || 0), totalRows);
      const deletedRows = Math.max(originalRows - totalRows, 0);
      const rowsWithError = new Set(errors.map((issue) => issue.row)).size;
      const rowsWithWarning = new Set(warnings.map((issue) => issue.row)).size;
      const correctedRows = Math.min(Array.isArray(state.correctedRows) ? state.correctedRows.length : 0, originalRows);

      if (kpiBoard) {
        kpiBoard.innerHTML = `
          <div class="kpi-card">
            <div class="kpi-label">Porcentaje de corrección</div>
            <div class="kpi-value">${progress}%</div>
            <div class="kpi-sub">Base inicial: ${baselineErrors} errores</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Estructura del archivo</div>
            <div class="kpi-value">${totalRows}×${totalColumns}</div>
            <div class="kpi-sub">Filas de datos × columnas</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Hallazgos</div>
            <div class="kpi-value">${allIssues.length}</div>
            <div class="kpi-sub">Errores: ${errors.length} · Advertencias: ${warnings.length} · Sospechosos: ${suspicious.length}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Duplicados externos</div>
            <div class="kpi-value">${externalDuplicateIssues.length}</div>
            <div class="kpi-sub">Filas con advertencia: ${rowsWithWarning}</div>
          </div>
        `;
      }

      renderCsvContextSummary();

      if (snapshotIssue || externalDuplicateIssues.length) {
        const duplicatesById = externalDuplicateIssues.filter((issue) => ['ALREADY_LOADED_DUPLICATE_ID', 'ALREADY_LOADED_USER_DUPLICATE_ID'].includes(String(issue.code || '').toUpperCase())).length;
        const duplicatesByNameEmail = externalDuplicateIssues.filter((issue) => ['ALREADY_LOADED_DUPLICATE_NAME_EMAIL', 'ALREADY_LOADED_USER_DUPLICATE_EMAIL'].includes(String(issue.code || '').toUpperCase())).length;
        const duplicatesByNamePhone = externalDuplicateIssues.filter((issue) => String(issue.code || '').toUpperCase() === 'ALREADY_LOADED_DUPLICATE_NAME_PHONE').length;
        duplicateCheck.classList.remove('hidden');
        duplicateCheck.classList.toggle('ok', externalDuplicateIssues.length === 0);
        duplicateCheck.innerHTML = `
          <div class="dup-check-title">Validación de duplicidad contra registros ya cargados</div>
          <div>Posibles duplicados detectados: <strong>${externalDuplicateIssues.length}</strong> (Identificación: ${duplicatesById}, Nombre/Email: ${duplicatesByNameEmail}, Nombre/Teléfono: ${duplicatesByNamePhone})</div>
          ${snapshotIssue ? `<div style="margin-top:4px;">${escapeHtml(snapshotIssue.message || '')}</div>` : ''}
        `;
      } else {
        duplicateCheck.classList.add('hidden');
        duplicateCheck.classList.remove('ok');
        duplicateCheck.innerHTML = '';
      }

      if (!matrixIssues.length) {
        findingsContainer.classList.add('hidden');
        return;
      }

      function classifyIssue(issue) {
        const code = String(issue.code || '').toUpperCase();
        if (code.includes('INCONSISTENT')) return 'Inconsistencia';
        if (code.includes('INVALID') || code.includes('MISSING')) return 'No parametrizado';
        if (code.includes('AUTOCORRECTED')) return 'Autocorregido';
        return 'Otros';
      }

      function escapeHtml(value) {
        return String(value || '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      }

      function sanitizeFilename(value) {
        return String(value || 'detalle')
          .replace(/[^a-z0-9_.-]+/gi, '_')
          .replace(/_+/g, '_')
          .replace(/^_+|_+$/g, '');
      }

      function formatIssueValue(value) {
        const text = String(value ?? '').trim();
        return text ? text : '(vacío)';
      }

      function groupRowsByCurrentInvalidValue(entry) {
        const groups = new Map();
        (entry.rows || []).forEach((csvRowNumber) => {
          const rowIndex = csvRowNumber - 2;
          if (rowIndex < 0 || rowIndex >= state.rows.length) return;
          const currentValue = String(state.rows[rowIndex]?.[entry.field] ?? '');
          if (!groups.has(currentValue)) {
            groups.set(currentValue, { value: currentValue, rows: [] });
          }
          groups.get(currentValue).rows.push(csvRowNumber);
        });

        return Array.from(groups.values()).sort((a, b) => {
          if (b.rows.length !== a.rows.length) return b.rows.length - a.rows.length;
          return String(a.value).localeCompare(String(b.value));
        });
      }

      function downloadRuleDetailCsv(entry) {
        const csvRows = [['columna', 'codigo', 'mensaje', 'fila']];
        entry.rows.forEach((rowNumber) => {
          csvRows.push([entry.field, entry.code, entry.message, String(rowNumber)]);
        });
        const content = csvRows
          .map((row) => row.map((cell) => {
            const text = String(cell || '');
            return (text.includes(',') || text.includes('"') || text.includes('\\n'))
              ? `"${text.replace(/"/g, '""')}"`
              : text;
          }).join(','))
          .join('\\n');

        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${sanitizeFilename(entry.field)}_${sanitizeFilename(entry.code)}_detalle.csv`;
        anchor.click();
        URL.revokeObjectURL(url);
      }

      function isDeletionSuggestionCode(code) {
        return [
          'ALREADY_LOADED_DUPLICATE_ID',
          'ALREADY_LOADED_DUPLICATE_NAME_EMAIL',
          'ALREADY_LOADED_DUPLICATE_NAME_PHONE',
          'ALREADY_LOADED_USER_DUPLICATE_ID',
          'ALREADY_LOADED_USER_DUPLICATE_EMAIL',
          'DUPLICATE_IDENTIFIER',
        ].includes(String(code || '').toUpperCase());
      }

      const categories = ['Inconsistencia', 'No parametrizado', 'Autocorregido', 'Otros'];
      const fields = Array.from(new Set(matrixIssues.map((issue) => String(issue.field || '').trim()).filter(Boolean)))
        .sort((a, b) => a.localeCompare(b));
      findingsContainer.style.setProperty('--findings-col-count', String(Math.max(fields.length, 1)));

      const detailsMap = {};
      const matrix = {};

      fields.forEach((field) => {
        matrix[field] = {};
        categories.forEach((category) => {
          matrix[field][category] = [];
        });
      });

      const grouped = new Map();
      matrixIssues.forEach((issue) => {
        const field = String(issue.field || '').trim();
        if (!field) return;
        const category = classifyIssue(issue);
        const key = `${field}||${category}||${issue.code}||${issue.message}`;
        if (!grouped.has(key)) {
          grouped.set(key, {
            field,
            category,
            code: String(issue.code || ''),
            message: String(issue.message || ''),
            rows: new Set(),
          });
        }
        grouped.get(key).rows.add(issue.row);
      });

      grouped.forEach((entry) => {
        const rows = Array.from(entry.rows).sort((a, b) => a - b);
        entry.rows = rows;
        matrix[entry.field][entry.category].push(entry);
      });

      findingsMatrix.insertAdjacentHTML('beforeend', `<div class="findings-cell header">Tipo de hallazgo</div>`);
      fields.forEach((field) => {
        findingsMatrix.insertAdjacentHTML('beforeend', `<div class="findings-cell header">${escapeHtml(field)}</div>`);
      });

      categories.forEach((category) => {
        findingsMatrix.insertAdjacentHTML('beforeend', `<div class="findings-cell rowlabel">${escapeHtml(category)}</div>`);

        fields.forEach((field) => {
          const entries = matrix[field][category] || [];
          if (!entries.length) {
            findingsMatrix.insertAdjacentHTML('beforeend', `<div class="findings-cell muted">—</div>`);
            return;
          }

          const html = entries.map((entry, idx) => {
            const detailKey = `${field}__${category}__${idx}`;
            detailsMap[detailKey] = entry;
            return `
              <div class="findings-rule">${escapeHtml(entry.code)}</div>
              <div class="findings-meta">${escapeHtml(entry.message)} · ${entry.rows.length} filas</div>
              <button class="findings-detail-btn" data-findings-detail="${escapeHtml(detailKey)}">Ver detalle</button>
            `;
          }).join('<div style="height:6px"></div>');

          findingsMatrix.insertAdjacentHTML('beforeend', `<div class="findings-cell">${html}</div>`);
        });
      });

      findingsMatrix.querySelectorAll('button[data-findings-detail]').forEach((button) => {
        button.addEventListener('click', () => {
          const key = button.dataset.findingsDetail;
          const entry = detailsMap[key];
          if (!entry) return;
          const previewRows = entry.rows.slice(0, 20).join(', ');
          const remaining = entry.rows.length > 20 ? ` · +${entry.rows.length - 20} más` : '';
          const canSuggestDelete = isDeletionSuggestionCode(entry.code);
          const fieldOptions = getOptionsForField(entry.field);
          const isTextEditableField = isManualTextEditableField(entry.field);
          const canMacroCorrect = fieldOptions.length > 0 && entry.rows.length > 0;
          const canGroupedTextCorrect = isTextEditableField && entry.rows.length > 0;
          const canGroupedCorrection = canMacroCorrect || canGroupedTextCorrect;
          const invalidGroups = canGroupedCorrection ? groupRowsByCurrentInvalidValue(entry) : [];
          const macroOptionsHtml = fieldOptions
            .map((option) => `<option value="${escapeHtml(String(option))}">${escapeHtml(String(option))}</option>`)
            .join('');
          const groupedCorrectionHtml = canGroupedCorrection
            ? invalidGroups.map((group, idx) => {
              const groupRowsPreview = group.rows.slice(0, 12).join(', ');
              const groupRemaining = group.rows.length > 12 ? ` · +${group.rows.length - 12} más` : '';
              const groupInputControl = canMacroCorrect
                ? `<select data-findings-group-select="${idx}" class="inline-input" style="max-width:320px;">${macroOptionsHtml}</select>`
                : `<input type="text" data-findings-group-text="${idx}" class="inline-input" style="max-width:320px;" value="${escapeHtml(String(group.value || ''))}" placeholder="Escribe valor corregido" />`;
              return `
                <div data-findings-group-card="${idx}" style="border:1px solid #FECACA; border-radius:8px; padding:8px; background:#fff; margin-top:6px;">
                  <div style="font-weight:700; color:#912018;">Dato actual: ${escapeHtml(formatIssueValue(group.value))}</div>
                  <div style="font-size:11px; color:#7A271A; margin-top:2px;">${group.rows.length} filas · ${escapeHtml(groupRowsPreview)}${groupRemaining}</div>
                  <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin-top:6px;">
                    ${groupInputControl}
                    <button data-findings-group-apply="${idx}" class="findings-action-btn primary">Aplicar a ${group.rows.length} filas</button>
                  </div>
                </div>
              `;
            }).join('')
            : '';
          findingsDetail.innerHTML = `
            <div class="findings-detail-title">${escapeHtml(entry.field)} · ${escapeHtml(entry.code)}</div>
            <div>${escapeHtml(entry.message)}</div>
            <div style="margin-top:4px;"><strong>Filas:</strong> ${escapeHtml(previewRows)}${remaining}</div>
            ${canGroupedCorrection ? `
              <div style="margin-top:8px; border:1px solid #FECACA; border-radius:8px; padding:8px; background:#FFF7F7;">
                <div style="font-weight:700; color:#912018; margin-bottom:6px;">Corrección agrupada por dato errado</div>
                <div style="font-size:11px; color:#7A271A;">Selecciona el valor correcto por grupo y aplica uno a uno.</div>
                <div id="findings-grouped-wrapper">${groupedCorrectionHtml}</div>
              </div>
            ` : ''}
            <div class="findings-actions">
              <button id="findings-copy-btn" class="findings-action-btn">Copiar lista</button>
              <button id="findings-export-btn" class="findings-action-btn primary">Exportar CSV</button>
              ${canSuggestDelete ? '<button id="findings-suggest-delete-btn" class="findings-action-btn">Sugerir eliminación</button><button id="findings-apply-delete-btn" class="findings-action-btn primary">Eliminar filas sugeridas</button>' : ''}
            </div>
          `;
          findingsModal.classList.remove('hidden');

          const copyBtn = document.getElementById('findings-copy-btn');
          if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
              const text = `${entry.field} · ${entry.code}: ${entry.message}. Filas: ${entry.rows.join(', ')}`;
              try {
                await navigator.clipboard.writeText(text);
                copyBtn.textContent = 'Copiado';
                setTimeout(() => { copyBtn.textContent = 'Copiar lista'; }, 1200);
              } catch {
                copyBtn.textContent = 'No disponible';
                setTimeout(() => { copyBtn.textContent = 'Copiar lista'; }, 1200);
              }
            });
          }

          const exportBtn = document.getElementById('findings-export-btn');
          if (exportBtn) {
            exportBtn.addEventListener('click', () => downloadRuleDetailCsv(entry));
          }

          findingsDetail.querySelectorAll('button[data-findings-group-apply]').forEach((applyBtn) => {
            applyBtn.addEventListener('click', async () => {
              const groupIndex = Number(applyBtn.getAttribute('data-findings-group-apply'));
              const group = invalidGroups[groupIndex];
              const select = findingsDetail.querySelector(`select[data-findings-group-select="${groupIndex}"]`);
              const textInput = findingsDetail.querySelector(`input[data-findings-group-text="${groupIndex}"]`);
              const selected = canMacroCorrect ? (select?.value || '') : (textInput?.value || '');
              if (!group || !selected.trim()) return;

              group.rows.forEach((csvRowNumber) => {
                const rowIndex = csvRowNumber - 2;
                if (rowIndex < 0 || rowIndex >= state.rows.length) return;
                state.rows[rowIndex][entry.field] = selected;
                if (state.template === 'tecnicos') {
                  enforceTecnicosRowCorrelation(state.rows[rowIndex]);
                }
              });

              markRowsAsCorrected(group.rows);
              state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
              state.pendingModalRevalidation = true;

              const groupCard = applyBtn.closest('[data-findings-group-card]');
              if (groupCard) {
                groupCard.remove();
              }

              const groupedWrapper = document.getElementById('findings-grouped-wrapper');
              if (groupedWrapper && groupedWrapper.querySelectorAll('[data-findings-group-card]').length === 0) {
                groupedWrapper.innerHTML = '<div style="margin-top:6px; font-size:11px; color:#067647;">No quedan grupos pendientes para este hallazgo.</div>';
              }
            });
          });

          const suggestDeleteBtn = document.getElementById('findings-suggest-delete-btn');
          if (suggestDeleteBtn) {
            suggestDeleteBtn.addEventListener('click', async () => {
              state.suggestedDeletionRows = Array.from(new Set([...state.suggestedDeletionRows, ...entry.rows])).sort((a, b) => a - b);
              const rowsText = state.suggestedDeletionRows.join(', ');
              const advisory = `Filas sugeridas para eliminar del CSV (posibles duplicados ya cargados): ${rowsText}`;
              if (duplicateCheck && !duplicateCheck.classList.contains('hidden')) {
                duplicateCheck.innerHTML += `<div style="margin-top:4px;"><strong>Nota:</strong> ${escapeHtml(advisory)}</div>`;
              }
              try {
                await navigator.clipboard.writeText(advisory);
                suggestDeleteBtn.textContent = 'Sugerido + copiado';
              } catch {
                suggestDeleteBtn.textContent = 'Sugerido';
              }
              setTimeout(() => { suggestDeleteBtn.textContent = 'Sugerir eliminación'; }, 1500);
            });
          }

          const applyDeleteBtn = document.getElementById('findings-apply-delete-btn');
          if (applyDeleteBtn) {
            applyDeleteBtn.addEventListener('click', async () => {
              const rowsToDelete = Array.from(new Set(entry.rows)).sort((a, b) => b - a);
              if (!rowsToDelete.length) return;

              rowsToDelete.forEach((csvRowNumber) => {
                const rowIndex = csvRowNumber - 2;
                if (rowIndex >= 0 && rowIndex < state.rows.length) {
                  state.rows.splice(rowIndex, 1);
                }
              });

              state.suggestedDeletionRows = Array.from(new Set([...state.suggestedDeletionRows, ...entry.rows])).sort((a, b) => a - b);
              state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
              closeFindingsModal();
              await revalidateCurrentCsv();
            });
          }
        });
      });

      findingsContainer.classList.remove('hidden');
    }

    function setTab(tab) {
      document.querySelectorAll('.tab-btn').forEach((button) => {
        button.classList.toggle('active', button.dataset.tab === tab);
      });
      document.getElementById('panel-a').classList.toggle('hidden', tab !== 'A');
      document.getElementById('panel-b').classList.toggle('hidden', tab !== 'B');
      document.getElementById('panel-c').classList.toggle('hidden', tab !== 'C');
    }

    async function validateFile() {
      const template = state.template;
      if (!template || !state.sourceFile) return;
      setTemplate(template);

      const form = new FormData();
      form.append('template', template);
      form.append('csv_file', state.sourceFile);

      const res = await fetch('/api/validate', { method: 'POST', body: form });
      const payload = await res.json();
      if (!res.ok) {
        document.getElementById('api-error').classList.remove('hidden');
        document.getElementById('api-error').textContent = payload.detail || 'No fue posible validar el archivo.';
        return;
      }

      applyValidationPayload(payload, true);

      if (payload.summary.error_count === 0) {
        if (payload.summary.correction_count > 0) {
          setTab('B');
        } else {
          setTab('A');
        }
      } else {
        setTab('C');
      }

      renderManualTable();
      renderManualFindings();
      setStep(2);
    }

    function downloadCsv() {
      if (!state.correctedCsv) {
        return;
      }
      const blob = new Blob([state.correctedCsv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${state.template}_corregido.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    }

    const templateList = document.querySelector('.template-list');
    if (templateList) {
      templateList.addEventListener('click', (event) => {
        const option = event.target.closest('.template-option');
        if (!option) return;
        const template = option.dataset.template;
        if (!template) return;
        setTemplate(template);
      });
    }

    document.querySelectorAll('.template-option').forEach((option) => {
      option.addEventListener('click', () => setTemplate(option.dataset.template));
    });

    document.getElementById('back-to-1').addEventListener('click', () => setStep(1));

    document.getElementById('pick-file').addEventListener('click', () => {
      document.getElementById('source-file').click();
    });

    document.getElementById('source-file').addEventListener('change', (event) => {
      setSourceFile(event.target.files && event.target.files.length ? event.target.files[0] : null);
    });

    const dropzone = document.getElementById('dropzone');
    dropzone.addEventListener('dragover', (event) => {
      event.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });
    dropzone.addEventListener('drop', (event) => {
      event.preventDefault();
      dropzone.classList.remove('dragover');
      const files = event.dataTransfer.files;
      if (files && files.length) {
        setSourceFile(files[0]);
      }
    });

    document.getElementById('validate-btn').addEventListener('click', validateFile);
    document.getElementById('download-final').addEventListener('click', downloadCsv);
    document.getElementById('apply-all').addEventListener('click', applyAllCorrections);

    window.__applyCorrection = applyCorrection;
    window.__applyAllCorrections = applyAllCorrections;
    window.__downloadCsv = downloadCsv;

    document.querySelectorAll('.tab-btn').forEach((button) => {
      button.addEventListener('click', () => setTab(button.dataset.tab));
    });

    setTemplate('tecnicos');
    updateValidateButtonState();
    setTab('C');
  </script>
</body>
</html>
"""
