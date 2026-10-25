
## What you need

You should atleast have Python 3.10 and also, please note, this has only been tested MacOS, nothing else!



## Install

Copy and paste this block:

```bash
cd ~
git clone https://github.com/Dhruvahere/Tapestries
cd Tapestries
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

`cd Tapestries` is the folder the clone just created,.

`pip install -r requirements.txt` installs Flask, pywebview, and numpy. `pip install -e .` makes the `tapestries` command.

## Run

The venv must be on. After that, `tapestries` works from any folder:

```bash
source ~/Tapestries/.venv/bin/activate
tapestries
```

If the command is not found:

```bash
source ~/Tapestries/.venv/bin/activate
python ~/Tapestries/launch.py
```

## Where your data lives

`~/Library/Application Support/Tapestries/tapestries.db`

It stays on that computer. Closing the window does not delete it.

## Art

Header and icon: hand-drawn knitting spool via Vecteezy. License PDF is in `static/images/`.

By Dhruva Gadiparthi.
