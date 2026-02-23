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
- **File Access**: SMB/CIFS protocol via `smbprotocol` or `pysmb`

### Supported Embroidery Formats
- `.dst` - Tajima
- `.pes` - Brother
- `.pec` - Brother
- `.exp` - Melco
- `.vp3` - Viking
- `.jef` - Janome
- `.xxx` - Wilcom
- `.ufo` - UFO (Wilcom)
- `.emd` - Elna
- `.csd` - Singer
- `.10o` - Pfaff

## Suggestions

### Architecture
- **API-First Design**: RESTful API for all file operations
- **Streaming Responses**: Large files streamed directly from SMB to client
- **Caching**: Cache thumbnails and directory listings for performance

### Security
- **Read-Only Mode Option**: Configurable Samba mount as read-only
- **Path Traversal Protection**: Prevent `../` attacks
- **File Validation**: Validate file extensions and magic bytes

### UX Features
- **Breadcrumb Navigation**: Easy path traversal
- **Search**: Filter files by name
- **Sort**: By name, date, size, type
- **Context Menus**: Right-click actions on files/folders
- **Keyboard Shortcuts**: Delete, select all, navigation

## Configuration

Create a `.env` file with:

```env
# Samba Configuration
SMB_HOST=your-smb-server
SMB_SHARE=embroidery
SMB_USERNAME=your-username
SMB_PASSWORD=your-password
SMB_PORT=445

# App Configuration
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Optional: suggest tags from design image
# For vision (auto-tag / suggest from image): set one of these when using the vision profile:
# OLLAMA_BASE_URL=http://ollama:11434
# Or OPENAI_API_KEY=sk-... to use OpenAI instead.
```

## Running

```bash
# Start all services
docker compose up -d
```

For **image-based tag suggestions**, start with the vision profile and run Ollama’s LLaVA model, Add `OLLAMA_BASE_URL=http://ollama:11434` to `.env`, then:

```bash
docker compose --profile vision up -d
docker compose exec ollama ollama run llava
```

```bash
# View logs
docker compose logs -f
# Stop services
docker compose down
```

## API Endpoints

### Files
- `GET /api/files` - List directory contents
- `GET /api/files/*` - Get file details or download
- `POST /api/files` - Upload new file
- `PUT /api/files/*` - Rename file
- `DELETE /api/files/*` - Delete file(s)
- `POST /api/files/*/move` - Move file to new location

### Thumbnails
- `GET /api/thumbnails/*` - Get generated thumbnail

### Tags
- `POST /api/tags/suggest?path=...` - Suggest 3–5 tags from design image (uses in-stack Ollama when vision profile is running, or OPENAI_API_KEY)

### Extraction
- `POST /api/files/*/extract` - Extract zip file contents

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
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
