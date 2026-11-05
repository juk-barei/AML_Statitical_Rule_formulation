    """ This file is for EDA. """
from pandas.core.indexes import extension
import time
from config import DEFAULT_FILE_EXTENSION, DEFAULT_OUTPUT_REPORT_EXTENSION, OUTPUT, argname
import numpy as np
import pandas as pd
from loaders import args_handling, cmd_args, load_csv_files, get_df_by_index, print_df_info

def overview_pd_lst(df_list: list[pd.DataFrame])->None:
    if len(df_list) == 0:
        raise IndexError("the list is short") 
    for df in df_list:
        overview_df(df)

def overview_df(df:pd.DataFrame)->None:
    """Overview information of a dataframe"""
    print(f"Overview on the data") 
    print(f"General Info: ")
    print_df_info(df)
    print(f"Statistics: {df.describe()}")
SAMPLE_REPORT_FILENAME = "NA_Report"

def get_null_values_in_df_lst(df_list: pd.DataFrame, df_list_name:str):
    df_lst_na_info = f"""# Dataframe List info\n- Total df: {len(df_list)}\n"""
    write_report_file(df_lst_na_info,SAMPLE_REPORT_FILENAME)
    df_lst_total_na = 0
    df_lst_execution_time = 0
    for index, df in enumerate(df_list):
        df_execution_time = 0
        df_na_info = f"""## Dataframe: {df_list_name[index]}\n"""
        write_report_file(df_na_info,SAMPLE_REPORT_FILENAME)
        # assert hasattr(df.columns,'__iter__')
        for col in df.columns:
            col_start_time = time.time()
            df_na_row = get_null_values_in_columns(df,col)
            col_execution_time =  time.time() - col_start_time
            df_na_info = f"""- {col}: {df_na_row[col].sum()}\n"""
            df_na_info += f"""- NA rows: {df[df[col].isna()]}.\n"""
            df_na_info += f"Time executed: {col_execution_time} s.\n"
            write_report_file(df_na_info,SAMPLE_REPORT_FILENAME)
            df_execution_time+= col_execution_time
        df_total_na = df.isna().sum().sum()
        df_lst_total_na+=df_total_na
        df_lst_execution_time += df_execution_time
        df_na_info=f"**Total NA**:{df_total_na}\n"
        df_na_info+= f"**Df execution time**: {df_execution_time} s. \n"
        write_report_file(df_na_info,SAMPLE_REPORT_FILENAME)
        # df_lst_info += f"{df_na_info}\n"
    df_lst_na_info = f"**Total NA accross all {len(df_list)} dfs**: {df_lst_total_na}.\n"
    df_lst_na_info += f"Total execution time: {df_lst_execution_time} s"
    write_report_file(df_lst_na_info,SAMPLE_REPORT_FILENAME)

def get_null_values_in_columns(df:pd.DataFrame, col: str) -> dict[str, int]:
    row_na_dict = {}
    for columns in df.columns:
        row_na_rows =  df[df[col].isna()]
        row_na_dict[columns] = row_na_rows
    return row_na_dict

def write_report_file(text: str, filename: str, mode= 'a+', extension: str = DEFAULT_OUTPUT_REPORT_EXTENSION) -> None: # will create acceptatble extension  list later on but not now.
    """Create file of report at the outputs location.
    Args:
    - text: text to generate report
    - filename: the name of file to be named for the report.
    - extension: extension of the report. Default to md file. Default to .md file for now.
    """
    if not isinstance(filename,str):
        raise TypeError("filename is a string.")
    if (len(text)) == 0:
        print(f"Text with length 0: {text}, varname: {varname.varname(text)}")
    try:
        filename = filename + extension 
        with open(OUTPUT/filename, mode) as file:
            file.write(text)
        print(f"Successfully written \n{text}\n to {OUTPUT/filename}.")
    except FileExistsError as e:
        raise e("File doesn't exist.")

def create_na_report(description:str, value:str, parent: str):
    """Create a report on na count of each column inside all dataframes.
    This will provide more flexibility of how and where to write into."""
    pass 

def main():
    args = cmd_args()
    args_handling(args)
    df_dict = load_csv_files(args.d, args.e)
    all_df_names = list(df_dict.keys())
    all_df = list(df_dict.values())
    # for index, df in enumerate(all_df):
    #     assert hasattr(df.columns,'__iter__')
    #     col0 = df.columns[0]
    #     df_na_row = get_null_values_in_columns(df,col0)
    #     # print(f"type of the df_na_row: {type(df_na_row)}")
    #     # print(f"df {all_df_names[index]} has {len(df_na_row)} NA rows.")
    report_text = get_null_values_in_df_lst(all_df, all_df_names)
    # write_report_file(report_text, "NA_report")
if __name__ == "__main__":
    main()
