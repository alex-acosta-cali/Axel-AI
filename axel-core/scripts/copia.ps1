# Copia local de axel.db y kb.json a C:\Proyectos\Axel-AI\copias\ con la fecha en el nombre.
# No copia .env. Solo imprime rutas y tamaños.
$ErrorActionPreference = "Stop"
$core = "C:\Proyectos\Axel-AI\axel-core"
$destino = "C:\Proyectos\Axel-AI\copias"
$fecha = Get-Date -Format "yyyy-MM-dd_HHmm"
New-Item -ItemType Directory -Force $destino | Out-Null

# axel.db con la copia de sqlite3: sirve aunque el demo esté prendido.
$db = Join-Path $core "axel.db"
$dbCopia = Join-Path $destino "axel_$fecha.db"
if (Test-Path $db) {
    & "$core\.venv\Scripts\python.exe" -c "import sqlite3,sys; a=sqlite3.connect(sys.argv[1]); b=sqlite3.connect(sys.argv[2]); a.backup(b); b.close(); a.close()" $db $dbCopia
    if ($LASTEXITCODE -ne 0) { throw "Falló la copia de axel.db" }
    Write-Host "OK $dbCopia ($((Get-Item $dbCopia).Length) bytes)"
} else {
    Write-Host "No existe $db"
}

$kb = Join-Path $core "kb.json"
$kbCopia = Join-Path $destino "kb_$fecha.json"
if (Test-Path $kb) {
    Copy-Item $kb $kbCopia
    Write-Host "OK $kbCopia ($((Get-Item $kbCopia).Length) bytes)"
} else {
    Write-Host "No existe $kb"
}
