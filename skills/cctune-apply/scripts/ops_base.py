"""Shared ground for every op: the result record, path safety and text reading."""
import difflib
import hashlib
import os
from dataclasses import dataclass, field

from plan_schema import PlanError
from redact import redact

SYSTEM_PREFIXES = ("/etc", "/usr", "/bin", "/sbin", "/lib", "/boot", "/var", "/opt", "/root", "/sys",
                   "/proc", "/dev", "/run", "/srv", "/mnt")
# Relative to $HOME. Code that runs at login or on every shell, and credential stores.
REFUSED_USER_PATHS = (".bashrc", ".zshrc", ".zprofile", ".profile", ".bash_profile", ".ssh",
                      ".config/autostart", ".config/systemd", ".gnupg", ".aws", ".kube",
                      ".claude/tune")  # plans and backups are the engine's own files
ALLOWED_USER_ROOTS = (".claude", ".agents", ".config/claude")
CREDENTIAL_STORES = (".ssh", ".gnupg", ".aws", ".kube")  # never read, never written
RC_BASENAMES = (".bashrc", ".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout", ".profile",
                ".bash_profile", ".bash_login", ".bash_logout", ".bash_aliases")
JSON_INDENT = 2


class ReadError(Exception):
    """A target could not be read as UTF-8 text (missing files are not errors)."""


@dataclass
class OpResult:
    kind: str
    path: str = ""
    before: str = None       # None = file did not exist
    after: str = None        # None = file removed (or symlink target)
    changed: bool = False
    note: str = ""
    symlink_target: str = ""
    manual_text: str = ""
    errors: list = field(default_factory=list)
    mode: int = None         # file_create: mode to set after writing
    summary_only: bool = False  # file_remove: never print the content, only size and hash

    def diff(self):
        if self.kind == "manual":
            return self.manual_text
        if self.kind == "symlink":
            return f"{self.path} -> {self.symlink_target}"
        if not self.changed:
            return ""
        if self.summary_only:
            return self._summary()
        # Never print a credential value, even in a diff that deletes it.
        a = redact(self.before or "").splitlines(keepends=True)
        b = redact(self.after or "").splitlines(keepends=True)
        return "".join(difflib.unified_diff(a, b, f"a{self.path}", f"b{self.path}", n=2))

    def _summary(self):
        if self.symlink_target:
            return f"removes symlink {self.path} -> {self.symlink_target}"
        text = self.before or ""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"removes {self.path}: {len(text.splitlines())} line(s), sha256 {digest}"


def expand(path):
    return os.path.realpath(os.path.expanduser(path))


def _home():
    return os.path.realpath(os.path.expanduser("~"))


def _under(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def _under_any_case(path, root):
    """Refusals compare case-insensitively: on a case-insensitive file system ~/.SSH is ~/.ssh."""
    return _under(path.casefold(), root.casefold())


def _in_git_worktree(real):
    """True for a file inside a repository whose root is neither $HOME nor a dot-directory."""
    home = _home()
    probe = os.path.dirname(real)
    while probe and probe != "/":
        if os.path.isdir(os.path.join(probe, ".git")):
            if not _under(probe, home):
                return True  # a repo outside $HOME (system prefixes were refused already)
            rel = os.path.relpath(probe, home)
            return rel != "." and not rel.startswith(".")  # not $HOME itself, not under a dot-dir
        probe = os.path.dirname(probe)
    return False


def check_path(path):
    """Return the absolute (unresolved) path a plan may write, or raise PlanError saying why not.

    The link location and, when it resolves, the link target are both validated, so ops see
    the symlink itself and can refuse or remove it while nothing reaches a forbidden file.
    """
    return _validate(path, _refuse_write_lexical, _validate_write_real)


def check_read_path(path):
    """Return the absolute path a check may read, or raise PlanError saying why not.

    Reads cover the write roots plus two files checks must see: ~/.claude.json (an entry was
    removed) and the shell startup files in $HOME (the secrets file is sourced). Nothing else:
    a check result is a one-bit oracle, so it must not reach ~/.netrc or any other secret.
    """
    return _validate(path, _refuse_read_lexical, _validate_read_real)


def _validate(path, refuse_lexical, validate_real):
    lexical = os.path.abspath(os.path.expanduser(path))
    refuse_lexical(lexical)
    if os.path.islink(lexical):
        validate_real(os.path.join(os.path.realpath(os.path.dirname(lexical)), os.path.basename(lexical)))
        if os.path.exists(lexical):
            validate_real(os.path.realpath(lexical))
    else:
        validate_real(os.path.realpath(lexical))
    return lexical


def _refuse_write_lexical(path):
    """Refusals that hold for the path as written, before any symlink is resolved."""
    home = _home()
    _refuse_read_lexical(path)
    if os.path.basename(path).casefold() in RC_BASENAMES:
        raise PlanError(f"shell startup file refused: {path}")
    if path.casefold() == os.path.join(home, ".claude.json").casefold():
        raise PlanError("~/.claude.json is rewritten by running sessions; use `claude mcp add/remove` or edit with all sessions closed")
    if any(_under_any_case(path, os.path.join(home, rel)) for rel in REFUSED_USER_PATHS):
        raise PlanError(f"login-time or credential path refused: {path}")


def _refuse_read_lexical(path):
    home = _home()
    if any(part.casefold() == ".git" for part in path.split("/")):
        raise PlanError(f"git metadata refused: {path}")
    if any(_under_any_case(path, os.path.join(home, rel)) for rel in CREDENTIAL_STORES):
        raise PlanError(f"credential path refused: {path}")


def _startup_link_targets(home):
    """Real paths that a shell startup file in $HOME is a symlink to (dotfiles repos)."""
    targets = set()
    for name in RC_BASENAMES:
        candidate = os.path.join(home, name)
        if os.path.islink(candidate):
            targets.add(os.path.realpath(candidate))
    return targets


def _validate_write_real(real):
    _refuse_write_lexical(real)
    home = _home()
    if real in _startup_link_targets(home):
        raise PlanError(f"shell startup file (via a $HOME symlink) refused: {real}")
    if any(_under(real, os.path.join(home, rel)) for rel in ALLOWED_USER_ROOTS):
        return
    _refuse_system(real)
    if _in_git_worktree(real):
        return
    raise PlanError(f"path outside ~/.claude, ~/.agents, ~/.config/claude or a git work tree: {real}")


def _validate_read_real(real):
    _refuse_read_lexical(real)
    home = _home()
    if any(_under(real, os.path.join(home, rel)) for rel in ALLOWED_USER_ROOTS):
        return
    if real == os.path.join(home, ".claude.json") or real in _home_startup_files(home):
        return
    _refuse_system(real)
    if _in_git_worktree(real):
        return
    raise PlanError(f"path outside the read allowlist (~/.claude, ~/.agents, ~/.config/claude, "
                    f"~/.claude.json, shell startup files, a git work tree): {real}")


def _home_startup_files(home):
    return {os.path.join(home, name) for name in RC_BASENAMES}


def _refuse_system(real):
    if any(_under(real, pre) for pre in SYSTEM_PREFIXES):
        raise PlanError(f"system path refused: {real}")


def target_kind(path):
    """missing | file | symlink | dangling-symlink | dir, without following the final link."""
    if os.path.islink(path):
        return "symlink" if os.path.exists(path) else "dangling-symlink"
    if not os.path.lexists(path):
        return "missing"
    return "dir" if os.path.isdir(path) else "file"


def read_text(path, overlay=None):
    """Current text of `path` (None when missing), preferring the in-item overlay of earlier ops."""
    if overlay is not None and path in overlay:
        return overlay[path]
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise ReadError(f"cannot read {path}: {exc}") from exc
