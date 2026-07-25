"""
open_kit.py  --  quickly open a generated application kit.

USAGE:
  py open_kit.py            -> opens the MOST RECENT kit
  py open_kit.py list       -> lists all kits (newest first) with numbers
  py open_kit.py 2          -> opens kit number 2 from that list
  py open_kit.py okta       -> opens the newest kit whose name contains "okta"

It opens in VS Code (rendered markdown preview) if available, otherwise in
your default app.
"""

import os
import sys
import glob
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
KITS = os.path.join(HERE, "kits")


def all_kits():
    # Prefer the ready-to-apply PDFs; fall back to .md if a PDF wasn't produced.
    files = glob.glob(os.path.join(KITS, "*.pdf")) or glob.glob(os.path.join(KITS, "*.md"))
    return sorted(files, key=os.path.getmtime, reverse=True)


def open_file(path):
    # Prefer VS Code (renders markdown); fall back to the OS default app.
    try:
        subprocess.run(["code", "-r", path], shell=True, check=True)
        print(f"Opened in VS Code: {os.path.basename(path)}")
        print("  (Press Ctrl+Shift+V in VS Code for the formatted preview.)")
        return
    except Exception:
        pass
    try:
        os.startfile(path)  # Windows default app
        print(f"Opened: {os.path.basename(path)}")
    except Exception as e:
        print(f"Could not open automatically. File is at:\n  {path}\n({e})")


def main():
    files = all_kits()
    if not files:
        print("No kits yet. They appear here after the monitor finds a new role.")
        return

    arg = sys.argv[1].strip().lower() if len(sys.argv) > 1 else None

    if arg == "list":
        print(f"{len(files)} kit(s), newest first:\n")
        for i, f in enumerate(files, 1):
            print(f"  {i:>2}. {os.path.basename(f)}")
        print("\nOpen one with:  py open_kit.py <number>")
        return

    if arg is None:
        open_file(files[0])
    elif arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(files):
            open_file(files[idx])
        else:
            print(f"No kit #{arg}. There are {len(files)}. Try:  py open_kit.py list")
    else:
        matches = [f for f in files if arg in os.path.basename(f).lower()]
        if matches:
            open_file(matches[0])
        else:
            print(f"No kit matching '{arg}'. Try:  py open_kit.py list")


if __name__ == "__main__":
    main()
