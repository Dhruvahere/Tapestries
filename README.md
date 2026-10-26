
## What You Need:

You should atleast have Python 3.10 and also, please note, this has only been tested MacOS, nothing else!



## How to Install 

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

`pip install -r requirements.txt` installs the libraries Flask, pywebview, and numpy. `pip install -e .` makes the `tapestries` command.

## How To Open:

The venv must be on. After that, `tapestries` works from any directory in your computer.

```bash
source ~/Tapestries/.venv/bin/activate
tapestries
```

If The Command Is Not Found:

```bash
source ~/Tapestries/.venv/bin/activate
python ~/Tapestries/launch.py
```

## Data Storage: 

`~/Library/Application Support/Tapestries/tapestries.db`

Don't worry, when you close the terminal app, your data doesn't go poof! It will stay right there in the SQLite Data storage. 

## Art

Header and icon: hand-drawn knitting spool from Vecteezy. License PDF is in `static/images/`!

By Dhruva Gadiparthi.
