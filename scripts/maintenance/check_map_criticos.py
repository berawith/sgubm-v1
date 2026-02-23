
import pandas as pd
df = pd.read_excel('MAPA_TOTAL_SISTEMA.xlsx', sheet_name='MikroTik Real')
# Buscar coincidencias
matches = df[df['Name'].str.contains('Juan Pablo|Grabiela|Alvarado|Barrios', case=False, na=False)]
print(matches.to_string())
