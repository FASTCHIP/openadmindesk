"""SFTP backend implementation with async support."""

from __future__ import annotations

import asyncio
import os
import stat
import logging
import threading
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

from paramiko import SSHClient, SFTPClient

from openadmindesk.core.host_key import HostKeyPrompt, HostKeyTrustStore, TrustOnFirstUsePolicy
from openadmindesk.core.remote_file import RemoteFile, FileType

logger = logging.getLogger(__name__)


class SftpBackend:
    """SFTP backend implementation with async support."""
    
    def __init__(self, host_key_store: HostKeyTrustStore | None = None) -> None:
        """Initialize the SFTP backend."""
        self._host_key_store = host_key_store or HostKeyTrustStore()
        self._pending_host_key: HostKeyPrompt | None = None
        self._ssh_client: Optional[SSHClient] = None
        self._sftp_client: Optional[SFTPClient] = None
        self._connected: bool = False
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sftp_async")
    
    def _get_executor(self):
        """Get the thread pool executor."""
        return self._executor
    
    async def _run_blocking(self, func, *args, **kwargs):
        """Run a blocking operation in the thread pool."""
        executor = self._executor
        if executor is None:
            raise RuntimeError("SftpBackend executor already closed")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))
    
    def _connect_sync(self, host: str, port: int = 22, username: str = "",
                        password: Optional[str] = None, private_key_path: Optional[str] = None) -> bool:
        """Connect to the SFTP server synchronously."""
        with self._lock:
            try:
                self._ssh_client = SSHClient()
                self._ssh_client.load_system_host_keys()
                self._host_key_store.load_into(self._ssh_client)
                host_key_policy = TrustOnFirstUsePolicy(self._host_key_store)
                self._ssh_client.set_missing_host_key_policy(host_key_policy)

                if private_key_path:
                    self._ssh_client.connect(
                        host,
                        port=port,
                        username=username,
                        key_filename=private_key_path,
                    )
                else:
                    self._ssh_client.connect(
                        host,
                        port=port,
                        username=username,
                        password=password,
                    )

                self._sftp_client = self._ssh_client.open_sftp()
                self._pending_host_key = None
                self._connected = True

                return True
            except Exception as e:
                if 'host_key_policy' in locals():
                    self._pending_host_key = host_key_policy.pending
                logger.error(f"Failed to connect to SFTP: {e}")
                self._connected = False
                return False

    def connect(self, host: str, port: int = 22, username: str = "", 
                  password: Optional[str] = None, private_key_path: Optional[str] = None) -> bool:
        """Connect to the SFTP server (synchronous)."""
        return self._connect_sync(host, port, username, password, private_key_path)
    
    async def connect_async(self, host: str, port: int = 22, username: str = "", 
                              password: Optional[str] = None, private_key_path: Optional[str] = None) -> bool:
        """Connect to the SFTP server asynchronously."""
        return await self._run_blocking(
            self._connect_sync, host, port, username, password, private_key_path
        )
    
    def _disconnect_sync(self) -> None:
        """Disconnect from the SFTP server synchronously."""
        with self._lock:
            if self._sftp_client:
                self._sftp_client.close()
            if self._ssh_client:
                self._ssh_client.close()
            self._sftp_client = None
            self._ssh_client = None
            self._connected = False
    
    def disconnect(self) -> None:
        """Disconnect from the SFTP server (synchronous)."""
        self._disconnect_sync()
    
    async def disconnect_async(self) -> None:
        """Disconnect from the SFTP server asynchronously."""
        await self._run_blocking(self._disconnect_sync)
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def pending_host_key(self) -> HostKeyPrompt | None:
        return self._pending_host_key

    def trust_pending_host_key(self) -> bool:
        if not self._pending_host_key:
            return False
        self._host_key_store.save_host_key(
            self._pending_host_key.hostname,
            self._pending_host_key.key,
        )
        self._pending_host_key = None
        return True

    def _list_directory_sync(self, path: str = "/") -> List[RemoteFile]:
        """List directory contents synchronously."""
        if not self._connected or not self._sftp_client:
            return []
        
        try:
            with self._lock:
                file_list = self._sftp_client.listdir_attr(path)
            files = []
            
            for attr in file_list:
                # Create RemoteFile object
                remote_file = self._attr_to_remote_file(attr, path)
                files.append(remote_file)
            
            return files
        except Exception as e:
            logger.error(f"Failed to list directory {path}: {e}")
            return []
    
    def list_directory(self, path: str = "/") -> List[RemoteFile]:
        """List directory contents (synchronous)."""
        return self._list_directory_sync(path)
    
    async def list_directory_async(self, path: str = "/") -> List[RemoteFile]:
        """List directory contents asynchronously."""
        return await self._run_blocking(self._list_directory_sync, path)
    
    def _get_file_info_sync(self, path: str) -> Optional[RemoteFile]:
        """Get information about a specific file synchronously."""
        if not self._connected or not self._sftp_client:
            return None
        
        try:
            with self._lock:
                attr = self._sftp_client.stat(path)
            return self._attr_to_remote_file(
                attr,
                os.path.dirname(path),
                filename=os.path.basename(path),
            )
        except Exception as e:
            logger.error(f"Failed to get file info for {path}: {e}")
            return None
    
    def get_file_info(self, path: str) -> Optional[RemoteFile]:
        """Get information about a specific file (synchronous)."""
        return self._get_file_info_sync(path)
    
    async def get_file_info_async(self, path: str) -> Optional[RemoteFile]:
        """Get information about a specific file asynchronously."""
        return await self._run_blocking(self._get_file_info_sync, path)
    
    def _download_file_sync(self, remote_path: str, local_path: str, callback=None) -> bool:
        """Download a file from remote to local synchronously."""
        if not self._connected or not self._sftp_client:
            return False
        
        try:
            with self._lock:
                self._sftp_client.get(remote_path, local_path, callback=callback)
            return True
        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str, callback=None) -> bool:
        """Download a file from remote to local (synchronous)."""
        return self._download_file_sync(remote_path, local_path, callback)
    
    async def download_file_async(self, remote_path: str, local_path: str) -> bool:
        """Download a file from remote to local asynchronously."""
        return await self._run_blocking(self._download_file_sync, remote_path, local_path)
    
    def _upload_file_sync(self, local_path: str, remote_path: str, callback=None) -> bool:
        """Upload a file from local to remote synchronously."""
        if not self._connected or not self._sftp_client:
            return False
        
        try:
            with self._lock:
                self._sftp_client.put(local_path, remote_path, callback=callback)
            return True
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    def upload_file(self, local_path: str, remote_path: str, callback=None) -> bool:
        """Upload a file from local to remote (synchronous)."""
        return self._upload_file_sync(local_path, remote_path, callback)
    
    async def upload_file_async(self, local_path: str, remote_path: str) -> bool:
        """Upload a file from local to remote asynchronously."""
        return await self._run_blocking(self._upload_file_sync, local_path, remote_path)
    
    def _make_directory_sync(self, path: str) -> bool:
        """Create a directory synchronously."""
        if not self._connected or not self._sftp_client:
            return False
        
        try:
            with self._lock:
                self._sftp_client.mkdir(path)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return False
    
    def make_directory(self, path: str) -> bool:
        """Create a directory (synchronous)."""
        return self._make_directory_sync(path)
    
    async def make_directory_async(self, path: str) -> bool:
        """Create a directory asynchronously."""
        return await self._run_blocking(self._make_directory_sync, path)
    
    def _remove_file_sync(self, path: str) -> bool:
        """Remove a file or directory synchronously."""
        if not self._connected or not self._sftp_client:
            return False
        
        try:
            with self._lock:
                self._sftp_client.remove(path)
            return True
        except Exception as e:
            logger.error(f"Failed to remove {path}: {e}")
            return False
    
    def remove_file(self, path: str) -> bool:
        """Remove a file or directory (synchronous)."""
        return self._remove_file_sync(path)
    
    async def remove_file_async(self, path: str) -> bool:
        """Remove a file or directory asynchronously."""
        return await self._run_blocking(self._remove_file_sync, path)
    
    def _attr_to_remote_file(self, attr, base_path: str, filename: str | None = None) -> RemoteFile:
        """Convert SFTP attributes to RemoteFile object."""
        name = filename or getattr(attr, "filename", None)
        if not name:
            name = os.path.basename(base_path.rstrip("/")) or "/"
        # Use '/' explicitly for remote SFTP paths (not os.path.join)
        base = "" if base_path == "/" else base_path.rstrip("/")
        full_path = f"{base}/{name}" if base else f"/{name}"
        
        # Determine file type
        file_type = FileType.OTHER
        if stat.S_ISDIR(attr.st_mode):
            file_type = FileType.DIRECTORY
        elif stat.S_ISREG(attr.st_mode):
            file_type = FileType.FILE
        elif stat.S_ISLNK(attr.st_mode):
            file_type = FileType.LINK
        
        # Create RemoteFile object
        return RemoteFile(
            path=full_path,
            name=name,
            size=attr.st_size,
            file_type=file_type,
            permissions=oct(attr.st_mode)[-3:],  # Get last 3 octal digits
            owner=str(attr.st_uid),
            group=str(attr.st_gid),
            modified_at=str(attr.st_mtime),
            is_hidden=name.startswith('.')
        )
    
    def close(self) -> None:
        """Shutdown the thread pool executor and disconnect."""
        if self._connected:
            self._disconnect_sync()
        executor = self._executor
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
