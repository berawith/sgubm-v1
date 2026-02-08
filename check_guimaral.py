
import pandas as pd
df_mt = pd.read_excel('MAPA_TOTAL_SISTEMA.xlsx', sheet_name='MikroTik Real')
print(df_mt[df_mt['Router'] == 'GUIMARAL'].to_string())
