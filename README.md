# Data and Statistical Analysis for Rule formulation for AML in Crypto

- **Hypothesis covered**: 2,4,6

## How to use this directory
- `src`: source code for analytical task.
- `docs`: look at the hypothesis and resources
- `datasets`: datasets for doing the statistical analysis
- `outputs`: the output from the analysis(figures, documentation, files...). This will be created from running the [QuickStart](QuickStart) section.

### How to use the `src` directory
- `.ipynb` files are for temporary inspection or intro.
- `.py` files are the real deal. They are the content.

**Note**: I am doing a personal experiment to see if using `.py` files will make the data/ML coding more smooth than using `.ipynb` files. And `.py` is a text file that could be opened in terminal-based text editor with no need for plugin. `.ipynb` files requires me to install plugin, pushing me to use either jupyterlab or vscode with plugins.

## What is in this directory:
- Statistical analysis
**NOTE**: ETL pipeline is already covered beforehand.

## Prerequisites
You can adopt the project to your development workflow. As of mine, I use `uv` as the package manager. Here is the list of prerequisites:
- `uv`: [install here only if you want](https://docs.astral.sh/uv/getting-started/installation/)
- minimum `python-version`: 3.14

## QuickStart
In the root directory (`data_analysis`),
1. Sync the packages: `uv sync` && `uv pip install -e .`
You should have the virtual environment and the packages installed.
2. Activate the virtual environment: `./venv/bin/activate`
3. **NOT WORKING YET**: Run the whole workflow: `python3 main.py`
Result will be stored in the `outputs` directory.

For now run in each file. Eg: `python3 src/processing.py --debug 1`

## Checklists
**Note**: This is just draft. For the whole flow breakdown, look at [flow.md](docs/flow.md)
### Main:
- [ X ] Loading:Implement the file ingestion with command line options.
- [ ] Processing: Implement EDA with report of insights and main decision to `outputs/`
- [ ] Aggregate data for missing columns.
- [ ] Data visualization: Implement Q-Q plot with Sharpio-Wiki Test for non normalized value to assume normal distribution for all rules when $n$ grows.
- [ ] Implement the t-test for Hypothesis testing on $H_0$ of each distribution.
- [ ] Formalize the rules based pattern and Hypothesis testing.
- [ ] Implement Evaluation on the rule formalization.

### Optional:
- [ ] Implement the visualization for main insights.

## Questions
- Should the study on assumption of normal distribution be further studied for if pattern in real-life doesn't represent normal distribution then we also study the Box Cox transformation?

## LICENSE
The Repository is under the MIT LICENSE.

## Author: Layhok Leng
