# 02 — Setup and Project Skeleton

> **Goal:** create an empty but correctly organised project that can run Python tests.
> **You will build:** `.gitignore`, `.vscode/settings.json`, `backend/requirements.txt`,
> `backend/src/__init__.py`, `backend/tests/__init__.py`.
> **Time:** ~45 minutes.
> **Prerequisites:** [01](01-the-game-and-the-problem.md). Python 3.11+ and git installed.

---

## The big picture

A real project is more than code files. It needs:

- **version control** (git) so you can save checkpoints and undo mistakes,
- a **private set of installed libraries** (a *virtual environment*) so this project's libraries don't
  clash with other projects,
- a **folder layout** that separates source code from tests and data,
- a **test runner** (pytest) so you can prove your code works.

We set all of this up now, once, so that from chapter 4 onwards we only think about the code.

```
lieng-stealer/              ← the project root (a git repository)
├── .gitignore              ← files git should NOT track
├── .vscode/settings.json   ← editor settings (optional)
└── backend/                ← everything Python lives here
    ├── requirements.txt    ← list of libraries to install
    ├── data/               ← generated data (chapter 7)
    ├── src/                ← the source code (a Python *package*)
    │   └── __init__.py
    └── tests/              ← the tests (also a package)
        └── __init__.py
```

> Later, in chapter 15, a second folder `frontend/` will hold the web page. Keeping the Python
> **backend** and the JavaScript **frontend** in separate folders is a common way to organise a
> "full-stack" project.

---

## Concepts you need

### Git in 30 seconds

Git records snapshots ("commits") of your folder. The commands you need:

```bash
git init                 # turn the current folder into a repository (once)
git status               # what changed since the last commit?
git add .                # mark all changes to be saved
git commit -m "message"  # save a snapshot with a description
git log --oneline        # list snapshots
```

### Virtual environments

When you `pip install flask`, Python puts Flask somewhere on your computer. If two projects need
different versions of Flask, they fight. A **virtual environment** (venv) is a folder (here `.venv/`)
holding a private copy of Python's package list for **one** project. You "activate" it in your terminal
so that `python` and `pip` use it.

### Packages and imports

A **module** is one `.py` file. A **package** is a folder of modules that contains a file called
`__init__.py` (it can be almost empty). Because `src/` will be a package, other code can write:

```python
from src.evaluator import Card
```

For Python to find `src`, the folder **containing** `src` (that is, `backend/`) must be on Python's
search path. The easiest way to guarantee that: **always run commands from inside `backend/`**, using
`python -m ...`. The `-m` flag adds the current folder to the search path.

---

## Step 2.1 — Create the folders and start git

```bash
mkdir lieng-stealer
cd lieng-stealer
git init
mkdir -p backend/src backend/tests backend/data .vscode
```

🧪 **Mini-check**

```bash
ls -a
```

Expected output (the order may differ):

```
.  ..  .git  .vscode  backend
```

---

## Step 2.2 — Tell git what to ignore

Some files should never be committed: Python's cache files, your virtual environment, the JavaScript
`node_modules/` folder (huge, and re-creatable with `npm install`) and secret `.env` files.

📄 **File:** `.gitignore` — *create this file*

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.pytest_cache/
.coverage

# Keep data tracked
!backend/data/winrates.json

# Node & Frontend Build
node_modules/
frontend/dist/
frontend/node_modules/
.env.local
.env.*.local
```

**How it works**

- Each line is a pattern. `__pycache__/` ignores every folder with that name, at any depth.
- `*.py[cod]` uses a character set: it matches `.pyc`, `.pyo` and `.pyd` files.
- A line starting with `!` **un-ignores** something. `!backend/data/winrates.json` makes sure our
  precomputed data file is committed, so other people don't have to regenerate it.

---

## Step 2.3 — Create the virtual environment and install libraries

📄 **File:** `backend/requirements.txt` — *create this file*

```text
flask==3.0.3
flask-cors==4.0.1
gunicorn==22.0.0
requests==2.31.0
rich==13.7.1
pytest==9.1.1
```

What each library is for (you'll meet each one later):

| Library | Used in | Purpose |
|---------|---------|---------|
| `flask` | ch 13 | the web API |
| `flask-cors` | ch 13 | lets the browser page call the API |
| `gunicorn` | ch 17 | production web server |
| `requests` | ch 13 | calling another web service (the LLM) |
| `rich` | ch 12 | pretty tables in the terminal |
| `pytest` | every chapter | running tests |

`==3.0.3` **pins** an exact version. Pinning means everyone who installs the project gets the same
versions, so "it works on my machine" also works on theirs.

Now create the environment and install:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 🪟 **Windows (PowerShell):** use `python -m venv .venv` and then `.venv\Scripts\Activate.ps1`.
> If PowerShell refuses to run the script, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

After activation, your prompt usually starts with `(.venv)`. **Every time you open a new terminal**
to work on the backend, `cd backend` and activate again.

🧪 **Mini-check**

```bash
python -c "import flask, flask_cors, requests, rich, pytest; print('all good')"
```

Expected output:

```
all good
```

---

## Step 2.4 — Make `src` and `tests` into packages

📄 **File:** `backend/src/__init__.py` — *create this file*

```python
"""Liêng Stealer - Game Theory Decision Engine for Liêng."""
```

📄 **File:** `backend/tests/__init__.py` — *create this file*

```python
"""Test suite for Liêng Stealer."""
```

Each file only contains a **docstring**: a string that documents the package. That is enough: the
mere presence of `__init__.py` makes the folder a package.

---

## Step 2.5 — Help your editor find the code (VS Code, optional)

Your editor's Python plugin (Pylance) needs to know that imports like `from src.evaluator import Card`
start from `backend/`. Otherwise it underlines them in red even though they run fine.

📄 **File:** `.vscode/settings.json` — *create this file*

```json
{
  "python.analysis.extraPaths": [
    "${workspaceFolder}/backend"
  ],
  "python.autoComplete.extraPaths": [
    "${workspaceFolder}/backend"
  ]
}
```

`${workspaceFolder}` is replaced by VS Code with the path of the folder you opened (the project root).

---

## Step 2.6 — Prove pytest works (a throwaway test)

Create a **temporary** file (it is not part of the final project, so it has no 📄 label):

```python
# backend/tests/test_smoke.py  (temporary — delete after this step)
def test_math_still_works() -> None:
    assert 1 + 1 == 2
```

Run it from `backend/`:

```bash
python -m pytest -q
```

Expected output (the time will differ):

```
.                                                                        [100%]
1 passed in 0.01s
```

**How pytest works:** it searches the `tests/` folder for files named `test_*.py`, then runs every
function whose name starts with `test_`. Inside a test, `assert <condition>` checks that something is
true. If it is false, the test fails and pytest shows you both sides of the comparison.

Now delete the temporary test:

```bash
rm tests/test_smoke.py
```

---

## ✅ Checkpoint

From the project root:

```bash
find . -path ./backend/.venv -prune -o -path ./.git -prune -o -print | sort
```

Expected output:

```
.
./.gitignore
./.vscode
./.vscode/settings.json
./backend
./backend/data
./backend/requirements.txt
./backend/src
./backend/src/__init__.py
./backend/tests
./backend/tests/__init__.py
```

Save your work:

```bash
git add .
git commit -m "chore: project skeleton"
```

`git status` should now say `nothing to commit, working tree clean`. Check that `.venv` was **not**
committed with `git ls-files | grep venv` (it should print nothing).

## Recap

- The backend lives in `backend/`; source in `backend/src/`, tests in `backend/tests/`.
- A **virtual environment** keeps this project's libraries private. Activate it in every new terminal.
- `__init__.py` turns a folder into a **package**, so we can write `from src.x import y`.
- Always run Python commands **from `backend/`** with `python -m ...`.

**Next:** [03 — Python toolkit](03-python-toolkit.md)