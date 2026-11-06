# GTA card uploader - runs every few minutes from Task Scheduler.
#
# Anything dropped into the top of D:\gta-media (png, jpg, jpeg, webp) is sent
# to github.com/chanhofai/gta-media in ONE commit, under cards/. The Convert
# cards workflow there turns each into the 1080x1350 JPEG Instagram needs.
# Sent files are moved into D:\gta-media\uploaded so nothing goes twice.
#
# What happened is written to D:\gta-media\upload-log.txt.
# Plain ASCII on purpose: Windows PowerShell 5.1 misreads a script without a
# byte-order mark that contains anything else.

$ErrorActionPreference = 'Stop'
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root    = Split-Path -Parent $Here
$Done    = Join-Path $Root 'uploaded'
$Log     = Join-Path $Root 'upload-log.txt'
$Repo    = 'chanhofai/gta-media'
$Branch  = 'main'
$Api     = "https://api.github.com/repos/$Repo"
$MaxSize = 95MB          # GitHub's hard limit on one file is 100MB

function Log($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $Log -Value $line
    if ((Test-Path $Log) -and (Get-Item $Log).Length -gt 1MB) {
        $keep = Get-Content $Log -Tail 2000
        Set-Content -Path $Log -Value $keep
    }
}

# Only one copy at a time, even if Task Scheduler starts a second.
$mutex = New-Object System.Threading.Mutex($false, 'Local\GtaCardUploader')
if (-not $mutex.WaitOne(0)) { exit 0 }

try {
    # Files still being copied in are left for the next run.
    $cutoff = (Get-Date).AddSeconds(-30)
    $files = @(Get-ChildItem -Path $Root -File | Where-Object {
        $_.Extension -match '^\.(png|jpe?g|webp)$' -and
        $_.LastWriteTime -lt $cutoff -and $_.Length -gt 0
    })
    if ($files.Count -eq 0) { exit 0 }

    $big = @($files | Where-Object { $_.Length -gt $MaxSize })
    foreach ($f in $big) {
        Log ("SKIPPED {0}: {1:N0} MB is over GitHub's limit. Save it again as a JPG." -f $f.Name, ($f.Length / 1MB))
    }
    $files = @($files | Where-Object { $_.Length -le $MaxSize })
    if ($files.Count -eq 0) { exit 0 }

    # Windows PowerShell 5.1 does not offer TLS 1.2 by default; GitHub needs it.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    # The token was saved by install.ps1, encrypted so only this Windows
    # account on this PC can read it.
    $tokenFile = Join-Path $Here 'token.txt'
    if (-not (Test-Path $tokenFile)) { Log 'No token saved. Run install.bat again.'; exit 1 }
    $secure = Get-Content $tokenFile | ConvertTo-SecureString
    $bstr   = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $token  = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    $headers = @{
        Authorization          = "Bearer $token"
        Accept                 = 'application/vnd.github+json'
        'User-Agent'           = 'gta-card-uploader'
        'X-GitHub-Api-Version' = '2022-11-28'
    }
    function Call($method, $url, $json) {
        $p = @{ Method = $method; Uri = $url; Headers = $headers; UseBasicParsing = $true }
        if ($json) {
            $p.Body = [Text.Encoding]::UTF8.GetBytes($json)
            $p.ContentType = 'application/json'
        }
        return Invoke-RestMethod @p
    }

    # 1. One blob per file. The JSON is built by hand: ConvertTo-Json in
    #    PowerShell 5.1 refuses strings over about 2MB, and a PNG is bigger.
    $entries = @()
    foreach ($f in $files) {
        $b64  = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f.FullName))
        $blob = Call 'POST' "$Api/git/blobs" ('{"encoding":"base64","content":"' + $b64 + '"}')
        $entries += @{ path = "cards/$($f.Name)"; mode = '100644'; type = 'blob'; sha = $blob.sha }
    }

    # 2. One commit on top of the latest main. If the converter committed in
    #    the meantime, start again from the new tip rather than overwrite it.
    $names = ($files | ForEach-Object { $_.Name }) -join ', '
    $message = "Upload $($files.Count) card(s) from D:\gta-media`n`n$names"
    $pushed = $false
    for ($try = 1; $try -le 4 -and -not $pushed; $try++) {
        $ref    = Call 'GET' "$Api/git/ref/heads/$Branch"
        $parent = $ref.object.sha
        $commit = Call 'GET' "$Api/git/commits/$parent"
        $tree   = Call 'POST' "$Api/git/trees" (@{ base_tree = $commit.tree.sha; tree = $entries } | ConvertTo-Json -Depth 5)
        $new    = Call 'POST' "$Api/git/commits" (@{ message = $message; tree = $tree.sha; parents = @($parent) } | ConvertTo-Json -Depth 5)
        try {
            Call 'PATCH' "$Api/git/refs/heads/$Branch" (@{ sha = $new.sha; force = $false } | ConvertTo-Json) | Out-Null
            $pushed = $true
        } catch {
            if ($try -eq 4) { throw }
            Start-Sleep -Seconds (2 * $try)
        }
    }

    # 3. Out of the drop folder, so they are never sent twice.
    if (-not (Test-Path $Done)) { New-Item -ItemType Directory -Path $Done | Out-Null }
    foreach ($f in $files) {
        $dest = Join-Path $Done $f.Name
        if (Test-Path $dest) {
            $dest = Join-Path $Done ("{0}-{1}{2}" -f $f.BaseName, (Get-Date -Format 'yyyyMMddHHmmss'), $f.Extension)
        }
        Move-Item -Path $f.FullName -Destination $dest
    }
    Log "Uploaded $($files.Count): $names"

    # Keep the local 'uploaded' folder short too; GitHub keeps the history.
    Get-ChildItem -Path $Done -File | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
catch {
    $msg = $_.Exception.Message
    $code = $null
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($code -eq 401) { $msg = 'GitHub rejected the token (expired or revoked). Make a new one and run install.bat again.' }
    elseif ($code -eq 403 -or $code -eq 404) { $msg = "GitHub said $code. The token needs Contents: Read and write on chanhofai/gta-media. Make a new one and run install.bat again." }
    Log "FAILED, will retry on the next run: $msg"
    exit 1
}
finally {
    $mutex.ReleaseMutex()
}
