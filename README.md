# Data and Statistical Analysis for Rule formulation for AML in Crypto

- **Hypothesis covered**: 2,4,6

## Prerequisites
You can adopt the project to your development workflow. As of mine, I use `uv` as the package manager. Here is the list of prerequisites:
- `uv`: [install here only if you want](https://docs.astral.sh/uv/getting-started/installation/)
- minimum `python-version`: 3.14

## QuickStart
As the dataset files are too big, I don't include in here. Run the following commands
In the root directory (`data_analysis`):
1. Create and enter the datasets directory
```mkdir -p datasets```

2. Download files from Google Drive using gdown (Ensure you replace the URL with your target Google Drive folder link)
```gdown --folder https://drive.google.com/drive/folders/16k2BfE3yQ5nHYVRCJZfpcqm6NdiagCxE -O datasets/```

3. Unzip any nested zip archives
```unzip "datasets/*.zip" -d datasets/```

4. Clean up downloaded zip files
```rm -f datasets/*.zip```

5. Sync the packages 
```uv sync```

6. setup build tools for project: 
```uv pip install -e .```

7. Activate the virtual environment: 
```./venv/bin/activate```

8. **NOT WORKING YET**: Run the whole workflow: 
`python3 main.py`
Result will be stored in the `outputs` directory.
For now run in each file. Eg: ```python3 src/processing.py --debug 1```

## How to use this directory
- `src`: source code for analytical task.
- `docs`: look at the hypothesis and resources
- `datasets`: datasets for doing the statistical analysis
- `outputs`: the output from the analysis(figures, documentation, files...).

### How to use the `src` directory
- `.ipynb` files are for temporary inspection or intro.
- `.py` files are the real deal. They are the content.

**Note**: I am doing a personal experiment to see if using `.py` files will make the data/ML coding more smooth than using `.ipynb` files. And `.py` is a text file that could be opened in terminal-based text editor with no need for plugin. `.ipynb` files requires me to install plugin, pushing me to use either jupyterlab or vscode with plugins.
**NOTE**: ETL pipeline is already covered beforehand.
## Checklists
**Note**: This is just draft. For the whole flow breakdown, look at [flow.md](docs/flow.md)
### Main:
- [Done] Loading:Implement the file ingestion with command line options.
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
