
import pandas as pd
df_mt = pd.read_excel('MAPA_TOTAL_SISTEMA.xlsx', sheet_name='MikroTik Real')
# Buscar por nombre o comentario
mask = df_mt.apply(lambda row: row.astype(str).str.contains('Grabiela|Alvarado', case=False).any(), axis=1)
print(df_mt[mask].to_string())
