
import os
import sys
import pandas as pd

# Leer el reporte de auditoría que generamos justo antes de la limpieza
def review_merged_candidates():
    try:
        df = pd.read_excel('AUDITORIA_DUPLICADOS_SGUBM.xlsx', sheet_name='IPs Duplicadas')
        print("CANDIDATOS QUE FUERON PROCESADOS EN LA LIMPIEZA:")
        print("-" * 80)
        
        # Agrupar por IP para ver quiénes estaban juntos
        for ip, group in df.groupby('IP'):
            names = group['Nombre en Sistema'].tolist()
            if len(set([n.split()[0] for n in names])) > 1:
                print(f"⚠️ POSIBLE ERROR DE FUSIÓN EN IP {ip}:")
                for _, row in group.iterrows():
                    print(f"   - {row['Nombre en Sistema']} (ID {row['ID']}, Cod {row['Codigo']})")
                print("")
            else:
                print(f"✅ Duplicado probable (mismo nombre): {ip} -> {names}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    review_merged_candidates()
