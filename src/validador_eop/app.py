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
    .inline-input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; font-size: 12px; }
    select.inline-input { appearance: auto; background: #fff; cursor: pointer; }
    select.inline-input:disabled { background: #F2F4F7; color: #98A2B3; cursor: not-allowed; }
    .summary-line { margin-top: 8px; color: #912018; font-size: 12px; }
    .note { margin-top: 8px; color: #667085; font-size: 13px; }
    .findings { margin-top: 8px; padding: 10px 12px; border: 1px solid #FECACA; border-radius: 8px; background: #FFFFFF; }
    .findings-title { font-size: 13px; font-weight: 700; color: #912018; margin-bottom: 6px; }
    .findings-list { margin: 0; padding-left: 18px; color: #7A271A; font-size: 12px; }
    .findings-list li { margin: 3px 0; }
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
      <div class=\"subtitle\">El sistema recibe cualquier formato y lo convierte a CSV para validar</div>
      <div class=\"template-list\">
        <div class=\"template-option\" data-template=\"tecnicos\">Plantilla Técnicos (recomendada)</div>
        <div class=\"template-option\" data-template=\"usuarios\">Plantilla Usuarios</div>
        <div class=\"template-option\" data-template=\"plan_padrino\">Plantilla Plan Padrino</div>
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
        <div id="manual-overview" class="summary-line"></div>
        <div id="manual-findings" class="findings hidden">
          <div class="findings-title">Resumen de hallazgos</div>
          <ul id="manual-findings-list" class="findings-list"></ul>
        </div>
        <div style="margin-top: 8px; font-size: 12px; font-weight: 700; color: #912018;">Opciones de corrección</div>
        <table>
          <thead>
            <tr>
              <th style=\"width: 70px;\">Fila</th>
              <th style=\"width: 150px;\">Campo</th>
              <th style=\"width: 180px;\">Valor actual</th>
              <th>Corrección sugerida / acción</th>
              <th style=\"width: 90px;\">Aplicar</th>
            </tr>
          </thead>
          <tbody id=\"manual-table-body\"></tbody>
        </table>
        <div id=\"manual-summary\" class=\"summary-line\">Se muestra una fila por cada error detectado en el validador.</div>
        <div class=\"actions\" style=\"justify-content: end; margin-top: 8px;\">
          <button id=\"apply-all\" class=\"btn\" onclick=\"window.__applyAllCorrections && window.__applyAllCorrections()\">Aplicar todas y regenerar CSV</button>
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
    };

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

    function applyCorrection(index) {
      const item = state.manualErrors[index];
      if (!item) return;
      const targetRow = item.row - 2;
      if (targetRow < 0 || targetRow >= state.rows.length) return;

      state.rows[targetRow][item.field] = item.proposed;
      enforceTecnicosRowCorrelation(state.rows[targetRow]);
      item.applied = true;
      state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
      renderManualTable();
    }

    function applyAllCorrections() {
      state.manualErrors.forEach((_, index) => {
        applyCorrection(index);
      });
      state.correctedCsv = buildCsv(state.headers, state.rows, state.delimiter);
    }

    function normalizeFieldKey(field) {
      return String(field || '')
        .toLowerCase()
        .replace(/[()]/g, '')
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
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

    function renderManualTable() {
      const body = document.getElementById('manual-table-body');
      body.innerHTML = '';
      const errors = state.manualErrors;

      errors.forEach((item, index) => {
        const targetRow = item.row - 2;
        const rowData = targetRow >= 0 && targetRow < state.rows.length ? state.rows[targetRow] : {};
        const correlatedOptions = getCorrelatedOptions(item.field, rowData);
        const catalogOptions = correlatedOptions.length ? correlatedOptions : getOptionsForField(item.field);
        const hasCatalogOptions = catalogOptions.length > 0;
        const selectedValue = hasCatalogOptions
          ? (catalogOptions.includes(item.proposed) ? item.proposed : catalogOptions[0])
          : '';
        item.proposed = selectedValue;

        const optionsHtml = (hasCatalogOptions ? catalogOptions : ['Sin opción de catálogo'])
          .map((opt) => {
            const textValue = String(opt);
            const value = hasCatalogOptions ? textValue : '';
            const selected = value === item.proposed ? ' selected' : '';
            return `<option value="${value.replace(/"/g, '&quot;')}"${selected}>${textValue}</option>`;
          })
          .join('');

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${item.row}</td>
          <td>${item.field}</td>
          <td class="field-error">${item.current || ''}</td>
          <td><select class="inline-input" data-index="${index}" ${hasCatalogOptions ? '' : 'disabled'}>${optionsHtml}</select></td>
          <td><button class="btn" data-apply="${index}" ${hasCatalogOptions ? '' : 'disabled'} onclick="window.__applyCorrection && window.__applyCorrection(${index})">Aplicar</button></td>
        `;
        body.appendChild(tr);
      });

      body.querySelectorAll('select[data-index]').forEach((select) => {
        select.addEventListener('change', (event) => {
          const idx = Number(event.target.dataset.index);
          state.manualErrors[idx].proposed = event.target.value;
        });
      });

      body.querySelectorAll('button[data-apply]').forEach((button) => {
        button.addEventListener('click', () => applyCorrection(Number(button.dataset.apply)));
      });

      document.getElementById('manual-summary').textContent =
        `Se muestran ${errors.length} filas de error (una por cada error detectado).`;
    }

    function renderManualFindings() {
      const overview = document.getElementById('manual-overview');
      const findingsContainer = document.getElementById('manual-findings');
      const findingsList = document.getElementById('manual-findings-list');
      findingsList.innerHTML = '';

      const allIssues = (state.validation?.issues || []).filter(
        (issue) => ['error', 'warning', 'suspicious'].includes(issue.severity) && issue.row > 1
      );
      const errors = allIssues.filter((issue) => issue.severity === 'error');
      const warnings = allIssues.filter((issue) => issue.severity === 'warning');
      const suspicious = allIssues.filter((issue) => issue.severity === 'suspicious');

      overview.textContent = `Hallazgos detectados: ${allIssues.length} · Errores: ${errors.length} · Advertencias: ${warnings.length} · Sospechosos: ${suspicious.length}`;

      const issues = allIssues;
      if (!issues.length) {
        findingsContainer.classList.add('hidden');
        return;
      }

      const grouped = new Map();
      issues.forEach((issue) => {
        const key = `${issue.field}||${issue.code}||${issue.message}`;
        if (!grouped.has(key)) {
          grouped.set(key, {
            field: issue.field,
            code: issue.code,
            message: issue.message,
            rows: new Set(),
          });
        }
        grouped.get(key).rows.add(issue.row);
      });

      Array.from(grouped.values())
        .sort((a, b) => String(a.field).localeCompare(String(b.field)))
        .forEach((entry) => {
          const rows = Array.from(entry.rows).sort((a, b) => a - b);
          const li = document.createElement('li');
          li.textContent = `${entry.field} · ${entry.code}: ${entry.message}. Filas: ${rows.join(', ')}`;
          findingsList.appendChild(li);
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
      if (!state.template || !state.sourceFile) return;

      const form = new FormData();
      form.append('template', state.template);
      form.append('csv_file', state.sourceFile);

      const res = await fetch('/api/validate', { method: 'POST', body: form });
      const payload = await res.json();
      if (!res.ok) {
        document.getElementById('api-error').classList.remove('hidden');
        document.getElementById('api-error').textContent = payload.detail || 'No fue posible validar el archivo.';
        return;
      }

      state.validation = payload;
      state.correctionOptions = payload.correction_options || {};
      state.correlationMaps = payload.correlation_maps || {};
      state.delimiter = payload.summary.delimiter || ',';
      const parsed = parseCsv(payload.corrected_csv || '', state.delimiter);
      state.headers = parsed.headers;
      state.rows = parsed.rows;
      state.correctedCsv = payload.corrected_csv || '';

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

    updateValidateButtonState();
    setTab('C');
  </script>
</body>
</html>
"""
