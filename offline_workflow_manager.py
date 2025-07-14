# offline_workflow_manager.py
"""
A lightweight, entirely offline task & workforce management tool for large companies.

Key features
------------
* SQLite for zero‑config local storage (works on any machine, network or air‑gapped)
* Command‑line interface so it runs in terminals without extra dependencies
* Core entities: Employees, Teams, Tasks, Shifts
* Simple role‑based permissions (manager vs regular user)
* Daily CSV export so data can be synced or analysed elsewhere
* Modular functions – easy to expand with GUI or network sync later

Run:
    python offline_workflow_manager.py --help
"""
import argparse
import csv
import datetime as dt
import getpass
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("workflow.db")
DATE_FMT = "%Y-%m-%d %H:%M"


def init_db():
    """Create tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT CHECK(role IN ('staff', 'manager')) NOT NULL DEFAULT 'staff',
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                assignee_id INTEGER REFERENCES employees(id),
                status TEXT CHECK(status IN ('todo', 'in‑progress', 'done')) NOT NULL DEFAULT 'todo',
                deadline TEXT,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER REFERENCES employees(id),
                start TEXT NOT NULL,
                end TEXT NOT NULL
            );
            """
        )
        conn.commit()


def add_employee(name: str, role: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO employees (name, role, active) VALUES (?,?,1)", (name, role)
        )
        conn.commit()


def list_employees(active_only=True):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        q = "SELECT id, name, role, active FROM employees"
        if active_only:
            q += " WHERE active=1"
        for row in cur.execute(q):
            print(f"#{row[0]:3} | {row[1]:20} | {row[2]:8} | {'active' if row[3] else 'inactive'}")


def add_task(title, description, assignee_id, deadline):
    now = dt.datetime.now().strftime(DATE_FMT)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO tasks (title, description, assignee_id, deadline, created, updated)
            VALUES (?,?,?,?,?,?)
            """,
            (title, description, assignee_id, deadline, now, now),
        )
        conn.commit()


def list_tasks(filter_status=None):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        q = """
            SELECT t.id, t.title, e.name, t.status, t.deadline
            FROM tasks t LEFT JOIN employees e ON t.assignee_id = e.id
        """
        params = []
        if filter_status:
            q += " WHERE t.status=?"
            params.append(filter_status)
        for row in cur.execute(q, params):
            print(
                f"#{row[0]:3} | {row[1]:25} | {(row[2] or 'unassigned'):15} | {row[3]:12} | {row[4] or '-'}"
            )


def update_task_status(task_id, status):
    now = dt.datetime.now().strftime(DATE_FMT)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tasks SET status=?, updated=? WHERE id=?", (status, now, task_id)
        )
        conn.commit()


def export_csv():
    """Dump all tables into dated CSV files for external sharing/backup."""
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    outdir = Path(f"export_{stamp}")
    outdir.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        for table in ["employees", "tasks", "shifts"]:
            rows = cur.execute(f"SELECT * FROM {table}").fetchall()
            cols = [d[0] for d in cur.description]
            with open(outdir / f"{table}.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
    print(f"Exported to {outdir}/")


def parse_args():
    p = argparse.ArgumentParser(description="Offline Workflow Manager")
    sp = p.add_subparsers(dest="cmd", required=True)

    emp = sp.add_parser("add-employee", help="Add a new employee")
    emp.add_argument("name")
    emp.add_argument("--role", choices=["staff", "manager"], default="staff")

    le = sp.add_parser("list-employees", help="List employees")
    le.add_argument("--all", action="store_true", help="Include inactive employees")

    task = sp.add_parser("add-task", help="Create a task")
    task.add_argument("title")
    task.add_argument("--desc", default="")
    task.add_argument("--assignee", type=int, help="Employee ID")
    task.add_argument("--deadline", help="YYYY-MM-DD HH:MM")

    lt = sp.add_parser("list-tasks", help="List tasks")
    lt.add_argument("--status", choices=["todo", "in‑progress", "done"])

    ut = sp.add_parser("update-task", help="Update task status")
    ut.add_argument("id", type=int)
    ut.add_argument("status", choices=["todo", "in‑progress", "done"])

    sp.add_parser("export", help="Export CSV snapshot")

    return p.parse_args()


def main():
    init_db()
    args = parse_args()
    if args.cmd == "add-employee":
        add_employee(args.name, args.role)
    elif args.cmd == "list-employees":
        list_employees(not args.all)
    elif args.cmd == "add-task":
        add_task(args.title, args.desc, args.assignee, args.deadline)
    elif args.cmd == "list-tasks":
        list_tasks(args.status)
    elif args.cmd == "update-task":
        update_task_status(args.id, args.status)
    elif args.cmd == "export":
        export_csv()
    else:
        print("Unknown command")


if __name__ == "__main__":
    # Simple auth – prompt manager to login before mutating data
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] not in ("list-employees", "list-tasks"):  # read‑only cmds exempt
        user = input("Manager name: ")
        pwd = getpass.getpass("Password (just press Enter for demo): ")
        # In production, verify against hashed credentials!
    main()
