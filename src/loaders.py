"""To load files, database, query,etc"""
import pandas as pd
import numpy as np
import os
import argparse
from pandas.errors import EmptyDataError
from config import OUTPUT, ROOT, SRC, DEFAULT_FILE_EXTENSION, Path, ARG_HELP_F_MESSAGE, DEFAULT_DEBUG_MODE, bold_text

def load_csv_files(src:str|Path, file_extension: str)->dict[str: pd.DataFrame]:
    """load csv files from a directory"""
    target_dir = Path(src)  
    # if (not isinstance(target_dir, Path)):
    #     raise TypeError(f"Not the right datatype. Expected Path or os.path argument. Recieved: {type(target_dir)}")
    if (not target_dir.exists()):
        raise FileNotFoundError(f"Directory Not Found: {target_dir} ")
    if( not target_dir.is_dir()):
        raise TypeError(f"Not a directory: {target_dir}")
    print(f"Loading csv files from the directory: {target_dir}") 
    csv_file = sorted(target_dir.glob(file_extension))
    if(len(csv_file)<=0):
        raise FileNotFoundError("No csv file in the directory specified.")
    return {element: pd.read_csv(element) for element in csv_file}

def get_file_order(df_dict: dict[str: pd.DataFrame], index: int) -> list[str, pd.DataFrame]:
    """access dataframe of the corresponding index that user wnats to search for. Allow both positive and negative indexing."""
    if(len(df_dict) == 0):
        raise ValueError("Can't acess the dataframe in the specified index. The dataframe list is empty")
    # Positive indexing handling
    if (index>=0) and (len(df_dict)-1 <= index):
        raise IndexError(f"No corresponding index in the dataframe. Input index: {index} ,max positive index allowed: {len(df_dict)-1}")
    # Negative index handling since it is not logical to do modulo index handling in this case.
    if ((index<0) and (len(df_dict)> -index)):
        raise IndexError(f"No corresponding index in the dataframe. Input index: {index} , min negative index allowed: {-len(df_dict)}")
    return (list(df_dict.keys())[index], list(df_dict.values())[index])

def get_df_by_index(df_dict:dict[str: pd.DataFrame], indices_str:list[str] | str ) -> list[tuple[str, pd.DataFrame]]:
    """faciliate result based on a list of indices from the user argument """
    # if they want all elements
    if(indices_str.strip()=="all"):
        return [map(lambda key, val: (key,val), list(df_dict.keys()), list(df_dict.values()))]
    #in case they specify more than one element
    indices = indices_str.split(",")
    try: 
        typed_indices_lst = map(int,indices)
    except Exception as e:
        raise TypeError("Can't covert the indices to integer for retieval.") 
    df_pair_lst = []
    for index in typed_indices_lst:
        df_pair_lst.append(get_file_order(df_dict, index))
    return df_pair_lst

def print_df_lst_info(df_lst: list[str, tuple[pd.DataFrame]]) -> None:
    """print the df general info"""
    print(f"printing {len(df_lst)} elements...")
    print(df_lst)
    for filename,df in df_lst:
        print("\n==============================")
        print(f"File loaded: {filename}")
        print_df_info(df)

def print_df_info(df:pd.DataFrame)->None:
    """Print very basic information about a dataframe"""
    print(f"Shape: {df.shape[0]} rows, {df.shape[1]} cols")
    print(f"column count: {len(df.columns)}")
    print(f"columns: {df.columns}")
    print(f"features and rows: {df.info()}")

def cmd_args()-> argparse.Namespace:
    """To get the arguments from the console."""
    parser = argparse.ArgumentParser(description="Load files and return Pandas DataFrame.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-d", 
                        type=str, 
                        default= SRC, 
                        help=f"directory to scan for files. Default value is {SRC}")
    parser.add_argument("-e",
                         type=str,
                         default= DEFAULT_FILE_EXTENSION,
                        help= f"file extension to filter from the specified directory. Default value is {DEFAULT_FILE_EXTENSION} extension."
                         )
    parser.add_argument("-f", 
                        type=str, 
                        default= '0', 
                        help=f"{ARG_HELP_F_MESSAGE}")
    parser.add_argument("--debug",
                        type=int,
                        default = 0,
                        help= f"activate the debug mode to see some varaible printed out. Default value is {DEFAULT_DEBUG_MODE}"
                        )
    return parser.parse_args()

def args_handling(args) -> None:
    # Debug value argument handling
    debug_value = args.debug
    # isinstance supports subclasses. I don't use strict type checking cuz I want some flexibility.
    if not (isinstance(debug_value, int)):
        raise TypeError("Invalid Type. Enter a value of 0 or 1.")
    if debug_value ==0:
        pass
    elif(debug_value==1):
        print(f"""Running with args:
                    - directory: {args.d} 
                    - file extension: {args.e}
                    - df indices to filter: {args.f}
            """)
    else:
        raise ValueError("Not a valid integer value. Enter a value of 0 or 1.")

def main() -> None:
    args = cmd_args()
    args_handling(args) 
    df_dict = load_csv_files(args.d, args.e)
    pd_lst = get_df_by_index(df_dict, args.f)
    print_df_lst_info(pd_lst)
    
if __name__ =="__main__":
    main()
