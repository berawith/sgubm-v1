# Script para eliminar el inicio automático de SGUBM
# Ejecutar como Administrador

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Desinstalador de Inicio Automático - SGUBM   " -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si se está ejecutando como administrador
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ ERROR: Este script debe ejecutarse como Administrador" -ForegroundColor Red
    Write-Host ""
    Write-Host "Haz clic derecho en PowerShell y selecciona 'Ejecutar como administrador'" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

$taskName = "SGUBM_AutoStart"

# Verificar si la tarea existe
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if (-not $existingTask) {
    Write-Host "⚠️  La tarea '$taskName' no existe." -ForegroundColor Yellow
    Write-Host "   No hay nada que eliminar." -ForegroundColor Gray
    Write-Host ""
    pause
    exit 0
}

Write-Host "Se encontró la tarea: $taskName" -ForegroundColor White
Write-Host "Estado: $($existingTask.State)" -ForegroundColor Gray
Write-Host ""

$response = Read-Host "¿Deseas eliminar esta tarea? (S/N)"

if ($response -eq 'S' -or $response -eq 's') {
    try {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host ""
        Write-Host "✅ Tarea eliminada exitosamente!" -ForegroundColor Green
        Write-Host ""
        Write-Host "El servidor SGUBM ya NO se iniciará automáticamente." -ForegroundColor White
        Write-Host "Puedes iniciarlo manualmente usando launcher.bat o run.py" -ForegroundColor Gray
    }
    catch {
        Write-Host ""
        Write-Host "❌ ERROR al eliminar la tarea: $_" -ForegroundColor Red
        pause
        exit 1
    }
}
else {
    Write-Host ""
    Write-Host "Operación cancelada." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Presiona cualquier tecla para salir..." -ForegroundColor Gray
pause
