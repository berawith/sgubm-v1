
import pandas as pd
df = pd.read_excel('AUDITORIA_DUPLICADOS_SGUBM.xlsx', sheet_name='IPs Duplicadas')
print(df[df['IP'] == '177.77.70.23'].to_string())
