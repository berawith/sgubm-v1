import subprocess
import time
import sys
import os

def run_server():
    print("="*50)
    print("🚀 CENTINELA SGUBM ACTIVO")
    print("Este script mantendrá el servidor vivo aunque falle o se editen archivos.")
    print("="*50)
    
    # Asegurar que estamos en el directorio correcto
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    while True:
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] --- Iniciando aplicación ---")
            # Usamos sys.executable para mantener el entorno virtual si existe
            process = subprocess.Popen([sys.executable, "run.py"])
            
            # Esperar a que el proceso termine (ya sea por crash o reload)
            process.wait()
            
            if process.returncode != 0:
                print(f"⚠️ El servidor se detuvo con error (code {process.returncode}).")
            
            print("🔄 Reiniciando automáticamente en 2 segundos...")
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo centinela por petición del usuario...")
            if 'process' in locals():
                process.terminate()
            break
        except Exception as e:
            print(f"❌ Error crítico en centinela: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_server()
