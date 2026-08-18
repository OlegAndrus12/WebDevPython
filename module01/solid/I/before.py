"""Interface Segregation — BEFORE: the single wide `FileStorage` interface forces
`ReadOnlyStorage` to implement `upload()` and `delete()`, two methods it cannot perform."""

from abc import ABC, abstractmethod

class FileStorage(ABC):
    @abstractmethod
    def upload(self, file_path: str):
        pass

    @abstractmethod
    def download(self, file_name: str):
        pass
    
    @abstractmethod
    def delete(self, file_name: str):
        pass

    @abstractmethod
    def list_files(self):
        pass


class ReadOnlyStorage(FileStorage):
    def upload(self, file_path: str):
        raise NotImplementedError("Read-only storage")
    
    def delete(self, file_name: str):
        raise NotImplementedError("Read-only storage")

    def list_files(self):
        return ["archived_1.txt", "archived_2.txt"]

