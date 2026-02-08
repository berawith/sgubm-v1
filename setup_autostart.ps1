# Script para configurar el inicio automático de SGUBM en Windows
# Ejecutar como Administrador

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Configurador de Inicio Automático - SGUBM    " -ForegroundColor Cyan
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

# Parámetros de la tarea
$taskName = "SGUBM_AutoStart"
$taskDescription = "Inicia automáticamente el servidor SGUBM al arrancar Windows"
$vbsPath = "c:\SGUBM-V1\SGUBM_Silencioso.vbs"
$workingDir = "c:\SGUBM-V1"

Write-Host "📋 Configuración de la tarea:" -ForegroundColor Green
Write-Host "   Nombre: $taskName"
Write-Host "   Script: $vbsPath"
Write-Host "   Directorio: $workingDir"
Write-Host ""

# Verificar que el archivo VBS existe
if (-not (Test-Path $vbsPath)) {
    Write-Host "❌ ERROR: No se encuentra el archivo $vbsPath" -ForegroundColor Red
    pause
    exit 1
}

# Eliminar tarea existente si existe
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "🔄 Eliminando tarea existente..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Crear la acción (ejecutar el VBS)
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $workingDir

# Crear el trigger (al iniciar sesión del usuario)
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Configuración adicional
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) # Sin límite de tiempo

# Obtener el usuario actual
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

# Crear el principal (ejecutar con privilegios del usuario actual)
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest

# Registrar la tarea
Write-Host "⚙️  Creando tarea programada..." -ForegroundColor Cyan
try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Description $taskDescription `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null
    
    Write-Host "✅ Tarea creada exitosamente!" -ForegroundColor Green
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "  CONFIGURACIÓN COMPLETADA" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "El servidor SGUBM ahora se iniciará automáticamente cuando:" -ForegroundColor White
    Write-Host "  ✓ Inicies sesión en Windows" -ForegroundColor Green
    Write-Host "  ✓ Arranque la computadora" -ForegroundColor Green
    Write-Host ""
    Write-Host "El servidor se ejecutará en segundo plano y abrirá" -ForegroundColor White
    Write-Host "automáticamente http://localhost:5000 en tu navegador." -ForegroundColor White
    Write-Host ""
    Write-Host "Para DESHABILITAR el inicio automático, ejecuta:" -ForegroundColor Yellow
    Write-Host "  Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Para ELIMINAR la tarea completamente, ejecuta:" -ForegroundColor Yellow
    Write-Host "  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor Cyan
    Write-Host ""
    
    # Preguntar si desea probar ahora
    $response = Read-Host "¿Deseas ejecutar la tarea ahora para probarla? (S/N)"
    if ($response -eq 'S' -or $response -eq 's') {
        Write-Host ""
        Write-Host "🚀 Iniciando SGUBM..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $taskName
        Write-Host "✅ Tarea ejecutada. El navegador debería abrirse en unos segundos." -ForegroundColor Green
    }
    
} catch {
    Write-Host "❌ ERROR al crear la tarea: $_" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

Write-Host ""
Write-Host "Presiona cualquier tecla para salir..." -ForegroundColor Gray
pause
