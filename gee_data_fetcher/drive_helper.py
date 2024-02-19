# -*- coding: utf-8 -*-
"""Google Drive API helper class."""

from collections import namedtuple
from pathlib import Path
from typing import Optional, Generator

from pydrive2.auth import GoogleAuth, RefreshError
from pydrive2.drive import GoogleDrive


__all__ = ["GoogleDriveHelper"]


Item = namedtuple("Item", ["id", "title"])


class GoogleDriveHelper:
    """Helper class to interact with Google Drive API."""

    def __init__(self, service_account_file: Path) -> None:
        """Initialize Google Drive API from service account."""
        gauth = GoogleAuth()
        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
            service_account_file.as_posix(),
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        self.drive = GoogleDrive(gauth)

    def _authenticate(self, secret_file: Path, credentials_file: Path):
        """Authenticate with Google Drive API."""
        GoogleAuth.DEFAULT_SETTINGS["client_config_file"] = str(secret_file)
        GoogleAuth.DEFAULT_SETTINGS["get_refresh_token"] = True
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile(str(credentials_file))
        if gauth.credentials is None:
            print("No credentials found.")
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            print("Refreshing token...")
            try:
                gauth.Refresh()
            except RefreshError:
                # Remove credentials file and try again
                credentials_file.unlink()
                return self._authenticate(secret_file, credentials_file)
        else:
            print("Authorizing...")
            gauth.Authorize()
        gauth.SaveCredentialsFile(str(credentials_file))
        return gauth

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

    def download_file(self, item: Item, path: Path):
        """Download a file from Google Drive to destination."""
        file = self.drive.CreateFile({"id": item.id})
        file.GetContentFile(str(path))

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
