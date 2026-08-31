param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

$mock = Join-Path $PSScriptRoot '..\scripts\mock-smart-search.mjs'
& node $mock @CliArgs
exit $LASTEXITCODE
