import sys
import os
sys.path.append(os.getcwd())
from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router, NetworkSegment

app = create_app()

def fix_segments():
    print("\n" + "="*70)
    print("REPARACIÓN DE SEGMENTOS: MI JARDIN")
    print("="*70 + "\n")
    
    with app.app_context():
        db = get_db()
        target_ip = "12.12.12.39"
        
        # 1. Buscar el router
        router = db.session.query(Router).filter_by(host_address=target_ip).first()
        
        if not router:
            print(f"❌ ERROR CRÍTICO: No se encontró el router con IP {target_ip}")
            print("   (Verifica que la IP sea correcta)")
            return
            
        print(f"✅ Router encontrado: {router.alias} (ID: {router.id})")
        
        # 2. Definir los segmentos requeridos
        required_segments = [
            {'name': 'Segmento Principal', 'cidr': '172.16.41.0/24'},
            {'name': 'Segmento Secundario 1', 'cidr': '10.10.10.0/24'},
            {'name': 'Segmento Secundario 2', 'cidr': '10.10.11.0/24'}
        ]
        
        # 3. Limpiar segmentos existentes de ESTE router
        existing = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == router.id).all()
        if existing:
            print(f"   ⚠️ Eliminando {len(existing)} segmentos antiguos de este router...")
            for seg in existing:
                db.session.delete(seg)
        
        # 4. Insertar nuevos segmentos
        print("   📥 Insertando nuevos segmentos...")
        for seg_data in required_segments:
            new_seg = NetworkSegment(
                router_id=router.id,
                name=seg_data['name'],
                cidr=seg_data['cidr']
            )
            db.session.add(new_seg)
            print(f"      + Agregado: {seg_data['cidr']}")
            
        try:
            db.session.commit()
            print("\n✅ ¡CAMBIOS GUARDADOS EXITOSAMENTE!")
            print(f"   El router {router.alias} ahora filtrará estrictamente por estos {len(required_segments)} rangos.")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error al guardar en base de datos: {e}")

if __name__ == "__main__":
    fix_segments()
