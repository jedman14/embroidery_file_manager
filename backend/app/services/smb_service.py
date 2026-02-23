import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from smb.SMBConnection import SMBConnection
from app.config import settings

class SMBService:
    def __init__(self):
        self.conn: Optional[SMBConnection] = None
        self.share = settings.smb_share

    def _disconnect(self) -> None:
        """Drop connection so next connect() creates a new one."""
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def connect(self) -> SMBConnection:
        """Establish SMB connection"""
        if self.conn is None or not self.conn.sock:
            self.conn = SMBConnection(
                settings.smb_username,
                settings.smb_password,
                "embroidery-client",
                settings.smb_host,
                domain="WORKGROUP",
                use_ntlm_v2=True
            )
            self.conn.connect(settings.smb_host, settings.smb_port)
        return self.conn

    def _on_connection_error(self) -> None:
        """Call when a socket/connection error occurs so we reconnect next time."""
        self._disconnect()

    def list_directory(self, path: str) -> List[dict]:
        """List contents of a directory on SMB share"""
        path = path.strip('/')
        if path:
            path = path + "/"
        # Use "" for root; some SMB servers fail with "."
        list_path = path
        last_err = None
        for attempt in range(2):
            try:
                conn = self.connect()
                files = conn.listPath(self.share, list_path)
                break
            except (OSError, ConnectionError, BrokenPipeError) as e:
                last_err = e
                self._on_connection_error()
                if attempt == 1:
                    raise
        else:
            raise last_err or RuntimeError("list_directory failed")
        items = []
        for f in files:
            if f.filename in ['.', '..']:
                continue
            item_path = (f"{path}{f.filename}".strip('/') if path else f.filename)
            is_dir = f.isDirectory
            items.append({
                "name": f.filename,
                "path": item_path,
                "is_directory": is_dir,
                "size": f.file_size if not is_dir else 0,
                "modified": datetime.fromtimestamp(f.last_write_time).isoformat() if f.last_write_time else None
            })
        return items
    
    def get_file(self, path: str) -> bytes:
        """Read file content from SMB share"""
        conn = self.connect()
        path = path.strip('/')
        
        from io import BytesIO
        file_data = BytesIO()
        
        attributes = conn.getAttributes(self.share, path)
        file_size = attributes.file_size
        
        conn.retrieveFile(self.share, path, file_data)
        return file_data.getvalue()
    
    def put_file(self, path: str, data: bytes) -> bool:
        """Write file to SMB share"""
        conn = self.connect()
        path = path.strip('/')
        
        from io import BytesIO
        file_data = BytesIO(data)
        
        conn.storeFile(self.share, path, file_data)
        return True
    
    def delete_file(self, path: str) -> bool:
        """Delete file from SMB share"""
        conn = self.connect()
        path = path.strip('/')
        conn.deleteFiles(self.share, path)
        return True

    def delete_directory(self, path: str) -> bool:
        """Delete empty directory from SMB share"""
        conn = self.connect()
        path = path.strip('/')
        conn.deleteDirectory(self.share, path)
        return True

    def delete_directory_recursive(self, path: str) -> bool:
        """Delete directory and all contents. Prefer pysmb's native recursive delete."""
        path = path.strip('/')
        if not path:
            return True
        conn = self.connect()
        try:
            conn.deleteFiles(self.share, path, delete_matching_folders=True)
            return True
        except Exception:
            pass
        items = self.list_directory(path)
        for item in items:
            if item['is_directory']:
                self.delete_directory_recursive(item['path'])
            else:
                self.delete_file(item['path'])
        self.delete_directory(path)
        return True
    
    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename a file or directory"""
        conn = self.connect()
        old_path = old_path.strip('/')
        new_path = new_path.strip('/')
        
        conn.rename(self.share, old_path, new_path)
        return True
    
    def move(self, source_path: str, dest_path: str) -> bool:
        """Move a file or directory"""
        return self.rename(source_path, dest_path)
    
    def create_directory(self, path: str) -> bool:
        """Create directory on SMB share"""
        conn = self.connect()
        path = path.strip('/')
        
        conn.createDirectory(self.share, path)
        return True

    def create_directory_recursive(self, path: str) -> bool:
        """Create directory and all parent directories on SMB share"""
        path = path.strip('/')
        if not path:
            return True

        parts = path.split('/')
        current = ''
        for part in parts:
            current = f"{current}/{part}" if current else part
            if not self.file_exists(current):
                self.create_directory(current)
        return True
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        conn = self.connect()
        path = path.strip('/')
        
        try:
            conn.getAttributes(self.share, path)
            return True
        except:
            return False

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory (not a file)"""
        conn = self.connect()
        path = path.strip('/')
        if not path:
            return True
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        if not parent:
            parent = ""
        else:
            parent = parent + "/"
        list_path = parent + "/" if parent else ""
        for f in conn.listPath(self.share, list_path):
            if f.filename == name:
                return bool(f.isDirectory)
        return False
    
    def get_file_size(self, path: str) -> int:
        """Get file size"""
        conn = self.connect()
        path = path.strip('/')
        
        attributes = conn.getAttributes(self.share, path)
        return attributes.file_size
