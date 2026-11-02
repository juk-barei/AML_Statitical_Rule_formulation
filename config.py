"""Put all the configuration in here"""
from pathlib import Path
from varname import argname
import warnings 
warnings.filterwarnings("ignore")
# == File ==
ROOT = Path().cwd().resolve()
SRC = ROOT / "datasets"
OUTPUT = ROOT / "outputs"
def print_path(path: Path):
    print(f"Path of the {argname('path')} is {path}")
DEFAULT_FILE_EXTENSION = "*.csv"
DEFAULT_DEBUG_MODE = 0
# === TEXT ===
BOLD_START = '\033[1m'
BOLD_END =  '\033[0m'

def bold_text(text:str) -> str:
    return BOLD_START+text+BOLD_END

ARG_HELP_F_MESSAGE = f"""
{bold_text("INFO")}: index of dataframe to access  from the dataframe list. Default shows only the first element df.
{bold_text("USAGE:")} Use one index to access one dataframe or input many indices separated by comma(,) for many element. 
{bold_text("VALUE: ")}
    - all: \t all elements of the dataframe list. 
    - 0: first dataframe to retrieve
    - 1, 2, 4: acccess the dataframe in the coreesponding index.
{bold_text("NOTE: ")} You can't enter keywoard {bold_text("all")} as a part of index chaining. Ex: 1, all, 4. """

def main():
    print_path(ROOT)
    print_path(SRC)
    print_path(OUTPUT)

if __name__ == "__main__":
    main()
