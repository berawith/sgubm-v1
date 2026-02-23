
import pandas as pd
df = pd.read_excel('MAPA_TOTAL_SISTEMA.xlsx', sheet_name='Base de Datos')
# Ver quién tenía la IP 177.77.70.9
print(df[df['IP_DB'] == '177.77.70.9'].to_string())
