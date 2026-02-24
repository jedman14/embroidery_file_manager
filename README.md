# Embroidery File Manager

A web-based file manager for embroidery files that connects to a Samba share (or local path). Supports nested folders, zips, CRUD, bulk operations, thumbnails, tags, notes, folder logos, format conversion, and search.

## Requirements

### Core Features
- **Samba or local storage**: Connect to an SMB share and/or use a local mount path
- **Nested folders**: Browse folder hierarchy; create folders
- **Zipped files**: Open .zip contents in-place; extract to a folder
- **CRUD**: Create, rename, delete files and folders; move between folders
- **Upload**: Upload files into the current folder
- **Thumbnails & preview**: Thumbnail grid and full-size preview for embroidery designs
- **File type detection**: DST, PES, PEC, EXP, VP3, JEF, XXX, etc.; filter by type, size, hoop, color changes
- **Search**: Search by file name, path, or tags (current folder first, then everywhere)
- **Bulk operations**: Select multiple items for delete or download
- **Tags**: Assign tags to files; search by tag; tag manager (rename, merge, delete tags; bulk add)
- **Notes**: Per-file notes (stored in app data)
- **Folder logos**: Custom icon per folder (URL or uploaded image)
- **Format conversion**: Convert between supported embroidery formats (e.g. PES → DST); download or save to folder
- **Auto-tag**: Optional batch tagging of untagged files using image recognition (Ollama/OpenAI)
- **Mobile-friendly UI**: Responsive layout with collapsible filters, touch-friendly actions, and card view on small screens (tags page)

### Technical Stack
- **Backend**: Python 3.12 with FastAPI
- **Frontend**: Svelte 5
- **Container**: Docker with Docker Compose
- **File Access**: SMB/CIFS via `smbprotocol`

### Supported Embroidery Formats
- `.dst` (Tajima), `.pes` / `.pec` (Brother), `.exp` (Melco), `.vp3` (Viking), `.jef` (Janome), `.xxx` / `.ufo` (Wilcom), `.emd` (Elna), `.csd` (Singer), `.10o` (Pfaff)

## Getting started

Edit `.env` with your SMB details before or after the first run. One-shot setup and run:

```bash
git clone https://github.com/jedman14/embroidery_file_manager.git
cd embroidery_file_manager
cp .env.example .env
# edit .env with your SMB_HOST, SMB_SHARE, SMB_USERNAME, SMB_PASSWORD
docker compose up -d --build
```

## Configuration

`.env` (from `.env.example`) — required and optional settings:

```env
# Samba (required)
SMB_HOST=your-smb-server
SMB_SHARE=embroidery
SMB_USERNAME=your-username
SMB_PASSWORD=your-password
SMB_PORT=445

# App
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Optional: local path instead of or in addition to SMB (FILE_SOURCE=smb|local|both)
# LOCAL_MOUNT_PATH=/mnt/embroidery

# Optional: tag suggestions from design images
# Use in-stack Ollama (default) or OpenAI:
# OLLAMA_BASE_URL=http://ollama:11434
# OPENAI_API_KEY=sk-...
```

The app is a single service (backend serves frontend on same origin). Open it by hostname or IP (e.g. `http://dock.home:8001` or `http://localhost:8001`); no per-machine API URL needed.

## Running

- **App (UI + API)**: http://localhost:8001  

To use **image-based tag suggestions**, pull and run the vision model:

```bash
docker compose exec ollama ollama run llava
```

```bash
# Logs
docker compose logs -f

# Stop
docker compose down
```

## API Endpoints

### Files
- `GET /api/files` – List directory (query: `path`)
- `GET /api/files/search` – Search by name/path/tags
- `GET /api/files/*` – File details or download
- `GET /api/files/*/embroidery-info` – Embroidery metadata (colors, hoop, color changes)
- `POST /api/files/embroidery-info-batch` – Batch embroidery info
- `POST /api/files` – Upload
- `POST /api/files/folder` – Create folder
- `PUT /api/files/*` – Rename
- `DELETE /api/files/*` – Delete (single or batch)
- `POST /api/files/*/move` – Move (body: `{"destination": "path"}`)
- `POST /api/files/*/extract` – Extract zip (query: `destination`)
- `GET /api/files/convert/formats` – Supported read/write formats
- `POST /api/files/convert` – Convert format (query: path, target_format; optional save path)

### Thumbnails & preview
- `GET /api/thumbnails/*` – Thumbnail image
- `GET /api/thumbnails/preview/*` – Full-size preview image

### Tags
- `GET /api/tags?path=...` – Tags for a path
- `POST /api/tags` – Set tags (body: path, tags)
- `GET /api/tags/search?tag=...` – Search files by tag
- `GET /api/tags/all` – All tags (names)
- `GET /api/tags/paths` – Paths that have tags
- `POST /api/tags/merge` – Merge one tag into another
- `DELETE /api/tags/globally` – Remove tag from all files
- `POST /api/tags/bulk-add` – Add tag to multiple paths
- `POST /api/tags/suggest?path=...` – Suggest tags from design image (Ollama or OpenAI)
- `POST /api/tags/run-auto-tag` – Auto-tag untagged files in a path

### Notes
- `GET /api/notes?path=...` – Notes for path(s)
- `POST /api/notes/batch` – Get notes for multiple paths
- `PUT /api/notes/*` – Set note for path
- `DELETE /api/notes/*` – Clear note

### Folder logos
- `GET /api/logos` – List folder logos
- `GET /api/logos/*` – Logo image for folder
- `POST /api/logos/*` – Set logo (body: url) or upload
- `DELETE /api/logos/*` – Remove folder logo

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # files, thumbnails, tags, logos, notes
│   │   ├── services/
│   │   ├── config.py
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   ├── routes/
│   │   └── app.html
│   ├── package.json
│   └── svelte.config.js
├── Dockerfile             # single image: frontend build + backend
├── docker-compose.yml
├── .env.example
└── README.md
```
