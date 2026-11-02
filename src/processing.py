""" This file is for EDA. """
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

def get_null_values_in_columns(df:pd.DataFrame, col: str) -> dict[str, int]:
    row_na_dict = {}
    for columns in df.columns:
        row_na_rows =  df[df[col].isna()].index
        row_na_dict[columns] = row_na_rows
    return row_na_dict

def generate_insight_report(text, filename: str, extension: str) -> None: # will create acceptatble extension  list later on but not now.
    pass

def main():
    args = cmd_args()
    args_handling(args)
    df_dict = load_csv_files(args.d, args.e)
    all_df_names = list(df_dict.keys())
    all_df = list(df_dict.values())
    for df in all_df:
        assert hasattr(df.columns,'__iter__')
        col0 = df.columns[0]
        df_na_row_ind = get_null_values_in_columns(df,col0)
        print(f"df {df} has {len(df_na_row_ind)} NA rows.")

if __name__ == "__main__":
    main()
