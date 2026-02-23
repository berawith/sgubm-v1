
import os

css_path = 'c:\\SGUBM-V1\\src\\presentation\\web\\static\\css\\dashboard.css'
marker = '/* --- Payment Modal Refinements --- */'

new_css = """/* --- Payment Modal "Ultra-Premium" Refinements --- */
.payment-modal-card {
    background: #ffffff;
    border: 1px solid #f1f5f9;
    border-radius: 20px;
    padding: 0;
    display: flex;
    align-items: stretch;
    justify-content: space-between;
    box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.08);
    margin-bottom: 32px;
    overflow: hidden;
    position: relative;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.payment-modal-card:hover {
    box-shadow: 0 20px 50px -12px rgba(79, 70, 229, 0.15);
    transform: translateY(-2px);
    border-color: #818cf8;
}

.payment-modal-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 6px;
    height: 100%;
    background: linear-gradient(180deg, #4f46e5 0%, #818cf8 100%);
}

.client-section {
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex: 1;
}

.client-card-avatar {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    background: #eff6ff;
    color: #4f46e5;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.75rem;
    box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.1);
}

.client-card-info {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.client-card-name {
    font-weight: 800;
    font-size: 1.25rem;
    color: #1e293b;
    letter-spacing: -0.02em;
}

.client-card-badges {
    display: flex;
    gap: 8px;
    align-items: center;
}

.client-code-pill {
    background: #f8fafc;
    color: #64748b;
    padding: 4px 10px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    border: 1px solid #e2e8f0;
}

.card-divider {
    width: 1px;
    background: linear-gradient(180deg, transparent 0%, #e2e8f0 20%, #e2e8f0 80%, transparent 100%);
    margin: 12px 0;
}

.debt-section {
    padding: 24px 32px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: center;
    background: linear-gradient(90deg, rgba(248, 250, 252, 0.5) 0%, rgba(255, 255, 255, 0) 100%);
    min-width: 180px;
}

.debt-info-pill {
    background: transparent;
    padding: 0;
    border-radius: 0;
    border: none;
    align-items: flex-end;
    width: auto;
}

.debt-info-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94a3b8;
    margin-bottom: 4px;
}

.debt-info-amount {
    font-size: 1.75rem;
    font-weight: 900;
    color: #ef4444;
    line-height: 1;
    letter-spacing: -0.02em;
    text-shadow: 0 4px 12px rgba(239, 68, 68, 0.15);
}

.debt-info-sub {
    font-size: 0.8rem;
    color: #64748b;
    font-weight: 500;
    margin-top: 4px;
}

.debt-info-pill.solvent .debt-info-amount {
    color: #10b981;
    text-shadow: 0 4px 12px rgba(16, 185, 129, 0.15);
}

.actions-section {
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 8px;
    border-left: 1px solid #f1f5f9;
}

.action-btn-glass {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    border: 1px solid #f1f5f9;
    background: #ffffff;
    color: #64748b;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    font-size: 1rem;
}

.action-btn-glass:hover {
    background: #f8fafc;
    color: #4f46e5;
    border-color: #e2e8f0;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.05);
}

.action-btn-glass.danger:hover {
    color: #ef4444;
    background: #fef2f2;
}

.input-premium {
    background: #f8fafc;
    border: 1px solid transparent;
    transition: all 0.3s ease;
}

.input-premium:focus {
    background: #ffffff;
    border-color: #4f46e5;
    box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
}

.input-label-premium {
    font-size: 0.75rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
    display: block;
}
"""

with open(css_path, 'r', encoding='utf-8') as f:
    content = f.read()

if marker in content:
    # Keep content up to the marker
    updated_content = content.split(marker)[0] + new_css
else:
    # Check if we should append or if it's cleaner to replace the last block manually
    # Just append if marker not found but we know we want to replace end
    updated_content = content + "\n" + new_css

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(updated_content)

print("CSS Updated Successfully")
