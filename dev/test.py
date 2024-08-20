import pandas as pd

file_path = 'D:\\mnt\\data\\demo.xlsx'
df = pd.read_excel(file_path)
print(df.head(3))
