param(
    [ValidateSet('Start','Stop','Resume','Snapshot','Status')][string]$Action = 'Start',
    [string]$Revision = 'dev/v2-05-ontology-prefill',
    [string]$Repository = '',
    [string]$RunId = '',
    [ValidateRange(1,65535)][int]$Port = 8000,
    [string]$ProviderConfigFile = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$archive = Join-Path $root 'data/exports/docker'
$inputDir = Join-Path $root 'data/input'
New-Item -ItemType Directory -Force -Path $archive,$inputDir | Out-Null
foreach ($tool in @('Dockerfile','report.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $tool) -PathType Leaf)) { throw "Missing $tool" }
}
function Native([string]$program,[string[]]$arguments) {
    $ErrorActionPreference = 'Continue'
    $output = & $program @arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "$program failed ($LASTEXITCODE): $output" }
    return $output
}
function NativeLog([string]$path,[string[]]$arguments) {
    $ErrorActionPreference = 'Continue'
    & docker @arguments *> $path
    return $LASTEXITCODE
}
function RunPath {
    if ($RunId -notmatch '^run-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$') { throw 'Specify a valid -RunId.' }
    $path = Join-Path $archive $RunId
    if (-not (Test-Path -LiteralPath (Join-Path $path 'metadata.json') -PathType Leaf)) { throw "Unknown run: $RunId" }
    return $path
}
function Health([string]$path) {
    $meta = Get-Content -LiteralPath (Join-Path $path 'metadata.json') -Raw | ConvertFrom-Json
    $credential = Join-Path (Join-Path $archive '.credentials') "$($meta.run_id).env"
    if (-not (Test-Path -LiteralPath $credential -PathType Leaf)) { throw 'Run credential file is missing.' }
    $password = ((Get-Content -LiteralPath $credential | Where-Object { $_ -like 'PHOTO_EDITOR_ACCESS_PASSWORD=*' }) -split '=',2)[1]
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("owner:$password"))
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        try {
            $url = "http://127.0.0.1:$($meta.port)/api/health"
            $response = Invoke-WebRequest -Uri $url -Headers @{Authorization="Basic $encoded"} -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200 -and ($response.Content | ConvertFrom-Json).status -eq 'ok') {
                $meta | Add-Member -NotePropertyName health_status -NotePropertyValue 'PASS' -Force
                $meta | Add-Member -NotePropertyName health_checked_at_utc -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
                $meta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $path 'metadata.json') -Encoding UTF8
                Write-Host "Ready: http://localhost:$($meta.port)/  username: owner  password: $password"
                return
            }
        } catch { Start-Sleep -Seconds 2 }
    }
    throw "Health check failed; inspect $(Join-Path $path 'logs')."
}
function Report([string]$path) {
    $meta = Get-Content -LiteralPath (Join-Path $path 'metadata.json') -Raw | ConvertFrom-Json
    $workspace = Join-Path $path 'workspace'
    Native docker @('run','--rm','--mount',"type=bind,source=$workspace,target=/workspace",
        '--mount',"type=bind,source=$path,target=/evaluation",
        '--mount',"type=bind,source=$inputDir,target=/host-input,readonly",
        '--workdir','/workspace',$meta.image_tag,'.venv/bin/python','/evaluation/tools/report.py',
        '--state','stopped') | Out-Null
    Write-Host "Report: $(Join-Path $path 'evaluation-report.md')"
}
if ("$(Native docker @('info','--format','{{.OSType}}'))".Trim() -ne 'linux') {
    throw 'Docker Desktop must use the Linux container backend.'
}
if ($Action -ne 'Start') {
    $path = RunPath
    $meta = Get-Content -LiteralPath (Join-Path $path 'metadata.json') -Raw | ConvertFrom-Json
    $container = $meta.container_name
    $status = "$(Native docker @('inspect','--format','{{.State.Status}}',$container))".Trim()
    if ($Action -eq 'Status') { Write-Host "$RunId : $status : $(Join-Path $path 'workspace')"; return }
    if ($Action -eq 'Resume') {
        if ($status -ne 'running') { Native docker @('start',$container) | Out-Null }
        Health $path
        return
    }
    if ($status -eq 'running') { Native docker @('stop','--time','120',$container) | Out-Null }
    if ((NativeLog (Join-Path $path 'logs/server.log') @('logs',$container)) -ne 0) { throw 'Could not save container logs.' }
    Report $path
    Write-Host "Workspace preserved: $(Join-Path $path 'workspace')"
    return
}
if ($RunId) { throw '-RunId is for an existing run.' }
$probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('127.0.0.1'),$Port)
try { $probe.Start() }
catch { throw "Host port $Port is in use; choose -Port with a free port." }
finally { $probe.Stop() }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required.' }
if (-not $Repository) { $Repository = "$(Native git @('-C',$root,'remote','get-url','origin'))".Trim() }
if (-not $Repository) { throw 'Specify -Repository.' }
try {
$repositoryUrl = $Repository
if (Test-Path -LiteralPath $Repository) {
    $sourceRepo = (Resolve-Path -LiteralPath $Repository).Path
    try { $repositoryUrl = "$(Native git @('-C',$sourceRepo,'remote','get-url','origin'))".Trim() }
    catch { $repositoryUrl = "file:///$($sourceRepo.Replace('\','/'))" }
}
$RunId = 'run-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$path = Join-Path $archive $RunId
$workspace = Join-Path $path 'workspace'
$logs = Join-Path $path 'logs'
$results = Join-Path $path 'test-results'
$toolsDir = Join-Path $path 'tools'
New-Item -ItemType Directory -Force -Path $path,$logs,$results,$toolsDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'report.py') -Destination (Join-Path $toolsDir 'report.py')
Write-Host "Run: $RunId"
Native git @('clone','--no-local','--no-checkout',$Repository,$workspace) | Out-Null
$candidate = "refs/remotes/origin/$Revision" + '^{commit}'
$ErrorActionPreference = 'Continue'
& git -C $workspace rev-parse --verify $candidate *> $null
$ErrorActionPreference = 'Stop'
if ($LASTEXITCODE -eq 0) {
    $sha = "$(Native git @('-C',$workspace,'rev-parse','--verify',$candidate))".Trim()
} else {
    $sha = "$(Native git @('-C',$workspace,'rev-parse','--verify',($Revision + '^{commit}')))".Trim()
}
Native git @('-C',$workspace,'checkout','--detach',$sha) | Out-Null
foreach ($required in @('requirements.lock','frontend/package-lock.json','scripts/setup_env.py',
    'scripts/frontend_bundle.py','backend/review/__main__.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $required) -PathType Leaf)) { throw "Revision lacks $required" }
}
$workspaceInput = Join-Path $workspace 'data/input'
New-Item -ItemType Directory -Force -Path $workspaceInput | Out-Null
if ((Get-Item -LiteralPath $inputDir).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'data/input itself is a reparse point; use a real directory for evaluation.'
}
$links = @(Get-ChildItem -LiteralPath $inputDir -Force -Recurse | Where-Object {
    $_.Attributes -band [IO.FileAttributes]::ReparsePoint
})
if ($links.Count) { throw 'data/input contains a reparse point; remove links before evaluation.' }
$inputs = @()
foreach ($file in @(Get-ChildItem -LiteralPath $inputDir -File -Force -Recurse)) {
    $relative = $file.FullName.Substring($inputDir.Length).TrimStart([char]'\',[char]'/')
    $target = Join-Path $workspaceInput $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    Copy-Item -LiteralPath $file.FullName -Destination $target
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) {
        throw "Input copy checksum mismatch: $relative"
    }
    $inputs += @{path=$relative.Replace('\','/'); sha256=$hash}
}
if ($inputs.Count) { $inputs | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $path 'input-checksums.json') -Encoding UTF8 }
else { '[]' | Set-Content -LiteralPath (Join-Path $path 'input-checksums.json') -Encoding UTF8 }
$imageTag = "photo-mass-editor-eval:$($RunId.ToLowerInvariant())"
$container = "photo-mass-editor-$($RunId.ToLowerInvariant())"
$buildLog = Join-Path $logs 'docker-build.log'
if ((NativeLog $buildLog @('build','--tag',$imageTag,'--file',(Join-Path $PSScriptRoot 'Dockerfile'),$workspace)) -ne 0) {
    throw "Docker build failed; see $buildLog"
}
$imageId = "$(Native docker @('image','inspect','--format','{{.Id}}',$imageTag))".Trim()
Native docker @('run','--rm','--mount',"type=bind,source=$workspace,target=/evaluation-workspace",
    '--entrypoint','/bin/sh',$imageTag,'-c','cp -a /workspace/. /evaluation-workspace/') | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $workspace '.venv/bin/python') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $workspace 'frontend/dist/index.html') -PathType Leaf)) {
    throw 'Image did not contain the canonical environment and production frontend.'
}
$credentialDir = Join-Path $archive '.credentials'
New-Item -ItemType Directory -Force -Path $credentialDir | Out-Null
$bytes = New-Object byte[] 24
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$password = [Convert]::ToBase64String($bytes).TrimEnd('=') -replace '\+','-' -replace '/','_'
$credential = Join-Path $credentialDir "$RunId.env"
@("PHOTO_EDITOR_ACCESS_PASSWORD=$password",'PHOTO_EDITOR_ALLOWED_HOSTS=localhost,127.0.0.1') |
    Set-Content -LiteralPath $credential -Encoding ASCII
if ($ProviderConfigFile) {
    if (-not (Test-Path -LiteralPath $ProviderConfigFile -PathType Leaf)) {
        throw 'Provider config file is missing.'
    }
    $ProviderConfigFile = (Resolve-Path -LiteralPath $ProviderConfigFile).Path
    if ($ProviderConfigFile.StartsWith(($path + [IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Provider config must stay outside the run archive.'
    }
}
$metadata = @{
    run_id=$RunId; repository=$repositoryUrl; checkout_source=$Repository; revision=$Revision; commit_sha=$sha
    started_at_utc=[DateTime]::UtcNow.ToString('o'); port=$Port; image_tag=$imageTag
    image_id=$imageId; container_name=$container; input_count=$inputs.Count
    health_status='NOT_RUN'; health_checked_at_utc=''
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $path 'metadata.json') -Encoding UTF8
$tests = @()
foreach ($check in @(
    @{name='python-unittest'; command=@('.venv/bin/python','-m','unittest','discover','-s','tests','-v')},
    @{name='frontend-vitest'; command=@('npm','--prefix','frontend','test')},
    @{name='frontend-build'; command=@('npm','--prefix','frontend','run','build')}
)) {
    $log = Join-Path $results "$($check.name).log"
    $dockerArgs = @('run','--rm','--mount',"type=bind,source=$workspace,target=/workspace",
        '--workdir','/workspace',$imageTag) + $check.command
    $passed = (NativeLog $log $dockerArgs) -eq 0
    $tests += @{name=$check.name;status=$(if ($passed) {'PASS'} else {'FAIL'});log="test-results/$($check.name).log"}
    $tests | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $results 'results.json') -Encoding UTF8
    if (-not $passed) { throw "$($check.name) failed; see $log. Run retained at $path" }
}
$dockerArgs = @('run','--detach','--name',$container,'--publish',"127.0.0.1:${Port}:8000",
    '--mount',"type=bind,source=$workspace,target=/workspace",
    '--env-file',$credential,'--workdir','/workspace')
if ($ProviderConfigFile) {
    $dockerArgs += @('--mount',"type=bind,source=$ProviderConfigFile,target=/workspace/config/openAI.env,readonly")
}
$dockerArgs += $imageTag
Native docker $dockerArgs | Out-Null
Health $path
Write-Host "Workspace: $workspace"
Write-Host "Stop and preserve: .\scripts\docker\evaluate.ps1 -Action Snapshot -RunId $RunId"
} catch {
    if ($path -and (Test-Path -LiteralPath $path -PathType Container)) {
        $failure = ($_.Exception.Message -replace '[\r\n]+',' ').Replace('|','/')
        $lines = @(
            '# Local Docker evaluation failure report','',
            "- Run ID: $RunId",
            "- Evaluated at UTC: $([DateTime]::UtcNow.ToString('o'))",
            "- Requested repository: $Repository",
            "- Requested revision: $Revision",
            "- Exact commit: $(if ($sha) { $sha } else { 'NOT_RUN' })",
            "- Result: FAIL - $failure",
            "- Workspace: $workspace (retained for inspection)",
            '', '## Automated checks', ''
        )
        $completed = @{}
        $resultFile = Join-Path $path 'test-results/results.json'
        if (Test-Path -LiteralPath $resultFile -PathType Leaf) {
            foreach ($item in @(Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json)) {
                $completed[$item.name] = $item.status
            }
        }
        foreach ($name in @('python-unittest','frontend-vitest','frontend-build')) {
            $status = if ($completed.ContainsKey($name)) { $completed[$name] } else { 'NOT_RUN' }
            $lines += "- ${name}: $status"
        }
        $lines += @('', 'Startup, SQLite integrity, checksum and workspace recovery: NOT_RUN unless separately checked.',
            'Inspect logs/ and test-results/ for the failed step. No paid API call was made by the launcher.')
        $lines | Set-Content -LiteralPath (Join-Path $path 'evaluation-report.md') -Encoding UTF8
    }
    throw
}
