
import pandas as pd
try:
    df = pd.read_excel('AUDITORIA_DUPLICADOS_SGUBM.xlsx', sheet_name='IPs Duplicadas')
    print(df.to_string())
except Exception as e:
    print(f"Error reading excel: {e}")
