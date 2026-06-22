# Alejandría

> Tu biblioteca personal. En tu homelab. Bajo tu control.

Una alternativa moderna y minimalista a Calibre-Web, construida para correr como un único contenedor Docker. Diseñada para ser fácil de instalar, fácil de usar y agradable a la vista.

---

## ¿Qué es?

**Alejandría** es una aplicación web auto-hospedable para gestionar tu biblioteca de ebooks. Soporta los mismos formatos que Calibre (EPUB, PDF, MOBI, AZW3, FB2, DJVU, CBZ, CBR, RTF, TXT, HTML, LIT, LRF, ODT…) y ofrece lectura en navegador, conversión, send-to-Kindle, OPDS, multi-usuario, estadísticas, resaltados y mucho más.

Está construida en Python + FastAPI en el backend y SvelteKit en el frontend, empaquetada en un único contenedor Docker que incluye Calibre para conversión.

---

## Quick start (3 minutos)

```bash
# 1. Clonar
git clone <repo> alejandria && cd alejandria

# 2. Configurar
cp .env.example .env
# (edita .env si quieres — admin/changeme funciona por defecto)

# 3. Arrancar
docker compose up -d

# 4. Abrir
# http://localhost:8080
# Login: admin / changeme
```

¡Eso es todo! Tu Alejandría está corriendo. Cualquier ebook que pongas en `./library/` será detectado automáticamente.

---

## Temas

La UI tiene **3 temas** (cambian al instante, sin parpadeo, se guarda en `localStorage`):

- **Claro** — fondo crema cálido `#F5F1E8`, no blanco puro, descansa la vista.
- **Oscuro** — negro cálido `#1A1816`, no OLED negro, mejor para sesiones largas.
- **Sepia** — clásico `#F4ECD8` para lectura.

---

## Formatos soportados

| Formato | Lectura navegador | Descarga | Conversión |
|---------|-------------------|----------|------------|
| EPUB    | ✅ Nativo (EPUB.js) | ✅ | ✅ |
| PDF     | ✅ Nativo (PDF.js)  | ✅ | ✅ |
| MOBI    | 🔄 Convertido a EPUB | ✅ | ✅ |
| AZW3    | 🔄 Convertido a EPUB | ✅ | ✅ |
| FB2     | 🔄 Convertido a EPUB | ✅ | ✅ |
| DJVU    | 🔄 Convertido a PDF  | ✅ | ✅ |
| CBZ/CBR | 🔄 Convertido a PDF  | ✅ | ✅ |
| RTF/TXT | ✅ Como texto plano   | ✅ | ✅ |
| HTML    | ✅ Nativo             | ✅ | ✅ |
| LIT/LRF | 🔄 Convertido         | ✅ | ✅ |
| ODT     | 🔄 Convertido         | ✅ | ✅ |

Conversión vía Calibre CLI (`ebook-convert`), con caché en `/config/caches/conversions/`.

---

## Arquitectura

```
┌──────────────────────────────────────────────┐
│  Docker (single container, port 8080)        │
│  ┌────────────────┐    ┌─────────────────┐  │
│  │  FastAPI       │    │  SvelteKit SPA  │  │
│  │  (Python 3.12) │◄──►│  (Node 20)      │  │
│  └────┬───────────┘    └─────────────────┘  │
│       ▼                                     │
│  ┌────────────────┐                         │
│  │  Calibre CLI   │                         │
│  │  calibredb /   │                         │
│  │  ebook-convert │                         │
│  └────────────────┘                         │
└──────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
   /library/      /config/      OPDS feed
   (Calibre       (SQLite,     :8080/opds
    books)        caches)
```

Más detalles en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Features

### Core
- Lectura EPUB/PDF en navegador con resaltados
- Gestión de biblioteca (búsqueda, filtros, orden, paginación)
- Vista de detalle con autores, tags, series, descripción, portadas
- Multi-usuario con roles (admin / user / guest)
- OPDS 1.2 feed (KOReader, Calibre Companion, Moon+, Marvin…)
- Send-to-Kindle (vía SMTP)
- Conversión entre formatos (vía Calibre CLI)
- Watcher de carpeta (auto-detecta libros nuevos)

### Lectura
- Progreso sincronizado por dispositivo
- Resaltados con color + nota
- Anotaciones libres
- 3 temas de lector (claro / oscuro / sepia)
- Tamaño y familia de fuente ajustables
- Tabla de contenidos (TOC)
- Atajos de teclado

### Organización
- Estantes manuales (custom)
- Estantes automáticos (Leyendo / Terminado / Favoritos / Wishlist)
- Tags, autores, series, idiomas, editoriales
- Filtros combinados en biblioteca

### Estadísticas
- Vista anual (heatmap)
- Racha de lectura
- Libros leídos vs. totales
- Tiempo total de lectura
- Velocidad promedio (páginas/hora)

### Tech
- PWA (instalable, offline para libros descargados)
- 3 temas (claro cálido / oscuro cálido / sepia)
- Responsive (móvil, tablet, desktop)
- Service Worker (caché de assets)

### Seguridad
- argon2id password hashing
- JWT con cookies HttpOnly
- CSRF token
- Rate limiting (login)
- OIDC opcional (Authentik / Authelia / Keycloak)
- Permisos por rol

---

## Estructura

```
alejandria/
├── docker/                  # Dockerfile + entrypoints
├── backend/                 # Python + FastAPI
│   ├── src/alejandria/
│   │   ├── auth/            # argon2, JWT, OIDC
│   │   ├── models/          # SQLAlchemy 2.0
│   │   ├── routers/         # 12 routers FastAPI
│   │   ├── schemas/         # Pydantic v2
│   │   ├── services/        # Calibre DB, scanner, conversion, SMTP…
│   │   └── utils/
│   └── tests/               # pytest
├── frontend/                # SvelteKit 2 + Svelte 5
│   └── src/
│       ├── lib/
│       │   ├── api/         # Type-safe fetch
│       │   ├── components/  # Logo, Sidebar, Cover, Toaster…
│       │   ├── reader/      # EPUB.js + PDF.js wrappers
│       │   └── stores/      # auth, theme
│       └── routes/          # home, library, read, shelves, stats…
├── docs/                    # ARCHITECTURE, CONFIG, OPDS, CONTRIBUTING
├── scripts/                 # dev.sh
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
└── README.md
```

---

## Configuración

Toda la config va en `.env` con prefijo `ALEJANDRIA_`. Lo más útil:

| Variable | Default | Qué hace |
|----------|---------|----------|
| `ALEJANDRIA_PORT` | 8080 | Puerto del contenedor |
| `ALEJANDRIA_SECRET_KEY` | *(generado)* | Clave JWT — **cambia en prod** |
| `ALEJANDRIA_ADMIN_USERNAME` | admin | Usuario admin inicial |
| `ALEJANDRIA_ADMIN_PASSWORD` | changeme | Password admin — **cambia en prod** |
| `ALEJANDRIA_LANGUAGE` | es | Idioma UI |
| `ALEJANDRIA_TIMEZONE` | UTC | Zona horaria |
| `SMTP_HOST` | — | Para send-to-Kindle |
| `SMTP_PORT` | 587 | |
| `SMTP_USER` | — | |
| `SMTP_PASSWORD` | — | (Gmail: app password) |
| `SMTP_FROM` | — | Email remitente |
| `PUID` | 1000 | UID del proceso (homelab) |
| `PGID` | 1000 | GID del proceso (homelab) |

Ver [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) para todas las variables y ejemplos de reverse proxy (Caddy, nginx, Traefik).

---

## OPDS

URL del catálogo: **`http://tu-host:8080/opds`**

Compatible con KOReader, Calibre Companion, Moon+ Reader, Marvin, Cantook, KyBook 3.

Ver [`docs/OPDS.md`](docs/OPDS.md) para instrucciones por cliente.

---

## Tests

```bash
# Backend
cd backend && uv pip install -e ".[dev]" && pytest -v

# Frontend
cd frontend && npm install && npm run check && npm test
```

---

## Scripts útiles

```bash
./scripts/dev.sh start       # arrancar producción
./scripts/dev.sh dev         # arrancar desarrollo (hot reload)
./scripts/dev.sh logs        # tail logs
./scripts/dev.sh shell       # shell dentro del contenedor
./scripts/dev.sh rebuild     # rebuild imagen
./scripts/dev.sh reset       # borrar library + config (DESTRUCTIVO)
./scripts/dev.sh test        # correr tests backend
```

---

## Contribuir

¡Las contribuciones son bienvenidas! Lee [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

---

## Licencia

- **Código de Alejandría**: MIT
- **Calibre CLI** (binario dentro del contenedor): GPL-3
- **EPUB.js**: BSD-2
- **PDF.js**: Apache-2.0

Ver [`LICENSE`](LICENSE).

---

## Créditos

- **Calibre** — el motor de conversión y biblioteca
- **EPUB.js** — renderizador de EPUB en navegador
- **PDF.js** — renderizador de PDF en navegador
- **FastAPI** — framework backend
- **SvelteKit** — framework frontend

---

**Construido con la convicción de que tus libros deberían ser tuyos.**