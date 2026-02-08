
import pandas as pd
df = pd.read_excel('AUDITORIA_DUPLICADOS_SGUBM.xlsx', sheet_name='IPs Duplicadas')
grabielas = df[df['Nombre en Sistema'].str.contains('Grabiela', na=False)]
print(grabielas.to_string())
