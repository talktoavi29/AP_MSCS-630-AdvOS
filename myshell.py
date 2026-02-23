from __future__ import annotations

import getpass
import hashlib
import json
import os
import shlex
import signal
import subprocess
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scheduler_simulation import SchedulerSim  # Deliverable 2

def win() -> bool:
    return os.name == "nt"


def err(msg) -> None:
    print("Error:", msg)


def clr() -> None:
    os.system("cls" if win() else "clear")


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def abs_path(p: str) -> str:
    """Normalize to an absolute path for permission tracking."""
    return str(Path(p).expanduser().resolve())

USERS_FILE = ".myshell_users.json"
PERMS_FILE = ".myshell_perms.json"


@dataclass
class User:
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role.lower() == "admin"


class SecurityManager:
    """Simulated authentication + file permissions."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or os.getcwd()).resolve()
        self.users_path = self.base_dir / USERS_FILE
        self.perms_path = self.base_dir / PERMS_FILE
        self._users: Dict[str, Dict[str, str]] = {}
        self._perms: Dict[str, Dict[str, str]] = {}
        self.current_user: Optional[User] = None
        self._load_or_init()

    def _load_or_init(self) -> None:
        if self.users_path.exists():
            self._users = json.loads(self.users_path.read_text(encoding="utf-8"))
        else:

            self._users = {
                "admin": {"password_hash": sha256_hex("admin123"), "role": "admin"},
                "user": {"password_hash": sha256_hex("user123"), "role": "user"},
            }
            self._save_users()

        if self.perms_path.exists():
            self._perms = json.loads(self.perms_path.read_text(encoding="utf-8"))
        else:
            self._perms = {}
            self._save_perms()

    def _save_users(self) -> None:
        self.users_path.write_text(json.dumps(self._users, indent=2), encoding="utf-8")

    def _save_perms(self) -> None:
        self.perms_path.write_text(json.dumps(self._perms, indent=2), encoding="utf-8")

    def login(self) -> None:
        """Interactive login loop."""
        while True:
            print("\n=== MyShell Login ===")
            print("Tip: default users are admin/admin123 and user/user123")
            uname = input("Username: ").strip()
            pwd = getpass.getpass("Password: ")
            if self._check_credentials(uname, pwd):
                role = self._users[uname]["role"]
                self.current_user = User(username=uname, role=role)
                print(f"Logged in as {uname} ({role}).")
                return
            print("Invalid username/password. Try again.")

    def logout(self) -> None:
        self.current_user = None

    def _check_credentials(self, username: str, password: str) -> bool:
        u = self._users.get(username)
        if not u:
            return False
        return u["password_hash"] == sha256_hex(password)

    def add_user(self, username: str, password: str, role: str) -> None:
        if username in self._users:
            raise ValueError("user already exists")
        if role.lower() not in {"admin", "user"}:
            raise ValueError("role must be admin or user")
        self._users[username] = {"password_hash": sha256_hex(password), "role": role.lower()}
        self._save_users()

    def set_password(self, username: str, new_password: str) -> None:
        if username not in self._users:
            raise ValueError("no such user")
        self._users[username]["password_hash"] = sha256_hex(new_password)
        self._save_users()

    def ensure_perm_record(self, path: str, owner: Optional[str] = None, mode: str = "rw-r--") -> None:
        ap = abs_path(path)
        if ap not in self._perms:
            self._perms[ap] = {"owner": owner or self._require_user().username, "mode": mode}
            self._save_perms()

    def chmod(self, path: str, mode: str) -> None:
        if len(mode) != 6 or any(c not in "rwx-" for c in mode):
            raise ValueError("mode must be 6 chars like rw-r-- or rwxr-x")
        ap = abs_path(path)
        self.ensure_perm_record(ap)
        self._perms[ap]["mode"] = mode
        self._save_perms()

    def chown(self, path: str, new_owner: str) -> None:
        if new_owner not in self._users:
            raise ValueError("no such user")
        ap = abs_path(path)
        self.ensure_perm_record(ap)
        self._perms[ap]["owner"] = new_owner
        self._save_perms()

    def lsperm(self, path: str) -> str:
        ap = abs_path(path)
        if ap not in self._perms:
            return "(no record)"
        rec = self._perms[ap]
        return f"owner={rec['owner']} mode={rec['mode']} path={ap}"

    def check(self, path: str, action: str) -> bool:
        """Check r/w/x for current user."""
        u = self._require_user()
        if u.is_admin:
            return True

        ap = abs_path(path)
        rec = self._perms.get(ap)
        if rec is None:
            self.ensure_perm_record(ap, owner=u.username, mode="rw-r--")
            rec = self._perms[ap]

        mode = rec["mode"]
        owner = rec["owner"]
        owner_bits = mode[0:3]
        other_bits = mode[3:6]
        bits = owner_bits if owner == u.username else other_bits

        want = action.lower()
        if want == "r":
            return bits[0] == "r"
        if want == "w":
            return bits[1] == "w"
        if want == "x":
            return bits[2] == "x"
        raise ValueError("action must be r/w/x")

    def _require_user(self) -> User:
        if not self.current_user:
            raise RuntimeError("not logged in")
        return self.current_user

class MemoryManager:
    """Simple paging simulator: frames hold (pid,page)."""

    def __init__(self, frames: int = 4, policy: str = "FIFO"):
        self.frames_total = max(1, int(frames))
        self.page_faults = 0
        self.frames: List[Tuple[int, int]] = []
        self.policy = "FIFO"
        self._fifo = deque()
        self._lru = OrderedDict() 
        self.set_policy(policy)

    def set_policy(self, policy: str) -> None:
        policy = policy.upper()
        if policy not in {"FIFO", "LRU"}:
            raise ValueError("policy must be FIFO or LRU")
        self.policy = policy
        self.page_faults = 0
        self.frames.clear()
        self._fifo.clear()
        self._lru.clear()

    def access(self, pid: int, page: int) -> None:
        key = (pid, page)
        if key in self.frames:
            print(f"HIT  -> Process {pid} Page {page}")
            if self.policy == "LRU":
                self._lru.move_to_end(key)
            return

        self.page_faults += 1
        print(f"FAULT -> Process {pid} Page {page}")

        if len(self.frames) >= self.frames_total:
            self._replace()

        self.frames.append(key)
        if self.policy == "FIFO":
            self._fifo.append(key)
        else:
            self._lru[key] = None

    def _replace(self) -> None:
        if self.policy == "FIFO":
            victim = self._fifo.popleft()
        else:
            victim, _ = self._lru.popitem(last=False)
        try:
            self.frames.remove(victim)
        except ValueError:
            pass
        print(f"REPLACE -> Evicted {victim}")

    def status(self) -> None:
        print("\nFrames:")
        for f in self.frames:
            print(f)
        print("Page Faults:", self.page_faults)
class ProducerConsumerDemo:
    def __init__(self, buffer_size: int = 5):
        import threading
        from queue import Queue

        self.threading = threading
        self.Queue = Queue

        self.buffer_size = buffer_size
        self.buffer = Queue(maxsize=buffer_size)
        self.mutex = threading.Semaphore(1)
        self.empty = threading.Semaphore(buffer_size)
        self.full = threading.Semaphore(0)

    def _producer(self, items: int = 6, delay: float = 0.4):
        for i in range(items):
            self.empty.acquire()
            self.mutex.acquire()
            item = f"item-{i}"
            self.buffer.put(item)
            print("Produced:", item)
            self.mutex.release()
            self.full.release()
            time.sleep(delay)

    def _consumer(self, items: int = 6, delay: float = 0.6):
        for _ in range(items):
            self.full.acquire()
            self.mutex.acquire()
            item = self.buffer.get()
            print("Consumed:", item)
            self.mutex.release()
            self.empty.release()
            time.sleep(delay)

    def run(self, items: int = 6):
        p = self.threading.Thread(target=self._producer, args=(items,))
        c = self.threading.Thread(target=self._consumer, args=(items,))
        p.start()
        c.start()
        p.join()
        c.join()

job_table: Dict[int, Dict[str, object]] = {}
job_counter = 1


def refresh_jobs() -> None:
    for jid in list(job_table.keys()):
        p = job_table[jid]["proc"]
        code = p.poll()
        if code is not None:
            job_table[jid]["status"] = f"done (exit={code})"


def show_jobs() -> None:
    refresh_jobs()
    if not job_table:
        print("(no jobs)")
        return
    for jid, info in job_table.items():
        print(f"[{jid}] pid={info['pid']} status={info['status']} cmd={info['cmd']}")


def fg_cmd(args: List[str]) -> None:
    if not args:
        err("fg needs job id")
        return
    try:
        jid = int(args[0])
        if jid not in job_table:
            err("job not found")
            return

        refresh_jobs()
        p = job_table[jid]["proc"]
        if p.poll() is not None:
            err("job already finished")
            return

        print("Foreground:", job_table[jid]["cmd"])
        job_table[jid]["status"] = "foreground"
        exit_code = p.wait()
        job_table[jid]["status"] = f"done (exit={exit_code})"
    except Exception as e:
        err(e)


def bg_cmd(args: List[str]) -> None:
    if not args:
        err("bg needs job id")
        return
    try:
        jid = int(args[0])
        if jid not in job_table:
            err("job not found")
            return

        refresh_jobs()
        p = job_table[jid]["proc"]
        if p.poll() is not None:
            err("job already finished")
            return

        if not win():
            try:
                os.kill(job_table[jid]["pid"], signal.SIGCONT)
            except Exception:
                pass

        job_table[jid]["status"] = "running"
        print("Background:", job_table[jid]["cmd"])
    except Exception as e:
        err(e)


def start_process(tokens: List[str], background: bool) -> None:
    global job_counter
    try:
        p = subprocess.Popen(tokens)
        if background:
            jid = job_counter
            job_counter += 1
            job_table[jid] = {"pid": p.pid, "proc": p, "cmd": " ".join(tokens), "status": "running"}
            print(f"Started job [{jid}] pid={p.pid}")
        else:
            p.wait()
    except FileNotFoundError:
        err("command not found: " + tokens[0])
    except Exception as e:
        err(e)


def do_cd(args: List[str]) -> None:
    try:
        os.chdir(os.path.expanduser("~") if len(args) == 0 else args[0])
    except Exception as e:
        err(e)


def do_pwd(_: List[str]) -> str:
    return os.getcwd() + "\n"


def do_echo(args: List[str]) -> str:
    return " ".join(args) + "\n"


def do_ls(args: List[str]) -> str:
    target = args[0] if args else "."
    try:
        items = os.listdir(target)
        return "\n".join(items) + ("\n" if items else "")
    except Exception as e:
        return f"Error: {e}\n"


def do_cat(args: List[str], sec: SecurityManager) -> str:
    if not args:
        return "Error: cat needs a file name\n"
    fp = args[0]
    if not sec.check(fp, "r"):
        return "Error: permission denied (read)\n"
    try:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}\n"


def do_mkdir(args: List[str], sec: SecurityManager) -> str:
    if not args:
        return "Error: mkdir needs a directory name\n"
    d = args[0]
    if not sec.check(d, "w"):
        return "Error: permission denied (write)\n"
    try:
        os.makedirs(d, exist_ok=True)
        sec.ensure_perm_record(d, mode="rwxr-x")
        return ""
    except Exception as e:
        return f"Error: {e}\n"


def do_rmdir(args: List[str], sec: SecurityManager) -> str:
    if not args:
        return "Error: rmdir needs a directory name\n"
    d = args[0]
    if not sec.check(d, "w"):
        return "Error: permission denied (write)\n"
    try:
        os.rmdir(d)
        return ""
    except Exception as e:
        return f"Error: {e}\n"


def do_rm(args: List[str], sec: SecurityManager) -> str:
    if not args:
        return "Error: rm needs a file name\n"
    fp = args[0]
    if not sec.check(fp, "w"):
        return "Error: permission denied (write)\n"
    try:
        os.remove(fp)
        return ""
    except Exception as e:
        return f"Error: {e}\n"


def do_touch(args: List[str], sec: SecurityManager) -> str:
    if not args:
        return "Error: touch needs a file name\n"
    name = args[0]
    if not sec.check(name, "w"):
        return "Error: permission denied (write)\n"
    try:
        if not os.path.exists(name):
            open(name, "w").close()
        os.utime(name, None)
        sec.ensure_perm_record(name, mode="rw-r--")
        return ""
    except Exception as e:
        return f"Error: {e}\n"


def do_kill(args: List[str]) -> str:
    if not args:
        return "Error: kill needs a pid\n"
    try:
        pid = int(args[0])
        os.kill(pid, signal.SIGTERM)
        return f"Killed {pid}\n"
    except Exception as e:
        return f"Error: {e}\n"

def split_pipeline(line: str) -> List[str]:
    """Split by | but respect quotes."""
    out: List[str] = []
    current: List[str] = []
    in_single = False
    in_double = False
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "|" and not in_single and not in_double:
            out.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    out.append("".join(current).strip())
    return [p for p in out if p]


def builtin_grep(args: List[str], input_data: Optional[str]) -> str:
    if not args:
        return "Error: grep needs a pattern\n"
    pat = args[0]
    data = input_data or ""
    lines = data.splitlines()
    out = [ln for ln in lines if pat in ln]
    return "\n".join(out) + ("\n" if out else "")


def builtin_sort(args: List[str], input_data: Optional[str]) -> str:
    data = input_data or ""
    lines = data.splitlines()
    lines.sort()
    return "\n".join(lines) + ("\n" if lines else "")


def run_pipeline(stages: List[List[str]], sec: SecurityManager) -> None:
    input_data: Optional[str] = None
    for i, tokens in enumerate(stages):
        output_data = run_single(tokens, sec, input_data=input_data)
        input_data = output_data
        if i == len(stages) - 1:
            print(output_data, end="")

sched = SchedulerSim()
mem = MemoryManager(frames=4, policy="FIFO")
pc_demo = ProducerConsumerDemo(buffer_size=5)
secman = SecurityManager(base_dir=os.getcwd())


def print_help() -> None:
    print("\n=== Built-in Commands ===")
    print("exit                         quit the shell")
    print("cd [path]                     change directory")
    print("pwd                           print working directory")
    print("echo <text>                   print text")
    print("clear                         clear the screen")
    print("ls [path]                     list directory")
    print("cat <file>                    print file contents")
    print("mkdir <dir>                   create directory")
    print("rmdir <dir>                   remove empty directory")
    print("rm <file>                     delete file")
    print("touch <file>                  create/update file timestamp")
    print("kill <pid>                    terminate process by pid")
    print("jobs                          show background jobs")
    print("fg <job_id>                   bring job to foreground")
    print("bg <job_id>                   resume job in background")
    print("\n=== Deliverable 2: Scheduler Simulation ===")
    print("addproc <name> <burst> <priority> [arrival]")
    print("psim                          list simulated processes")
    print("sched_rr <quantum> [sleep]    run round-robin scheduler")
    print("sched_prio [sleep]            run preemptive priority scheduler")
    print("reset_sim                     clear all simulated processes")
    print("\n=== Deliverable 3: Memory + Sync ===")
    print("mem_policy <FIFO|LRU>          set paging policy (resets frames)")
    print("mem_access <pid> <page>        access a page")
    print("mem_status                     show frames and page fault count")
    print("run_pc [items]                 run producer-consumer demo")
    print("\n=== Deliverable 4: Piping ===")
    print("Use pipes like: ls | grep txt | sort")
    print("Built-in pipeline helpers: grep <pattern>, sort")
    print("\n=== Deliverable 4: Security ===")
    print("whoami                         show current user")
    print("logout                         log out and return to login")
    print("useradd <name> <role>          (admin) add a user")
    print("passwd [name]                  change password")
    print("chmod <mode> <path>            (admin or owner) set mode like rw-r--")
    print("chown <user> <path>            (admin) change owner")
    print("lsperm <path>                  show permission record")
    print("help                           show this help\n")


def run_single(tokens: List[str], sec: SecurityManager, input_data: Optional[str]) -> str:
    """Run one command and return its output string."""

    cmd = tokens[0]
    args = tokens[1:]

    if cmd == "help":
        print_help()
        return ""

    if cmd == "whoami":
        u = sec.current_user
        return (f"{u.username} ({u.role})\n" if u else "(not logged in)\n")

    if cmd == "logout":
        sec.logout()
        sec.login()
        return ""

    if cmd == "useradd":
        u = sec.current_user
        if not u or not u.is_admin:
            return "Error: admin only\n"
        if len(args) < 2:
            return "Error: useradd <name> <role>\n"
        name, role = args[0], args[1]
        pwd = getpass.getpass(f"New password for {name}: ")
        try:
            sec.add_user(name, pwd, role)
            return f"Added user {name} ({role})\n"
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "passwd":
        if not sec.current_user:
            return "Error: not logged in\n"
        target = args[0] if args else sec.current_user.username
        if target != sec.current_user.username and not sec.current_user.is_admin:
            return "Error: can only change your own password\n"
        newp = getpass.getpass("New password: ")
        try:
            sec.set_password(target, newp)
            return "Password updated\n"
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "chmod":
        if len(args) < 2:
            return "Error: chmod <mode> <path>\n"
        mode, path = args[0], args[1]
        u = sec.current_user
        if not u:
            return "Error: not logged in\n"
        ap = abs_path(path)
        rec = sec._perms.get(ap)
        owner = rec["owner"] if rec else u.username
        if (not u.is_admin) and owner != u.username:
            return "Error: only admin or owner can chmod\n"
        try:
            sec.chmod(path, mode)
            return "OK\n"
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "chown":
        u = sec.current_user
        if not u or not u.is_admin:
            return "Error: admin only\n"
        if len(args) < 2:
            return "Error: chown <user> <path>\n"
        new_owner, path = args[0], args[1]
        try:
            sec.chown(path, new_owner)
            return "OK\n"
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "lsperm":
        if not args:
            return "Error: lsperm <path>\n"
        return sec.lsperm(args[0]) + "\n"

    if cmd == "mem_policy":
        if not args:
            return "Error: mem_policy <FIFO|LRU>\n"
        try:
            mem.set_policy(args[0])
            return f"Policy set to {args[0]}\n"
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "mem_access":
        if len(args) < 2:
            return "Error: mem_access <pid> <page>\n"
        try:
            pid = int(args[0])
            page = int(args[1])
            mem.access(pid, page)
            return ""
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "mem_status":
        mem.status()
        return ""

    if cmd == "run_pc":
        items = int(args[0]) if args else 6
        pc_demo.run(items=items)
        return ""

    if cmd == "addproc":
        if len(args) < 3:
            return "Error: addproc <name> <burst_ticks> <priority> [arrival_ticks]\n"
        try:
            name = args[0]
            burst = int(args[1])
            priority = int(args[2])
            arrival = int(args[3]) if len(args) >= 4 else 0
            p = sched.add_process(name=name, burst=burst, priority=priority, arrival=arrival)
            return f"Added: pid={p.pid} name={p.name} burst={p.burst} prio={p.priority} arrival={p.arrival}\n"
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "psim":
        procs = sched.list_processes()
        if not procs:
            return "(no simulated processes) use addproc first\n"
        lines = [f"{'PID':<5}{'Name':<12}{'Burst':<8}{'Prio':<8}{'Arr':<8}"]
        for p in procs:
            lines.append(f"{p.pid:<5}{p.name:<12}{p.burst:<8}{p.priority:<8}{p.arrival:<8}")
        return "\n".join(lines) + "\n"

    if cmd == "sched_rr":
        if len(args) < 1:
            return "Error: sched_rr <quantum_ticks> [tick_sleep_seconds]\n"
        try:
            quantum = int(args[0])
            tick_sleep = float(args[1]) if len(args) >= 2 else 0.0
            sched.schedule_round_robin(quantum=quantum, tick_sleep=tick_sleep)
            return ""
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "sched_prio":
        try:
            tick_sleep = float(args[0]) if len(args) >= 1 else 0.0
            sched.schedule_priority_preemptive(tick_sleep=tick_sleep)
            return ""
        except Exception as e:
            return f"Error: {e}\n"

    if cmd == "reset_sim":
        sched.reset()
        return "Simulated process list cleared.\n"

    if cmd == "pwd":
        return do_pwd(args)
    if cmd == "echo":
        return do_echo(args)
    if cmd == "ls":
        return do_ls(args)
    if cmd == "cat":
        return do_cat(args, sec)
    if cmd == "mkdir":
        return do_mkdir(args, sec)
    if cmd == "rmdir":
        return do_rmdir(args, sec)
    if cmd == "rm":
        return do_rm(args, sec)
    if cmd == "touch":
        return do_touch(args, sec)
    if cmd == "kill":
        return do_kill(args)
    if cmd == "grep":
        return builtin_grep(args, input_data)
    if cmd == "sort":
        return builtin_sort(args, input_data)

    try:
        res = subprocess.run(tokens, input=input_data, capture_output=True, text=True)
        out = res.stdout
        if res.stderr:
            out += res.stderr
        return out
    except FileNotFoundError:
        return f"Error: command not found: {cmd}\n"
    except Exception as e:
        return f"Error: {e}\n"


def parse_tokens(line: str) -> Tuple[Optional[List[str]], bool]:
    line = line.strip()
    if not line:
        return None, False

    bg = False
    if line.endswith("&"):
        bg = True
        line = line[:-1].strip()

    try:
        parts = shlex.split(line)
        if not parts:
            return None, False
        return parts, bg
    except Exception:
        err("bad command format")
        return None, False


def main() -> None:
    secman.login()
    print("MyShell Deliverable 1-4 Integrated. Type help for commands. Type exit to quit.")

    while True:
        try:
            refresh_jobs()
            u = secman.current_user
            prompt_user = u.username if u else "?"
            cmdline = input(f"{prompt_user}:{os.getcwd()} $ ")

            if not cmdline.strip():
                continue

            if "|" in cmdline:
                parts = split_pipeline(cmdline)
                stages: List[List[str]] = []
                bad = False
                for p in parts:
                    toks, bg = parse_tokens(p)
                    if toks is None:
                        bad = True
                        break
                    if bg:
                        print("Error: background '&' not supported with pipes")
                        bad = True
                        break
                    stages.append(toks)
                if not bad and stages:
                    run_pipeline(stages, secman)
                continue

            tokens, bg = parse_tokens(cmdline)
            if tokens is None:
                continue

            cmd = tokens[0]
            args = tokens[1:]

            if cmd == "exit":
                print("bye")
                break
            if cmd == "cd":
                do_cd(args)
                continue
            if cmd == "clear":
                clr()
                continue
            if cmd == "jobs":
                show_jobs()
                continue
            if cmd == "fg":
                fg_cmd(args)
                continue
            if cmd == "bg":
                bg_cmd(args)
                continue

            if bg:
                start_process(tokens, background=True)
                continue

            out = run_single(tokens, secman, input_data=None)
            if out:
                print(out, end="")

        except KeyboardInterrupt:
            print("\n(ctrl+c) shell still running")
        except EOFError:
            print("\n(end)")
            break


if __name__ == "__main__":
    main()
