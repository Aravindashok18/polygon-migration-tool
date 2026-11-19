"""
Provider-neutral interface for test-case storage.

The migration flow (PolygonAPI.migrate_to_storage) only talks to this
interface. Each provider (Cloudflare R2 / AWS S3, Azure Blob, ...) lives in
its own module and implements the abstract methods below, so switching
provider is a configuration change (STORAGE_PROVIDER) rather than a rewrite.

Object layout (unchanged from the original Azure implementation):

    test_cases/{problem_id}/{test_number}      input file
    test_cases/{problem_id}/{test_number}.a    expected output file

where problem_id is the *database* id of the Problem row and test_number is
the 1-based position of the test, zero-padded to two digits (01, 02, ... 10).
"""

from abc import ABC, abstractmethod


class StorageError(Exception):
    """Raised when a storage provider cannot complete an operation."""


class TestCaseStorage(ABC):
    """Base class every storage provider implements."""

    #: Human readable provider name, shown to the user in success messages.
    display_name = "cloud storage"

    ROOT_PREFIX = "test_cases"

    # ------------------------------------------------------------------ keys
    @classmethod
    def problem_prefix(cls, problem_id):
        return f"{cls.ROOT_PREFIX}/{problem_id}/"

    @classmethod
    def input_key(cls, problem_id, test_number):
        return f"{cls.ROOT_PREFIX}/{problem_id}/{int(test_number):02d}"

    @classmethod
    def output_key(cls, problem_id, test_number):
        return f"{cls.input_key(problem_id, test_number)}.a"

    @classmethod
    def file_key(cls, problem_id, filename):
        return f"{cls.ROOT_PREFIX}/{problem_id}/{filename}"

    # ------------------------------------------------- provider primitives
    @abstractmethod
    def upload_file(self, key, data, content_type="application/octet-stream"):
        """Store ``data`` (bytes) at ``key``, overwriting any existing object."""

    @abstractmethod
    def list_files(self, prefix):
        """Return the list of object keys that start with ``prefix``."""

    @abstractmethod
    def read_file(self, key):
        """Return the object at ``key`` decoded as UTF-8 text."""

    @abstractmethod
    def delete_files(self, keys):
        """Delete the given object keys. Missing keys are ignored."""

    @abstractmethod
    def location(self):
        """Short description of where files go, e.g. ``r2://bucket``."""

    # ------------------------------------------- test-case level helpers
    def upload_test_case(self, problem_id, test_number, input_data, output_data):
        """Upload one input/output pair. Raises StorageError on failure."""
        self.upload_file(
            self.input_key(problem_id, test_number),
            _to_bytes(input_data),
            content_type="text/plain; charset=utf-8",
        )
        self.upload_file(
            self.output_key(problem_id, test_number),
            _to_bytes(output_data),
            content_type="text/plain; charset=utf-8",
        )

    def list_problem_files(self, problem_id):
        return self.list_files(self.problem_prefix(problem_id))

    def delete_problem_files(self, problem_id):
        """Delete every object under test_cases/{problem_id}/. Returns count."""
        keys = self.list_problem_files(problem_id)
        if keys:
            self.delete_files(keys)
        return len(keys)


def _to_bytes(data):
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    return str(data).encode("utf-8")
