param(
    [string]$Python = "C:\Users\Timon\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    # 이미지 재제작·재삽입에 쓰는 Python(numpy, Pillow, opencv 필요). 비우면 이미지 단계를 건너뛴다.
    [string]$ImagePython = "python",
    [switch]$SkipImages
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }

if (-not $SkipImages -and $ImagePython) {
    # 재제작 PNG → 게임 텍스처(assets/images/native) 순서: SLG 이름판, 스태프롤, UI, 로고, 재삽입
    foreach ($step in 'remake_slg_plates', 'remake_staff_roll', 'remake_ui', 'remake_logo', 'inject_images') {
        & $ImagePython "$PSScriptRoot\src\$step.py"
        if ($LASTEXITCODE -ne 0) { throw "이미지 단계 실패: $step" }
    }
}

& $Python "$PSScriptRoot\src\build.py"
if ($LASTEXITCODE -ne 0) { throw '빌드 검증 실패. 출력 파일은 기존 것 그대로입니다. out/build-report.json을 확인하세요.' }
