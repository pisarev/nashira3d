# Build the core on Windows. Needs FPC 3.2.2.
#
# The path to the compiler comes from FPC_EXE, or is looked up in PATH. It must
# not be nailed down: it sits in different places on different machines, and
# past releases have already tripped over that.
$ErrorActionPreference = 'Stop'

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here
$Tp   = Join-Path $Root 'thirdparty\pascal-mathparser'
$Out  = Join-Path $Root 'build\win64'

if (-not (Test-Path (Join-Path $Tp 'src'))) {
    throw "the parser is missing: $Tp. Clone it at the tag v1.3.4"
}

$Fpc = if ($env:FPC_EXE) { $env:FPC_EXE } else { 'fpc.exe' }
New-Item -ItemType Directory -Force $Out | Out-Null

# The old library is deleted BEFORE the build. Otherwise the check at the end
# passes over SOMEONE ELSE'S file: the compiler failed, last time's dll is
# still there, and the script says "built". That once cost a false conclusion
# about a fix that was not working.
$Lib = Join-Path $Out 'nashira3d.dll'
if (Test-Path $Lib) { Remove-Item $Lib -Force }

Push-Location $Here
try {
    & $Fpc -MDelphi -O2 -vw- -Sh -dNOFORMS -dNOGRAPHICS `
        "-FU$Out" "-FE$Out" `
        "-Fu$Tp\src\compat" "-Fu$Tp\src" "-Fu$Tp\jit" "-Fi$Tp\src" `
        nashira3d.lpr
    if ($LASTEXITCODE -ne 0) { throw "fpc returned $LASTEXITCODE" }
} finally {
    Pop-Location
}

if (-not (Test-Path $Lib)) { throw "the build said nothing, but there is no library: $Lib" }
"built: $Lib $((Get-Item $Lib).Length) bytes"
