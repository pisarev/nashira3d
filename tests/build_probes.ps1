# Build the Pascal probes and benchmarks. Needs FPC 3.2.2.
#
# WHY A SEPARATE SCRIPT. mesh_probe.exe used to be built by hand, and the
# knowledge of how to do it lived only in someone's head. Delete build, and the
# battery started reporting a failure, because there was nothing left to check
# with. That is the right behaviour from the battery and the wrong shape for
# the tree: whatever a run depends on has to be built by a command, not by
# memory.
#
# The path to the compiler comes from FPC_EXE, or is looked up in PATH.
$ErrorActionPreference = 'Stop'

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here
$Core = Join-Path $Root 'core'
$Tp   = Join-Path $Root 'thirdparty\pascal-mathparser'
$Out  = Join-Path $Root 'build\probe'

if (-not (Test-Path (Join-Path $Tp 'src'))) {
    throw "the parser is missing: $Tp. Clone it at the tag v1.3.4"
}

$Fpc = if ($env:FPC_EXE) { $env:FPC_EXE } else { 'fpc.exe' }
New-Item -ItemType Directory -Force $Out | Out-Null

# The probes the battery runs, and the benchmarks that are run by hand.
$Targets = @('mesh_probe', 'cam_probe', 'bench_mesh', 'bench_adaptive')

Push-Location $Here
try {
    foreach ($t in $Targets) {
        # The artefact is deleted BEFORE the build: otherwise a failed build
        # leaves the previous exe, it runs, and it gives numbers from old code.
        $exe = Join-Path $Out "$t.exe"
        if (Test-Path $exe) { Remove-Item $exe -Force }

        & $Fpc -MDelphi -O2 -vw- -Sh -dNOFORMS -dNOGRAPHICS `
            "-FU$Out" "-FE$Out" `
            "-Fu$Core" "-Fu$Tp\src\compat" "-Fu$Tp\src" "-Fu$Tp\jit" "-Fi$Tp\src" `
            "$t.dpr"
        if ($LASTEXITCODE -ne 0) { throw "fpc returned $LASTEXITCODE on $t" }
        if (-not (Test-Path $exe)) { throw "fpc did not create $exe" }
        Write-Host "built: $exe $((Get-Item $exe).Length) bytes"
    }
}
finally { Pop-Location }
