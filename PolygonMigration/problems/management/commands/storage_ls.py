"""
List (and optionally print) the test-case files stored for a problem.

    python manage.py storage_ls            # check the provider is reachable, list all test_cases/
    python manage.py storage_ls 3          # list test_cases/3/
    python manage.py storage_ls 3 --show 1 # also print test 01 input and 01.a output
"""

from django.core.management.base import BaseCommand, CommandError

from problems.storage import StorageError, TestCaseStorage, get_storage


class Command(BaseCommand):
    help = "List test-case files in the configured cloud storage (STORAGE_PROVIDER)."

    def add_arguments(self, parser):
        parser.add_argument("problem_id", nargs="?", help="Database problem id (omit to list everything)")
        parser.add_argument("--show", type=int, metavar="N", help="Print the input/output of test N")

    def handle(self, *args, problem_id=None, show=None, **opts):
        try:
            storage = get_storage()
            prefix = (TestCaseStorage.problem_prefix(problem_id) if problem_id
                      else f"{TestCaseStorage.ROOT_PREFIX}/")
            keys = sorted(storage.list_files(prefix))
        except StorageError as e:
            raise CommandError(str(e))

        self.stdout.write(f"{storage.display_name} {storage.location()}/{prefix}  ({len(keys)} files)")
        for key in keys:
            self.stdout.write(f"  {key}")

        if show is not None:
            if not problem_id:
                raise CommandError("--show needs a problem_id")
            for key in (storage.input_key(problem_id, show), storage.output_key(problem_id, show)):
                try:
                    body = storage.read_file(key)
                except StorageError as e:
                    raise CommandError(str(e))
                self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- {key} ---"))
                self.stdout.write(body)
