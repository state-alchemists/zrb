import json
import os
import shutil
import tempfile
import time
import warnings
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.engine.agent.types import ModelMessage

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.capabilities.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.capabilities.history_manager.archive_layout import (
    ARCHIVE_DIR_NAME,
    TOOL_RESULTS_DIR_SUFFIX,
    archive_lock_path,
    archive_names_in,
    tool_results_names_in,
)
from zrb.llm.capabilities.history_manager.message_repair import sanitize_history
from zrb.llm.contracts.util.subagent_session_naming import (
    SUBAGENT_HISTORY_SUBDIR,
    parse_delegated_session,
    subagent_history_directories,
)
from zrb.util.match import fuzzy_match
from zrb.util.owner_only import makedirs_owner_only, tighten_once
from zrb.util.string.name import has_random_name_prefix, safe_segment
from zrb.util.todo.duration import parse_duration

BACKUP_DIR_NAME = "backups"
"""Subdirectory of the history directory holding timestamped backups.

Backups live apart from live transcripts so rotation can never mistake a
conversation whose name happens to end in a timestamp
(`standup-2026-11-20-09-00`) for a backup of another one, and so search and
session listing, which only read the history root and `subagent/`, never offer
a backup as a conversation.
"""

# In-RAM cache bound: the most-recently-used conversations kept in memory.
# Evicted entries reload losslessly from disk on next access, so the bound
# only trades a re-read for memory in long sessions that touch many
# conversations.
_MAX_CACHED_CONVERSATIONS = 8

# A history file with no messages holds an empty list, which the writer
# (`json.dump(messages, f, indent=2)`) spells `[]` — two bytes — while a name
# reserved before anything was said is an empty file of zero. Anything larger
# has at least one message, so `search` can drop the empties by size without
# reading every file in the directory.
_EMPTY_HISTORY_MAX_BYTES = 2


def default_history_manager() -> "FileHistoryManager":
    """The file-backed history manager used wherever no explicit one is
    configured."""
    return FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)


def _is_older_than(path: str, cutoff: float) -> bool:
    """Whether *path* exists and its mtime is before *cutoff*."""
    try:
        return os.stat(path).st_mtime < cutoff
    except OSError:
        return False


def _newest_mtime(path: str) -> float:
    """The newest mtime of *path* or a regular file directly inside it.

    A missing path reports ``inf`` so a caller deciding whether to delete it
    treats "unknown" as "keep", never as "old enough".
    """
    try:
        newest = os.stat(path).st_mtime
    except OSError:
        return float("inf")
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        newest = max(newest, entry.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    continue
    except OSError:
        return newest
    return newest


def _is_within(directory: str, path: str) -> bool:
    """Whether *path* stays inside *directory* after resolving symlinks.

    A lexical prefix check is not enough: a symlinked entry inside the tree
    resolves somewhere else without changing the spelling. `commonpath` over
    both real paths compares what the OS would actually touch.
    """
    root = os.path.realpath(directory)
    candidate = os.path.realpath(path)
    try:
        return os.path.commonpath([root, candidate]) == root
    except ValueError:
        # Different drives on Windows: no relative path between them.
        return False


def _references_named_in(directory: str) -> "tuple[set[str], set[str]]":
    """What the `.json` files directly in *directory* point at.

    Returns the archive filenames and the tool-result directory names they
    mention, read through the same spelling their writers use
    (`archive_layout.archive_names_in`). Read as text with `errors="ignore"`
    rather than parsed: a file that is not valid JSON any more still names the
    archive it was written against.
    """
    archives: set[str] = set()
    tool_results: set[str] = set()
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return archives, tool_results
    for entry in entries:
        if not entry.name.endswith(".json"):
            continue
        try:
            if not entry.is_file():
                continue
            with open(entry.path, encoding="utf-8", errors="ignore") as stream:
                content = stream.read()
                archives.update(archive_names_in(content))
                tool_results.update(tool_results_names_in(content))
        except OSError:
            continue
    return archives, tool_results


def _is_zrb_owned_history_entry(name: str) -> bool:
    """Whether *name*, a direct child of the history directory, is zrb's own.

    A conversation's live file ends in `.json`; backups and sub-agent
    transcripts, and verbatim archives, sit in their own dedicated, zrb-named
    subdirectories. Used both to create new entries owner-only and to narrow a
    pre-existing history directory without touching whatever else a
    user-configured path might already hold.
    """
    return name.endswith(".json") or name in (
        SUBAGENT_HISTORY_SUBDIR,
        ARCHIVE_DIR_NAME,
        BACKUP_DIR_NAME,
    )


class FileHistoryManager(AnyHistoryManager):
    def __init__(self, history_dir: str):
        self._history_dir = os.path.expanduser(history_dir)
        # LRU-ordered: most recently used entries at the end (see _evict_lru).
        self._cache: "OrderedDict[str, list[ModelMessage]]" = OrderedDict()
        # Cache sync time; None means no file existed at sync.
        self._cache_mtime: dict[str, float | None] = {}
        # Unsaved entries stay cached to avoid data loss.
        self._dirty: set[str] = set()
        # Prune expired auto-named conversations on the first save.
        self._has_pruned = False
        makedirs_owner_only(self._history_dir)
        # A history directory written before the private-mode rule keeps its
        # old modes; this narrows only zrb's own entries in it, once, and is a
        # no-op on every later call.
        tighten_once(self._history_dir, owned_entries=_is_zrb_owned_history_entry)

    @property
    def storage_dir(self) -> str:
        """The directory this manager stores conversation files in."""
        return self._history_dir

    def is_dirty(self, conversation_name: str) -> bool:
        """Whether *conversation_name* has in-memory updates not yet persisted."""
        return conversation_name in self._dirty

    def cache_sync_mtime(self, conversation_name: str) -> "float | None":
        """The on-disk mtime this conversation's cache entry was last synced
        to, or None if it has never been synced (or had no file at sync
        time)."""
        return self._cache_mtime.get(conversation_name)

    def load(self, conversation_name: str) -> "list[ModelMessage]":
        # lazy: heavy third-party
        from pydantic import ValidationError

        from zrb.llm.engine.agent.types import ModelMessagesTypeAdapter

        file_path, current_mtime = self._resolve_read_path(conversation_name)

        # Serve from cache only while the on-disk file hasn't changed since we
        # last synced. A differing mtime (incl. the file appearing/disappearing)
        # means the cache is stale and we must re-read — except for dirty
        # entries: their content exists only in memory and is NEWER than any
        # disk state, so an external write landing between update() and save()
        # must not make load() discard it.
        if conversation_name in self._cache and (
            conversation_name in self._dirty
            or self._cache_mtime.get(conversation_name) == current_mtime
        ):
            self._cache.move_to_end(conversation_name)
            return self._cache[conversation_name]

        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return []
                data = sanitize_history(json.loads(content))
                messages = ModelMessagesTypeAdapter.validate_python(data)
                self._cache[conversation_name] = messages
                self._cache.move_to_end(conversation_name)
                self._cache_mtime[conversation_name] = current_mtime
                self._evict_lru()
                return messages

        except ValidationError as e:
            zrb_print(
                f"Warning: Failed to load history for {conversation_name} even after cleanup: {e}",
                plain=True,
            )
            return []

        except (json.JSONDecodeError, OSError) as e:
            zrb_print(
                f"Warning: Failed to load history for {conversation_name}: {e}",
                plain=True,
            )
            return []

    def update(self, conversation_name: str, messages: "list[ModelMessage]"):
        self._cache[conversation_name] = messages
        self._cache.move_to_end(conversation_name)
        self._dirty.add(conversation_name)
        # Record the current file mtime as the sync point so a subsequent load()
        # against an unchanged file returns this in-memory update rather than
        # re-reading stale disk content.
        self._cache_mtime[conversation_name] = self._file_mtime(
            self._get_file_path(conversation_name)
        )
        self._evict_lru()

    def _evict_lru(self):
        """Drop clean least-recently-used entries beyond the cache bound."""
        while len(self._cache) > _MAX_CACHED_CONVERSATIONS:
            victim = next((k for k in self._cache if k not in self._dirty), None)
            if victim is None:
                return
            self._cache.pop(victim, None)
            self._cache_mtime.pop(victim, None)

    @staticmethod
    def _file_mtime(file_path: str) -> float | None:
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return None

    @staticmethod
    def _file_stat(file_path: str) -> "tuple[float, int] | None":
        """The file's mtime and size, or None when it cannot be read."""
        try:
            stat = os.stat(file_path)
        except OSError:
            return None
        return stat.st_mtime, stat.st_size

    def save(self, conversation_name: str, write_backup: bool = True):
        # lazy: heavy third-party
        from pydantic import ValidationError

        from zrb.llm.engine.agent.types import ModelMessagesTypeAdapter

        if conversation_name not in self._cache:
            return

        messages = self._cache[conversation_name]
        file_path = self._get_file_path(conversation_name)

        try:
            # pydantic-ai's type adapter union omits BinaryContent, so dumping one
            # warns even though serialization works.
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Pydantic serializer warnings",
                    category=UserWarning,
                )
                raw = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
            filtered_data = sanitize_history(raw)

            ModelMessagesTypeAdapter.validate_python(filtered_data)

            if not self._save_data_to_file(file_path, filtered_data):
                # Write failed (already logged by _save_data_to_file): keep the
                # entry dirty and its mtime unrefreshed so it's never mistaken
                # for safely persisted and evicted from the cache.
                return
            # Refresh the sync point so our own write doesn't look like an
            # out-of-band change on the next load().
            self._cache_mtime[conversation_name] = self._file_mtime(file_path)
            # Disk now matches the cache: the entry is evictable again.
            self._dirty.discard(conversation_name)
            if not self._has_pruned:
                self._has_pruned = True
                self._prune_expired(conversation_name)

            # Mid-turn checkpoints pass write_backup=False: a backup per tool
            # call would fill the history dir with near-duplicates.
            backup_retain = CFG.LLM_HISTORY_BACKUP_RETAIN
            if write_backup and backup_retain != 0:
                timestamp = datetime.now()
                backup_path = self._get_backup_file_path(conversation_name, timestamp)
                if backup_path:
                    self._save_data_to_file(backup_path, filtered_data)
                    if backup_retain > 0:
                        self._rotate_backups(conversation_name, keep=backup_retain)

        except ValidationError as e:
            zrb_print(
                f"Warning: Failed to save history for {conversation_name} due to validation error: {e}",
                plain=True,
            )

        except OSError as e:
            zrb_print(
                f"Error: Failed to save history for {conversation_name}: {e}",
                plain=True,
            )

    def rename(self, conversation_name: str, new_name: str) -> None:
        """Move one conversation's history file to *new_name* (ADR-0109).

        Sub-agent transcripts stay where they are: they hang off the
        conversation's key, which a rename keeps. Timestamped backups stay
        under the old name. For ordinary conversations only (auto-naming
        renames nothing else), so the legacy delegated-transcript path never
        applies.

        Raises `OSError`, leaving everything in place, when the unsaved
        history cannot be written, there is no saved history to move,
        *new_name* exists on disk or is open in memory, or the filesystem
        cannot hard-link. The target is
        created exclusively (`os.link`), so it is never overwritten, even by a
        concurrent writer."""
        self.save(conversation_name, write_backup=False)
        if conversation_name in self._dirty:
            raise OSError(
                f"Cannot rename '{conversation_name}': its unsaved history "
                "could not be written, so it stays under its current name."
            )
        source = self._get_file_path(conversation_name)
        target = self._get_file_path(new_name)
        if new_name in self._cache or new_name in self._dirty:
            raise OSError(
                f"Cannot rename '{conversation_name}' to '{new_name}': that "
                "conversation is already open in memory and would be overwritten."
            )
        if not os.path.exists(source):
            raise OSError(
                f"Cannot rename '{conversation_name}': it has no saved history "
                "to move, so it keeps its current name."
            )
        try:
            os.link(source, target)
        except FileExistsError as e:
            raise OSError(
                f"Cannot rename '{conversation_name}' to '{new_name}': "
                f"{target} already exists and would be overwritten."
            ) from e
        try:
            os.unlink(source)
        except OSError as e:
            try:
                os.unlink(target)  # undo the link, so nothing is duplicated
            except OSError:
                raise OSError(
                    f"Renaming '{conversation_name}' left both {source} and "
                    f"{target} in place; remove the one you do not want."
                ) from e
            raise
        self._cache.pop(conversation_name, None)
        self._cache_mtime.pop(conversation_name, None)
        self._dirty.discard(conversation_name)

    def search(
        self,
        keyword: str,
        include_delegated: bool = True,
        include_empty: bool = True,
    ) -> list[str]:
        """Conversation names matching *keyword*, newest first among equals.

        `include_delegated=False` omits sub-agent transcripts.
        `include_empty=False` omits conversations that hold no messages — a
        name reserved and then never used leaves a file behind for every such
        attempt, so they otherwise crowd out the ones with something to load.
        """
        if not os.path.exists(self._history_dir):
            return []

        matches = []
        # Delegated transcripts live in subagent/{agent_type}/ subdirectories;
        # scan those alongside the history root (which may still hold legacy
        # flat delegated files) so search sees every conversation.
        directories = (
            subagent_history_directories(self._history_dir)
            if include_delegated
            else [self._history_dir]
        )
        for directory in directories:
            try:
                filenames = os.listdir(directory)
            except OSError:
                continue
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue

                conversation_name = filename[:-5]

                is_match, score = fuzzy_match(conversation_name, keyword)
                if not is_match:
                    continue
                file_stat = self._file_stat(os.path.join(directory, filename))
                if (
                    not include_empty
                    and file_stat is not None
                    and file_stat[1] <= _EMPTY_HISTORY_MAX_BYTES
                ):
                    continue
                mtime = file_stat[0] if file_stat is not None else None
                matches.append((conversation_name, score, mtime or 0.0))

        # Sort by fuzzy score (lower is better), then most-recently-modified
        # first. With an empty keyword every score is 0.0, so the effective
        # order is mtime-descending — recent sessions surface first in `/load`.
        matches.sort(key=lambda x: (x[1], -x[2]))

        return [m[0] for m in matches]

    def _resolve_read_path(self, conversation_name: str) -> tuple[str, float | None]:
        """Return the conversation path and its mtime, with legacy fallback."""
        file_path = self._get_file_path(conversation_name)
        mtime = self._file_mtime(file_path)
        if mtime is not None:
            return file_path, mtime
        legacy_path = self._get_legacy_file_path(conversation_name)
        if os.path.exists(legacy_path):
            return legacy_path, self._file_mtime(legacy_path)
        return file_path, None

    def _get_legacy_file_path(self, conversation_name: str) -> str:
        """The pre-`subagent/`-layout location for a delegated transcript:
        flat in the history root, next to ordinary sessions."""
        return os.path.join(
            self._history_dir, f"{safe_segment(conversation_name)}.json"
        )

    def _get_file_path(self, conversation_name: str) -> str:
        safe_name = safe_segment(conversation_name)
        delegated = parse_delegated_session(safe_name)
        if delegated is not None:
            # Delegated sub-agent transcripts live in their own per-agent-type
            # directory so a history listing/backup/prune never mixes them
            # with ordinary sessions (and vice versa).
            return os.path.join(
                self._history_dir,
                SUBAGENT_HISTORY_SUBDIR,
                safe_segment(delegated[1]),
                f"{safe_name}.json",
            )
        return os.path.join(self._history_dir, f"{safe_name}.json")

    def _get_backup_directory(self, conversation_name: str) -> str:
        """The directory holding *conversation_name*'s backups, or ``""``.

        Keyed by the sanitized name, so two conversations never share a backup
        set — including one whose name carries a timestamp, which the old
        layout folded into the conversation it looked like a backup of.

        Empty means the name would point the backup outside the history tree
        (`safe_segment` turns a path into one filename-safe segment, and the
        dot segments `"."`/`".."` are refused outright). The containment check
        is the second line of defence: `safe_segment` strips separators, so a
        symlinked `backups/` entry is what could still resolve elsewhere.
        """
        key = safe_segment(conversation_name)
        if key in (".", ".."):
            return ""
        backup_root = os.path.join(self._history_dir, BACKUP_DIR_NAME)
        directory = os.path.join(backup_root, key)
        if not _is_within(backup_root, directory):
            zrb_print(
                f"Warning: Refusing to write history backups outside "
                f"{backup_root}: {directory}",
                plain=True,
            )
            return ""
        return directory

    def _contained_backup_path(self, directory: str, filename: str) -> str:
        """*filename* inside *directory*, or ``""`` if it escapes it."""
        path = os.path.join(directory, filename)
        if not _is_within(directory, path):
            zrb_print(
                f"Warning: Refusing to write a history backup outside "
                f"{directory}: {path}",
                plain=True,
            )
            return ""
        return path

    def _get_backup_file_path(self, conversation_name: str, timestamp: datetime) -> str:
        """Return a conflict-free timestamped backup path, or ``""``.

        An unsafe or escaping name yields no path, so the save continues
        without a backup rather than writing one outside the backup tree.
        """
        directory = self._get_backup_directory(conversation_name)
        if not directory:
            return ""
        ts_str = timestamp.strftime("%Y-%m-%d-%H-%M-%S")
        candidate = self._contained_backup_path(directory, f"{ts_str}.json")
        if not candidate or not os.path.exists(candidate):
            return candidate
        for counter in range(1, 1001):
            candidate = self._contained_backup_path(
                directory, f"{ts_str}-{counter}.json"
            )
            if not candidate or not os.path.exists(candidate):
                return candidate
        # Fallback to using microseconds: two backups a second apart can
        # share a name only under a clock that does not advance.
        return self._contained_backup_path(
            directory, f"{ts_str}-{timestamp.strftime('%f')}.json"
        )

    def _save_data_to_file(self, file_path: str, data: Any) -> bool:
        """Atomically save filtered data; return whether the write succeeded.

        The temporary file gets a unique name from `tempfile.mkstemp` in the
        destination directory, so two concurrent saves of the same
        conversation never open the same inode and publish each other's bytes
        while both report success. `mkstemp` creates it owner-only and with
        `O_EXCL`, so a symlink planted at its path is refused rather than
        followed; `os.replace` then carries that mode onto *file_path* itself,
        whatever mode it had before. `makedirs_owner_only` can raise
        `PermissionError` (an `OSError`) for a symlinked directory, caught by
        the same handler as any other failed write: a transcript this call
        cannot place safely is a failed save, not a crash.
        """
        directory = os.path.dirname(file_path)
        tmp_path: "str | None" = None
        try:
            makedirs_owner_only(directory)
            descriptor, tmp_path = tempfile.mkstemp(
                dir=directory, prefix=".zrb-history-", suffix=".tmp"
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, file_path)
            tmp_path = None
            return True
        except OSError as e:
            zrb_print(f"Error: Failed to save history to {file_path}: {e}", plain=True)
            return False
        finally:
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _prune_expired(self, current: str) -> None:
        """Prune expired auto-named root histories; never fail the triggering save."""
        retention = parse_duration(CFG.LLM_HISTORY_RETENTION or "")
        if retention <= 0:
            return
        cutoff = time.time() - retention
        protected = {safe_segment(current), *map(safe_segment, self._dirty)}
        try:
            entries = list(os.scandir(self._history_dir))
        except OSError:
            return
        for entry in entries:
            if not entry.name.endswith(".json"):
                continue
            base = entry.name[: -len(".json")]
            if (
                not has_random_name_prefix(base)
                or parse_delegated_session(base) is not None
                or base in protected
            ):
                continue
            try:
                if entry.is_file() and entry.stat().st_mtime < cutoff:
                    os.remove(entry.path)
                    self._remove_backups(base)
            except OSError:
                continue
        self._prune_orphan_backups(cutoff, protected)
        self._prune_unreferenced_archives(cutoff, current)

    def _remove_backups(self, conversation_name: str) -> None:
        """Drop the backup set that belonged to a pruned conversation."""
        directory = self._get_backup_directory(conversation_name)
        if not directory:
            return
        shutil.rmtree(directory, ignore_errors=True)

    def _prune_orphan_backups(self, cutoff: float, protected: set[str]) -> None:
        """Drop a stale backup set whose live transcript is gone.

        Retention walks the live files, so it can only collect a backup set
        through the conversation that owns it. A transcript renamed or removed
        outside this manager — another process, a manual `mv`, a crash between
        the unlink and the cleanup — leaves `backups/<name>/` behind with no
        live file to reach it from, and nothing would ever collect it. Such a
        set goes here, on the same cutoff, and its own newest backup decides
        the age so a set written moments ago for a save still in flight is kept.

        Only auto-named sets are collected: retention never prunes a
        conversation the user named, so its backup set is not retention's to
        delete either. Delegated transcripts are left to the count-based
        sub-agent pruning that owns them.
        """
        for directory in self._backup_directories():
            name = os.path.basename(directory)
            if (
                not has_random_name_prefix(name)
                or parse_delegated_session(name) is not None
                or name in protected
            ):
                continue
            if os.path.exists(self._get_file_path(name)):
                continue
            if _newest_mtime(directory) >= cutoff:
                continue
            shutil.rmtree(directory, ignore_errors=True)

    def _prune_unreferenced_archives(self, cutoff: float, current: str) -> None:
        """Delete archives and tool-result directories nothing points at.

        An archive is the only copy of the text a summary dropped, so it goes
        only when nothing points at it: no history file in this directory — the
        live one or a backup of it — carries its pointer. Age is required too,
        so an archive written moments ago for a conversation whose history has
        not been saved yet is never collected. A conversation the user named is
        kept by retention, so its archive is too, and a session with no history
        file of its own (the opening-message key) survives as long as the
        summary that names it does.

        A compaction can write the archive and leave the conversation dirty —
        its save deferred or still pending — well before this call's own
        trigger, for a *different* conversation, runs the one-time prune: that
        archive would otherwise be the only unreferenced-looking one on disk,
        even though an in-memory summary still points to it. Every dirty
        conversation is kept for exactly the same reason `current` already is,
        not only the one triggering this save.

        Tool-result directories are collected on the same rule, but they do not
        depend on an archive existing: a conversation can prune a result long
        before it ever compacts, and retention would otherwise never see the
        directory at all.
        """
        archives_dir = os.path.join(self._history_dir, ARCHIVE_DIR_NAME)
        try:
            names = os.listdir(archives_dir)
        except OSError:
            return
        archives = [n for n in names if n.endswith(".md") and not n.startswith(".")]
        tool_result_dirs = [
            n
            for n in names
            if n.endswith(TOOL_RESULTS_DIR_SUFFIX) and not n.startswith(".")
        ]
        if not archives and not tool_result_dirs:
            return
        referenced_archives, referenced_tool_results = self._referenced_artifacts()
        # Live even before its history file lands: the session being saved,
        # and any other conversation whose own save is still pending.
        live_keys = {safe_segment(name) for name in (current, *self._dirty)}
        self._remove_unreferenced_archives(
            archives_dir, archives, referenced_archives, live_keys, cutoff
        )
        self._remove_unreferenced_tool_results(
            archives_dir, tool_result_dirs, referenced_tool_results, live_keys, cutoff
        )

    def _remove_unreferenced_archives(
        self,
        archives_dir: str,
        archives: "list[str]",
        referenced: "set[str]",
        live_keys: "set[str]",
        cutoff: float,
    ) -> None:
        """Unlink each archive (and its tool results) nothing references."""
        keep = {f"{key}.md" for key in live_keys}
        for name in archives:
            if name in referenced or name in keep:
                continue
            path = os.path.join(archives_dir, name)
            if not _is_older_than(path, cutoff):
                continue
            try:
                os.remove(path)
            except OSError:
                continue
            try:
                os.remove(archive_lock_path(path))
            except OSError:
                pass
            # The directory beside the archive is not removed here. It has its
            # own pass because it can outlive the archive: a transcript may
            # still carry a PRUNED TOOL RESULT pointer to it after the summary
            # stopped naming the archive. That pass decides by reference and
            # age; deleting in both places would bypass the reference check.

    def _remove_unreferenced_tool_results(
        self,
        archives_dir: str,
        names: "list[str]",
        referenced: "set[str]",
        live_keys: "set[str]",
        cutoff: float,
    ) -> None:
        """Remove each tool-result directory nothing references, when old.

        The directory's own mtime is not enough to call it old: a conversation
        reusing its directory writes a new result into it, and that does not
        always move the directory's timestamp. The newest file inside decides,
        so a freshly spilled result is never collected before the transcript
        that will name it is saved.
        """
        for name in names:
            key = name[: -len(TOOL_RESULTS_DIR_SUFFIX)]
            if name in referenced or key in live_keys:
                continue
            path = os.path.join(archives_dir, name)
            if _newest_mtime(path) >= cutoff:
                continue
            shutil.rmtree(path, ignore_errors=True)

    def _backup_directories(self) -> "list[str]":
        """Every per-conversation directory under `backups/`."""
        backup_root = os.path.join(self._history_dir, BACKUP_DIR_NAME)
        try:
            with os.scandir(backup_root) as entries:
                return [
                    entry.path
                    for entry in entries
                    if entry.is_dir(follow_symlinks=False)
                ]
        except OSError:
            return []

    def _referenced_artifacts(self) -> "tuple[set[str], set[str]]":
        """What any transcript this manager can write points at.

        Returns the archive filenames and the tool-result directory names, so
        one read of every transcript answers both questions. Every directory a
        transcript can live in, not just the root: a sub-agent's summary points
        at the same shared `verbatim/` directory as its parent's, so a pointer
        inside `subagent/<agent-type>/` is just as load-bearing. Backups live
        under `backups/<conversation>/` and are read here too, because a backup
        still names the archive it was written against. Legacy backups written
        flat in the root before that layout are read by the root pass.
        """
        archives: set[str] = set()
        tool_results: set[str] = set()
        directories = subagent_history_directories(self._history_dir)
        directories.extend(self._backup_directories())
        for directory in directories:
            found_archives, found_tool_results = _references_named_in(directory)
            archives.update(found_archives)
            tool_results.update(found_tool_results)
        return archives, tool_results

    def _rotate_backups(self, conversation_name: str, keep: int) -> None:
        """Keep the *keep* newest backups for *conversation_name*.

        Only the conversation's own backup directory is listed, so a live
        transcript — however its name is spelled — is never a rotation
        candidate.
        """
        if keep < 0:
            return
        directory = self._get_backup_directory(conversation_name)
        if not directory:
            return
        try:
            names = [name for name in os.listdir(directory) if name.endswith(".json")]
        except OSError:
            return
        if len(names) <= keep:
            return
        # Sort by filename descending (lexicographic = chronological for ISO-8601
        # timestamps). More deterministic than mtime on filesystems with coarse
        # granularity (FAT32, Docker overlayfs).
        names.sort(reverse=True)
        for name in names[keep:]:
            try:
                os.remove(os.path.join(directory, name))
            except OSError:
                continue
