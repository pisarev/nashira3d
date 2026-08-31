# Building the outside consumer of the seam under Windows.
#
# The compiler here is foreign ON PURPOSE: the core is built by fpc and the
# consumer by cl from Visual Studio. Should the layout of the table, the
# calling convention or the alignment of the fields drift apart, it is a
# foreign compiler that notices - our own binding could have been wrong in
# step with the core.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$out  = Join-Path $root "build/probe"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$vcvars = Get-ChildItem "C:\Program Files\Microsoft Visual Studio",
                        "C:\Program Files (x86)\Microsoft Visual Studio" `
          -Recurse -Filter "vcvars64.bat" -ErrorAction SilentlyContinue |
          Select-Object -First 1 -ExpandProperty FullName
if (-not $vcvars) { throw "vcvars64.bat not found: Visual Studio with C++ is required" }

$src = Join-Path $here "c_consumer.c"
$inc = Join-Path $root "include"
$exe = Join-Path $out  "c_consumer.exe"
$obj = Join-Path $out  "c_consumer.obj"

# The output of vcvars is silenced: it writes a harmless "vswhere.exe was not
# found" to the error stream, and with $ErrorActionPreference = Stop that fells
# a build which in fact went through. Measured 2026-08-31: cl did its work and
# the script declared a failure.
cmd /c "`"$vcvars`" >nul 2>&1 && cl /nologo /W4 /O1 /I `"$inc`" `"$src`" /Fe:`"$exe`" /Fo:`"$obj`""
if ($LASTEXITCODE -ne 0) { throw "cl returned $LASTEXITCODE" }
Write-Output "built: $exe"
Write-Output "run:   $exe $root/build/win64/nashira3d.dll"
