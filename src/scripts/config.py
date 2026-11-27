"""Put all the configuration in here"""
from pathlib import Path

# == File ==
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "datasets"
OUTPUT = ROOT / "outputs"
ETL_OUTPUT_DIR = OUTPUT / "etl"
EDA_OUTPUT_DIR = OUTPUT / "eda"
HYPOTHESIS_TESTING_OUTPUT_DIR = OUTPUT / "hypothesis_testing"
STATISTICAL_LEARNING_OUTPUT_DIR = OUTPUT / "statistical_learning"
PROFILING_OUTPUT_DIR = ETL_OUTPUT_DIR / "transform" /"profile"

def print_path(path: Path):
    try:
        from varname import argname
        label = argname("path")
    except Exception:
        label = "path"
    print(f"Path of the {label} is {path}")
# DEFAULT VALUE
DEFAULT_FILE_EXTENSION = "*.csv"
DEFAULT_DEBUG_MODE = 0
DEFAULT_OUTPUT_REPORT_EXTENSION = ".md"

# === TEXT ===
BOLD_RED_START = '\033[1;31m'
BOLD_END =  '\033[0m'

def bold_text(text:str) -> str:
    return BOLD_RED_START+text+BOLD_END

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
