param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

$ErrorActionPreference = 'Stop'

$mock = Join-Path $PSScriptRoot '..\scripts\mock-smart-search.mjs'
& node $mock @CliArgs
exit $LASTEXITCODE
