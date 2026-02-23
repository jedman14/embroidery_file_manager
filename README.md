# Embroidery File Manager

A web-based file manager for embroidery files that connects to a Samba share. Supports nested folder structures, zipped files, CRUD operations, bulk management, file previews, and embroidery file type detection.

## Requirements

### Core Features
- **Samba Share Integration**: Connect to a remote SMB share to access embroidery files
- **Nested Folder Support**: Browse through multiple levels of folder hierarchy
- **Zipped File Support**: Handle compressed embroidery files (.zip)
- **CRUD Operations**: Create, Read, Update (rename), Delete embroidery files
- **Move Files**: Drag-and-drop or menu-based file moving between folders
- **Picture Preview**: Display thumbnail images of embroidery designs
- **File Type Detection**: Identify embroidery file formats (DST, PES, PEC, EXP, VP3, etc.)
- **Bulk Management**: Select multiple files for bulk operations (move, delete, download)

### Technical Stack
- **Backend**: Python 3.12 with FastAPI
- **Frontend**: Svelte 5
- **Container**: Docker with Docker Compose
- **File Access**: SMB/CIFS via `smbprotocol`

### Supported Embroidery Formats
- `.dst` (Tajima), `.pes` / `.pec` (Brother), `.exp` (Melco), `.vp3` (Viking), `.jef` (Janome), `.xxx` / `.ufo` (Wilcom), `.emd` (Elna), `.csd` (Singer), `.10o` (Pfaff)

## Getting started

Edit `.env` with your SMB details (and optional `VITE_API_URL`) before or after the first run. One-shot setup and run:

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

# Optional: tag suggestions from design images
# Use in-stack Ollama (default) or OpenAI:
# OLLAMA_BASE_URL=http://ollama:11434
# OPENAI_API_KEY=sk-...
```

For the frontend to reach the API when running in Docker, set `VITE_API_URL` in `.env` to your backend URL (e.g. `http://localhost:8001` or your machine’s IP). The compose file may override this for your environment.

## Running

- **Frontend**: http://localhost:5174  
- **Backend API**: http://localhost:8001  

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
- `GET /api/files/*` – File details or download
- `POST /api/files` – Upload
- `PUT /api/files/*` – Rename
- `DELETE /api/files/*` – Delete
- `POST /api/files/*/move` – Move (body: `{"destination": "path"}`)
- `POST /api/files/*/extract` – Extract zip (query: `destination`)

### Thumbnails & logos
- `GET /api/thumbnails/*` – Thumbnail image
- `GET /api/logos/*` – Logo image

### Tags
- `POST /api/tags/suggest?path=...` – Suggest tags from design image (Ollama or OpenAI)

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # files, thumbnails, tags, logos
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
│   ├── svelte.config.js
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```
