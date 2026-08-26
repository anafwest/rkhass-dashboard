import pandas as pd
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if os.path.exists("data.xlsx"):
    df = pd.read_excel("data.xlsx")
    print(f"File: data.xlsx")
    print(f"Modification: {os.path.getmtime('data.xlsx')}")
    print(f"Records: {len(df)}")
elif os.path.exists("data.xls"):
    try:
        df = pd.read_html("data.xls", encoding="utf-8")[0]
    except:
        df = pd.read_html("data.xls", encoding="cp1256")[0]
    print(f"File: data.xls")
    print(f"Modification: {os.path.getmtime('data.xls')}")
    print(f"Records: {len(df)}")
else:
    print("No data file found!")
