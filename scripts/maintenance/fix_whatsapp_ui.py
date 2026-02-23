
import os

path = r"c:\SGUBM-V1\src\presentation\web\templates\modules\whatsapp.html"

extra_html = """
    /* Configuration & Action Styles */
    .header-actions { display: flex; align-items: center; gap: 12px; }
    .btn-quantum-tiny {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255,255,255,0.1);
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s;
    }
    .btn-quantum-tiny:hover { background: #6366f1; transform: rotate(45deg); }
    .btn-quantum-tiny svg { width: 16px; height: 16px; }

    .whatsapp-config-modal {
        background: rgba(15, 15, 25, 0.95);
        backdrop-filter: blur(40px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 20px;
        padding: 30px;
        color: white;
        max-width: 500px;
        width: 90%;
    }
    .config-section { margin-bottom: 20px; }
    .field-group { display: flex; flex-direction: column; gap: 5px; margin-bottom: 15px; }
    .field-group label { font-size: 12px; opacity: 0.7; }
    .field-group input { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 10px; color: white; }
    .webhook-box { background: rgba(99, 102, 241, 0.1); border: 1px dashed #6366f1; border-radius: 8px; padding: 10px; display: flex; justify-content: space-between; align-items: center; }
    .webhook-box code { font-size: 11px; color: #818cf8; word-break: break-all; }
    .btn-save-quantum { width: 100%; padding: 12px; background: #6366f1; border: none; border-radius: 10px; color: white; font-weight: bold; cursor: pointer; }
</style>

<!-- Agent Configuration Modal -->
<div id="whatsapp-config-modal" class="modal-overlay" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 2000; background: rgba(0,0,0,0.8); backdrop-filter: blur(8px); align-items: center; justify-content: center;">
    <div class="whatsapp-config-modal">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="margin: 0;">Configuración del Agente</h3>
            <button onclick="document.getElementById('whatsapp-config-modal').style.display='none'" style="background: none; border: none; color: white; cursor: pointer; font-size: 24px;">&times;</button>
        </div>
        <div class="config-section">
            <div class="field-group"><label>Gemini API Key</label><input type="password" id="config-gemini-key"></div>
            <div class="field-group"><label>Nombre del Agente</label><input type="text" id="config-agent-name"></div>
        </div>
        <div class="config-section">
            <label style="font-size:12px; opacity:0.7;">Webhook URL (Copia en tu Bridge)</label>
            <div class="webhook-box"><code id="config-webhook-url">Cargando...</code><button onclick="app.modules.whatsapp.copyWebhook()" style="background:#6366f1; border:none; color:white; padding:4px 8px; border-radius:4px; font-size:10px; cursor:pointer;">Copiar</button></div>
            <div class="field-group" style="margin-top:10px;"><label>Número de Teléfono</label><input type="text" id="config-agent-phone"></div>
        </div>
        <button class="btn-save-quantum" onclick="app.modules.whatsapp.saveConfig()">Guardar Configuración</button>
    </div>
</div>
"""

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if "</style>" in content:
    # Append styles before </style> and Modal after it
    # We find the LAST </style>
    parts = content.rsplit("</style>", 1)
    new_content = parts[0] + extra_html + parts[1]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully updated whatsapp.html")
else:
    print("Could not find </style> in whatsapp.html")
