
import pandas as pd
df_mt = pd.read_excel('MAPA_TOTAL_SISTEMA.xlsx', sheet_name='MikroTik Real')
df_db = pd.read_excel('MAPA_TOTAL_SISTEMA.xlsx', sheet_name='Base de Datos')

db_users = set(df_db['User_DB'].astype(str).tolist())
orphans = df_mt[~df_mt['Name'].isin(db_users)]
print("USUARIOS EN MIKROTIK NO REGISTRADOS EN BD (Posibles candidatos a ser Grabiela):")
print(orphans[orphans['Router'] != 'PRINCIPAL'].to_string())
