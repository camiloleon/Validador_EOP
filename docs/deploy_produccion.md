# Entregables de paso a producción — Validador EOP

Fecha de corte: 2026-03-05

## 1) Entregables incluidos
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `.env.example`
- `docs/master_plan.md`
- `docs/deploy_produccion.md`

## 2) Pre-requisitos del servidor
- Docker Engine 24+
- Docker Compose v2
- Puerto disponible para exposición (por defecto 8000)

## 3) Preparar variables de entorno
```bash
cp .env.example .env
```
Editar `.env` si desea cambiar el puerto externo:
```dotenv
HOST_PORT=8000
```

## 4) Levantar en servidor (prueba)
```bash
docker compose up -d --build
```

Verificar estado:
```bash
docker compose ps
curl -f http://127.0.0.1:8000/api/health
```

## 5) Logs y soporte
```bash
docker compose logs -f validador-eop
```

## 6) Apagado
```bash
docker compose down
```

## 7) Rollback por versión
```bash
git fetch --tags
git checkout <tag>
docker compose up -d --build
```

## 8) Backup de versión (código fuente)
Generar artefacto zip del punto exacto (sin `.git`):
```bash
git archive --format=zip --output backup_validador_eop_<tag>.zip <tag>
```

## 9) Notas operativas
- El servicio expone `FastAPI` en `0.0.0.0:8000` dentro del contenedor.
- Catálogos requeridos: `Parametros/Parametrizacion EOP.xlsx`.
- Endpoint de salud: `/api/health`.

## 10) Despliegue con dominio + HTTPS (Nginx + Let's Encrypt)

Archivos usados:
- `docker-compose.prod.yml`
- `.env.prod.example`
- `deploy/nginx/templates/http.conf.template`
- `deploy/nginx/templates/https.conf.template`

### Paso A — Bootstrap HTTP
```bash
cp .env.prod.example .env.prod
```
Editar `.env.prod`:
```dotenv
DOMAIN=tu-dominio.com
LETSENCRYPT_EMAIL=tu-correo@empresa.com
HOST_PORT_HTTP=80
HOST_PORT_HTTPS=443
NGINX_MODE=http
```

Levantar app + nginx en HTTP:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build validador-eop nginx
```

### Paso B — Emitir certificado
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm certbot \
	certonly --webroot -w /var/www/certbot \
	-d $DOMAIN --email $LETSENCRYPT_EMAIL --agree-tos --no-eff-email
```

### Paso C — Activar HTTPS
Cambiar en `.env.prod`:
```dotenv
NGINX_MODE=https
```

Recrear nginx:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --force-recreate nginx
```

Verificar:
```bash
curl -f https://tu-dominio.com/api/health
```

### Renovación automática
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile renew up -d certbot-renew
```
