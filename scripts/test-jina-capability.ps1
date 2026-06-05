<#
.SYNOPSIS
Run isolated live checks for Smart Search Jina Reader capability.

.DESCRIPTION
This script intentionally uses a temporary SMART_SEARCH_CONFIG_DIR and clears
other web_fetch provider env vars for the current process while it runs, so
`smart-search fetch` must use Jina instead of being satisfied by Tavily or
Firecrawl first.

It never prints the Jina key. By default it reads JINA_API_KEY from the current
process env var or from the local Smart Search config file. You can also pass
`-JinaApiKey` explicitly.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\test-jina-capability.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\test-jina-capability.ps1 -Profile full -Modes default,readerlm-v2

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\test-jina-capability.ps1 -Urls "https://example.com","https://www.iana.org/help/example-domains" -Modes default
#>

[CmdletBinding()]
param(
    [string[]]$Urls,

    [ValidateSet("quick", "full")]
    [string]$Profile = "quick",

    [ValidateSet("default", "readerlm-v2")]
    [string[]]$Modes = @("default", "readerlm-v2"),

    [string]$JinaApiKey = $env:JINA_API_KEY,

    [string]$JinaReaderApiUrl = "https://r.jina.ai",

    [int]$TimeoutSeconds = 60,

    [string]$EvidenceDir = (Join-Path $env:TEMP ("smart-search-jina-evidence-" + (Get-Date -Format "yyyyMMdd-HHmmss"))),

    [switch]$KeepOtherFetchProviders
)

$ErrorActionPreference = "Stop"

function Get-SafeSlug {
    param([Parameter(Mandatory = $true)][string]$Text)
    $slug = $Text -replace '^https?://', ''
    $slug = $slug -replace '[^A-Za-z0-9._-]+', '-'
    $slug = $slug.Trim('-')
    if ($slug.Length -gt 70) {
        $slug = $slug.Substring(0, 70)
    }
    if (-not $slug) {
        return "url"
    }
    return $slug
}

function Get-SmartSearchConfigValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    $pathOutput = & smart-search config path --format json 2>&1
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    $pathText = ($pathOutput | Out-String).Trim()
    try {
        $pathData = $pathText | ConvertFrom-Json
    }
    catch {
        return $null
    }

    if (-not $pathData.config_file -or -not (Test-Path -LiteralPath $pathData.config_file)) {
        return $null
    }

    try {
        $configData = Get-Content -LiteralPath $pathData.config_file -Raw | ConvertFrom-Json
        return $configData.$Name
    }
    catch {
        return $null
    }
}

function ConvertFrom-SmartSearchJson {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [int]$ExitCode
    )

    $trimmed = $Text.Trim()
    $start = $trimmed.IndexOf("{")
    $end = $trimmed.LastIndexOf("}")
    if ($start -lt 0 -or $end -lt $start) {
        return [pscustomobject]@{
            ok = $false
            error_type = "parse_error"
            error = "smart-search did not return a JSON object"
            exit_code = $ExitCode
            raw = $trimmed
        }
    }

    $jsonText = $trimmed.Substring($start, $end - $start + 1)
    try {
        return $jsonText | ConvertFrom-Json
    }
    catch {
        return [pscustomobject]@{
            ok = $false
            error_type = "parse_error"
            error = $_.Exception.Message
            exit_code = $ExitCode
            raw = $trimmed
        }
    }
}

function Invoke-SmartSearchJson {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $output = & smart-search @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | Out-String).Trim()
    $data = ConvertFrom-SmartSearchJson -Text $text -ExitCode $exitCode
    if ($null -eq $data.exit_code) {
        $data | Add-Member -NotePropertyName exit_code -NotePropertyValue $exitCode -Force
    }
    return $data
}

function Save-JsonEvidence {
    param(
        [Parameter(Mandatory = $true)]$Data,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $Data | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath $Path -Encoding utf8
}

if (-not $Urls -or $Urls.Count -eq 0) {
    $Urls = @(
        "https://example.com",
        "https://www.iana.org/help/example-domains"
    )

    if ($Profile -eq "full") {
        $Urls += @(
            "https://www.rfc-editor.org/rfc/rfc2606.txt",
            "https://arxiv.org/pdf/1706.03762"
        )
    }
}

if (-not $JinaApiKey) {
    $JinaApiKey = Get-SmartSearchConfigValue -Name "JINA_API_KEY"
}
if (-not $JinaApiKey) {
    throw "JINA_API_KEY was not found. Pass -JinaApiKey or run 'smart-search setup --non-interactive --jina-key <key>' first."
}

New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
$TempConfigDir = Join-Path $env:TEMP ("smart-search-jina-config-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempConfigDir -Force | Out-Null

$envNamesToSave = @(
    "SMART_SEARCH_CONFIG_DIR",
    "JINA_API_KEY",
    "JINA_READER_API_URL",
    "JINA_RESPOND_WITH",
    "JINA_TIMEOUT_SECONDS"
)
if (-not $KeepOtherFetchProviders) {
    $envNamesToSave += @(
        "TAVILY_API_KEY",
        "FIRECRAWL_API_KEY",
        "ZHIPU_MCP_API_KEY"
    )
}

$savedEnv = @{}
foreach ($name in $envNamesToSave) {
    $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

try {
    [Environment]::SetEnvironmentVariable("SMART_SEARCH_CONFIG_DIR", $TempConfigDir, "Process")
    [Environment]::SetEnvironmentVariable("JINA_API_KEY", $JinaApiKey, "Process")
    [Environment]::SetEnvironmentVariable("JINA_READER_API_URL", $JinaReaderApiUrl, "Process")
    [Environment]::SetEnvironmentVariable("JINA_TIMEOUT_SECONDS", [string]$TimeoutSeconds, "Process")

    if (-not $KeepOtherFetchProviders) {
        foreach ($name in @("TAVILY_API_KEY", "FIRECRAWL_API_KEY", "ZHIPU_MCP_API_KEY")) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        }
    }

    Write-Host "Smart Search Jina capability test"
    Write-Host "smart-search : $((& smart-search --version 2>$null) -join ' ')"
    Write-Host "reader api   : $JinaReaderApiUrl"
    Write-Host "timeout      : $TimeoutSeconds seconds"
    Write-Host "temp config  : $TempConfigDir"
    Write-Host "evidence dir : $EvidenceDir"
    Write-Host "modes        : $($Modes -join ', ')"
    Write-Host ""

    [Environment]::SetEnvironmentVariable("JINA_RESPOND_WITH", $null, "Process")
    $doctor = Invoke-SmartSearchJson -Arguments @("doctor", "--format", "json")
    Save-JsonEvidence -Data $doctor -Path (Join-Path $EvidenceDir "00-doctor.json")

    $doctorSummary = [pscustomobject]@{
        ok = $doctor.ok
        minimum_profile_ok = $doctor.minimum_profile_ok
        web_fetch_configured = (($doctor.capability_status.web_fetch.configured | ForEach-Object { $_ }) -join ",")
        jina_status = $doctor.jina_connection_test.status
        missing = (($doctor.minimum_profile_missing | ForEach-Object { $_ }) -join ",")
    }
    Write-Host "Doctor summary"
    $doctorSummary | Format-List

    $summaries = New-Object System.Collections.Generic.List[object]
    $caseIndex = 0
    foreach ($mode in $Modes) {
        if ($mode -eq "readerlm-v2") {
            [Environment]::SetEnvironmentVariable("JINA_RESPOND_WITH", "readerlm-v2", "Process")
        }
        else {
            [Environment]::SetEnvironmentVariable("JINA_RESPOND_WITH", $null, "Process")
        }

        foreach ($url in $Urls) {
            $caseIndex += 1
            $slug = Get-SafeSlug -Text $url
            $jsonPath = Join-Path $EvidenceDir ("{0:D2}-{1}-{2}.json" -f $caseIndex, $mode, $slug)
            $contentPath = Join-Path $EvidenceDir ("{0:D2}-{1}-{2}.md" -f $caseIndex, $mode, $slug)

            Write-Host ("Running [{0}] mode={1} url={2}" -f $caseIndex, $mode, $url)
            $result = Invoke-SmartSearchJson -Arguments @("fetch", $url, "--format", "json")
            Save-JsonEvidence -Data $result -Path $jsonPath
            if ($result.content) {
                $result.content | Set-Content -LiteralPath $contentPath -Encoding utf8
            }

            $attempts = ""
            if ($result.provider_attempts) {
                $attempts = (($result.provider_attempts | ForEach-Object {
                    "{0}:{1}:{2}" -f $_.provider, $_.status, $_.error_type
                }) -join ",")
            }

            $content = [string]$result.content
            $preview = $content
            if ($preview.Length -gt 260) {
                $preview = $preview.Substring(0, 260)
            }
            $preview = ($preview -replace "\s+", " ").Trim()

            $summaries.Add([pscustomobject]@{
                case = $caseIndex
                mode = $mode
                ok = $result.ok
                provider = $result.provider
                fallback = $result.fallback_used
                content_len = $content.Length
                attempts = $attempts
                json = $jsonPath
                content = $(if ($result.content) { $contentPath } else { "" })
                preview = $preview
            })
        }
    }

    Write-Host ""
    Write-Host "Fetch summary"
    $summaries | Format-Table case, mode, ok, provider, fallback, content_len, attempts -AutoSize

    Write-Host ""
    Write-Host "Content preview"
    foreach ($item in $summaries) {
        Write-Host ("[{0}] {1} {2}" -f $item.case, $item.mode, $item.preview)
        Write-Host ""
    }

    $summaryPath = Join-Path $EvidenceDir "summary.json"
    Save-JsonEvidence -Data $summaries -Path $summaryPath
    Write-Host "Saved summary : $summaryPath"
    Write-Host "Saved details : $EvidenceDir"
    Write-Host ""
    Write-Host "Expected: provider should be 'jina'. If another provider appears, rerun without -KeepOtherFetchProviders."
}
finally {
    foreach ($name in $savedEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnv[$name], "Process")
    }
}
