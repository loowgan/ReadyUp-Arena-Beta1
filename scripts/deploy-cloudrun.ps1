param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$Service = "readyup-arena-api",
    [string]$Repository = "readyup-arena"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$envFile = Join-Path $backendDir "cloudrun.env"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI introuvable dans le PATH. Installe Google Cloud SDK avant de lancer ce script."
}

if (-not (Test-Path $envFile)) {
    throw "Fichier d'environnement introuvable: $envFile"
}

$envContent = Get-Content $envFile -Raw
if ($envContent.Contains("REPLACE_WITH_")) {
    Write-Warning "backend/cloudrun.env contient encore des placeholders REPLACE_WITH_. Le service peut se deployer, mais les liens publics et le CORS seront faux tant que tu ne les remplaces pas."
}

$image = "$Region-docker.pkg.dev/$ProjectId/$Repository/$Service`:latest"

Write-Host "Activation des APIs Cloud Run / Cloud Build / Artifact Registry..."
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    --project $ProjectId | Out-Host

$repoExists = $true
try {
    gcloud artifacts repositories describe $Repository `
        --location $Region `
        --project $ProjectId | Out-Null
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    Write-Host "Creation du repository Artifact Registry $Repository..."
    gcloud artifacts repositories create $Repository `
        --repository-format=docker `
        --location=$Region `
        --project=$ProjectId | Out-Host
}

Write-Host "Build de l'image backend..."
gcloud builds submit $backendDir `
    --tag $image `
    --project $ProjectId | Out-Host

Write-Host "Deploiement Cloud Run..."
gcloud run deploy $Service `
    --image $image `
    --project $ProjectId `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --env-vars-file $envFile | Out-Host

Write-Host ""
Write-Host "Deploiement termine."
Write-Host "Met a jour BACKEND_PUBLIC_URL, FRONTEND_URL et CORS_ORIGINS dans backend/cloudrun.env si besoin, puis relance le script."
