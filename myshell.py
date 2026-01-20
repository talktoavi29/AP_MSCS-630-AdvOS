import os
import shlex
import signal
import subprocess

job_table = {}
job_counter = 1


def win():
    return os.name == "nt"


def err(msg):
    print("Error:", msg)


def clr():
    os.system("cls" if win() else "clear")


def refresh_jobs():
    for jid in list(job_table.keys()):
        p = job_table[jid]["proc"]
        code = p.poll()
        if code is not None:
            job_table[jid]["status"] = f"done (exit={code})"


def do_cd(args):
    try:
        if len(args) == 0:
            os.chdir(os.path.expanduser("~"))
        else:
            os.chdir(args[0])
    except Exception as e:
        err(e)


def do_pwd():
    print(os.getcwd())


def do_echo(args):
    print(" ".join(args))


def do_ls(args):
    target = args[0] if args else "."
    try:
        for f in os.listdir(target):
            print(f)
    except Exception as e:
        err(e)


def do_cat(args):
    if not args:
        err("cat needs a file name")
        return
    try:
        with open(args[0], "r", encoding="utf-8", errors="replace") as fp:
            print(fp.read(), end="")
    except Exception as e:
        err(e)


def do_mkdir(args):
    if not args:
        err("mkdir needs a directory name")
        return
    try:
        os.makedirs(args[0], exist_ok=True)
    except Exception as e:
        err(e)


def do_rmdir(args):
    if not args:
        err("rmdir needs a directory name")
        return
    try:
        os.rmdir(args[0])
    except Exception as e:
        err(e)


def do_rm(args):
    if not args:
        err("rm needs a file name")
        return
    try:
        os.remove(args[0])
    except Exception as e:
        err(e)


def do_touch(args):
    if not args:
        err("touch needs a file name")
        return

    name = args[0]
    try:
        if not os.path.exists(name):
            open(name, "w").close()
        os.utime(name, None)
    except Exception as e:
        err(e)


def do_kill(args):
    if not args:
        err("kill needs a pid")
        return
    try:
        pid = int(args[0])
        os.kill(pid, signal.SIGTERM)
        print("Killed", pid)
    except Exception as e:
        err(e)


def show_jobs():
    refresh_jobs()
    if not job_table:
        print("(no jobs)")
        return
    for jid, info in job_table.items():
        print(f"[{jid}] pid={info['pid']} status={info['status']} cmd={info['cmd']}")


def fg_cmd(args):
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


def bg_cmd(args):
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


def start_process(tokens, background):
    global job_counter

    try:
        p = subprocess.Popen(tokens)

        if background:
            jid = job_counter
            job_counter += 1
            job_table[jid] = {
                "pid": p.pid,
                "proc": p,
                "cmd": " ".join(tokens),
                "status": "running"
            }
            print(f"Started job [{jid}] pid={p.pid}")
        else:
            p.wait()

    except FileNotFoundError:
        err("command not found: " + tokens[0])
    except Exception as e:
        err(e)


def parse(line):
    line = line.strip()
    if not line:
        return None

    bg = False
    if line.endswith("&"):
        bg = True
        line = line[:-1].strip()

    try:
        parts = shlex.split(line)
        if not parts:
            return None
        return parts, bg
    except Exception:
        err("bad command format")
        return None


def main():
    print("MyShell Deliverable 1. Type exit to quit.")
    while True:
        try:
            refresh_jobs()
            cmdline = input(os.getcwd() + " $ ")

            parsed = parse(cmdline)
            if not parsed:
                continue

            tokens, bg = parsed
            cmd = tokens[0]
            args = tokens[1:]

            if cmd == "exit":
                print("bye")
                break
            elif cmd == "cd":
                do_cd(args)
            elif cmd == "pwd":
                do_pwd()
            elif cmd == "echo":
                do_echo(args)
            elif cmd == "clear":
                clr()
            elif cmd == "ls":
                do_ls(args)
            elif cmd == "cat":
                do_cat(args)
            elif cmd == "mkdir":
                do_mkdir(args)
            elif cmd == "rmdir":
                do_rmdir(args)
            elif cmd == "rm":
                do_rm(args)
            elif cmd == "touch":
                do_touch(args)
            elif cmd == "kill":
                do_kill(args)
            elif cmd == "jobs":
                show_jobs()
            elif cmd == "fg":
                fg_cmd(args)
            elif cmd == "bg":
                bg_cmd(args)
            else:
                start_process(tokens, bg)

        except KeyboardInterrupt:
            print("\n(ctrl+c) shell still running")
        except EOFError:
            print("\n(end)")
            break


if __name__ == "__main__":
    main()
