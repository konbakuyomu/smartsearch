<#
.SYNOPSIS
  Make this Windows account trust the Smart Search self-signed code-signing certificate (opt-in).

  Imports only the public certificate committed in the repository into the current user's
  "Trusted Root Certification Authorities" and "Trusted Publishers" stores, after checking it
  holds no private key, is limited to code signing and is within its validity period.
  Windows asks for confirmation before adding a root certificate. Afterwards files signed by
  Smart Search verify as trusted on this machine (Get-AuthenticodeSignature: Valid).

  This does not create SmartScreen reputation: a Setup.exe downloaded with a browser can still
  show the SmartScreen prompt; installing from a local build or updating inside the app does not.
  Trust only a certificate whose SHA-256 you have compared with the one published in the README.

.EXAMPLE
  ./desktop/scripts/Trust-WindowsSigningCertificate.ps1
  ./desktop/scripts/Trust-WindowsSigningCertificate.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string] $CertificatePath = (Join-Path $PSScriptRoot '../packaging/windows/smart-search.cer'),
    [switch] $Remove
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Windows-Signing.ps1')

$certificate = Get-ExpectedSigningCertificate $CertificatePath
try {
    $sha256 = $certificate.GetCertHashString([Security.Cryptography.HashAlgorithmName]::SHA256)
    Write-Output "Certificate: $($certificate.Subject)  SHA-256 $sha256  valid until $($certificate.NotAfter.ToString('yyyy-MM-dd'))"
    foreach ($name in @('Root', 'TrustedPublisher')) {
        $store = [Security.Cryptography.X509Certificates.X509Store]::new($name, 'CurrentUser')
        try {
            $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
            $present = @($store.Certificates | Where-Object Thumbprint -eq $certificate.Thumbprint)
            if ($Remove) {
                foreach ($item in $present) { $store.Remove($item) }
                Write-Output "  CurrentUser\$name`: $(if ($present) { 'removed' } else { 'was not present' })"
            }
            elseif ($present) {
                Write-Output "  CurrentUser\$name`: already trusted"
            }
            else {
                if ($name -eq 'Root') { Assert-SigningCertificate $certificate $certificate }
                $store.Add($certificate)  # Root: Windows shows a confirmation dialog
                $added = @($store.Certificates | Where-Object Thumbprint -eq $certificate.Thumbprint)
                if (-not $added) { throw "CurrentUser\$name`: not added (confirmation declined?)" }
                Write-Output "  CurrentUser\$name`: added"
            }
        }
        finally { $store.Close() }
    }
}
finally { $certificate.Dispose() }
