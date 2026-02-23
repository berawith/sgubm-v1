
import pandas as pd
for sheet in ['IPs Duplicadas', 'Codigos Duplicados', 'Nombres Genericos']:
    try:
        df = pd.read_excel('AUDITORIA_DUPLICADOS_SGUBM.xlsx', sheet_name=sheet)
        matches = df[df.apply(lambda row: row.astype(str).str.contains('Alvarado|Piscuri|Grabiela', case=False).any(), axis=1)]
        if not matches.empty:
            print(f"--- Fósforos en {sheet} ---")
            print(matches.to_string())
    except: pass
