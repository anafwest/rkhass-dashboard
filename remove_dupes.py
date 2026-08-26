import pandas as pd
import os
import shutil
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

df = pd.read_excel("data.xlsx")
before = len(df)

col0 = df.columns[0]
df_clean = df.drop_duplicates(subset=[col0], keep='first')
after = len(df_clean)

# backup
shutil.copy2("data.xlsx", f"backups/data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

df_clean.to_excel("data.xlsx", index=False)

print(f"Before: {before}")
print(f"After: {after}")
print(f"Removed: {before - after}")
