# -*- coding: utf-8 -*-
"""Google Drive API helper class."""

from collections import namedtuple
from pathlib import Path
from typing import Optional, Generator
from time import sleep

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from pydrive2.files import ApiRequestError


__all__ = ["GoogleDriveHelper"]


Item = namedtuple("Item", ["id", "title"])


class GoogleDriveHelper:
    """Helper class to interact with Google Drive API."""

    def __init__(self, service_account_file: Path) -> None:
        """Initialize Google Drive API from service account."""
        # Authenticate using service account.
        gauth = GoogleAuth(
            settings={
                "client_config_backend": "service",
                "service_config": {
                    "client_json_file_path": service_account_file.as_posix(),
                },
                "oauth_scope": ["https://www.googleapis.com/auth/drive"],
            }
        )
        # Authenticate and create the PyDrive client.
        gauth.ServiceAuth()
        self.drive = GoogleDrive(gauth)

    def create_directory(self, title: str, parent: Optional[Item] = None):
        """Create a directory in Google Drive."""
        file = self.drive.CreateFile(
            {"title": title, "mimeType": "application/vnd.google-apps.folder"}
        )
        if parent is not None:
            file["parents"] = [{"id": parent.id}]
        file.Upload()
        return Item(file["id"], file["title"])

    def list_directory(self, item: Optional[Item] = None):
        """Show the content of a folder in Google Drive."""
        if item is None:
            query = "'root' in parents and trashed=false"
        else:
            query = f"'{item.id}' in parents and trashed=false"
        file_list = self.drive.ListFile({"q": query}).GetList()
        return (Item(file["id"], file["title"]) for file in file_list)

    def search(self, query: str):
        """Search for files/directories in Google Drive."""
        q = f"title contains '{query}' and trashed=false"
        file_list = self.drive.ListFile({"q": q}).GetList()
        return (Item(file["id"], file["title"]) for file in file_list)

    def search_in_folder(self, item: Item, query: str):
        """Search for files/directories in a folder in Google Drive."""
        q = f"'{item.id}' in parents and title contains '{query}' and trashed=false"
        file_list = self.drive.ListFile({"q": q}).GetList()
        return (Item(file["id"], file["title"]) for file in file_list)

    def download_file(self, item: Item, path: Path, retry: int = 3, delay: int = 30):
        """Download a file from Google Drive to destination."""
        try:
            file = self.drive.CreateFile({"id": item.id})
            file.GetContentFile(str(path))
        except Exception as e:  # catch all exceptions
            if retry == 0:
                raise e
            else:
                sleep(delay)
                self.download_file(item, path, retry - 1, delay * 2)

    def upload_file(self, path: Path, title: str, parent: Optional[Item] = None):
        """Upload a file to Google Drive."""
        file = self.drive.CreateFile({"title": title})
        if parent is not None:
            file["parents"] = [{"id": parent.id}]
        file.SetContentFile(str(path))
        file.Upload()
        return Item(file["id"], file["title"])

    def delete_file(self, item: Item):
        """Delete file in Google Drive."""
        file = self.drive.CreateFile({"id": item.id})
        file.Delete()

    def list_trash(self) -> Generator[Item, None, None]:
        """Show trash in Google Drive."""
        item_list = self.drive.ListFile({"q": "trashed=true"}).GetList()
        return (Item(item["id"], item["title"]) for item in item_list)

    def empty_trash(self):
        """Empty trash in Google Drive."""
        for item in self.drive.ListFile({"q": "trashed=true"}).GetList():
            item.Delete()
