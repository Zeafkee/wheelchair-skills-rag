# test_rag_comparison.ps1 - RAG vs No-RAG (4 Model Comparison)

$baseUrl = "http://localhost:8000"

# Test edilecek ZOR beceriler
$questions = @(
    @{
        id = "1"
        name = "Rolls forwards 10m"
        question = "How do I roll forwards 10 meters in a wheelchair?"
        expectedActions = @("move_forward", "brake")
    },
    @{
        id = "4"
        name = "Turns while moving backwards 90deg"
        question = "How do I turn 90 degrees while moving backwards in a wheelchair?"
        expectedActions = @("move_backward", "turn_left", "turn_right")
    },
    @{
        id = "5"
        name = "Turns in place 180deg"
        question = "How do I turn 180 degrees in place while sitting in a wheelchair?"
        expectedActions = @("turn_left", "turn_right")
    },
    @{
        id = "6"
        name = "Maneuvers sideways 0.5m"
        question = "How do I maneuver my wheelchair sideways by half a meter?"
        expectedActions = @("move_forward", "move_backward", "turn_left", "turn_right")
    },
    @{
        id = "7"
        name = "Gets through hinged door"
        question = "How do I get through a hinged door while in a wheelchair?"
        expectedActions = @("move_forward", "move_backward", "turn_left", "turn_right", "brake")
    },
    @{
        id = "17"
        name = "Ascends 10deg incline"
        question = "How do I ascend a 10 degree incline ramp in a wheelchair?"
        expectedActions = @("move_forward", "brake")
    },
    @{
        id = "19"
        name = "Rolls across side-slope 5deg"
        question = "How do I roll across a 5 degree side slope in a wheelchair?"
        expectedActions = @("move_forward", "turn_left", "turn_right")
    },
    @{
        id = "21"
        name = "Gets over gap 15cm"
        question = "How do I get over a 15 centimeter gap in a wheelchair?"
        expectedActions = @("move_forward", "pop_casters")
    },
    @{
        id = "22"
        name = "Gets over threshold 2cm"
        question = "How do I get over a 2 centimeter threshold in a wheelchair?"
        expectedActions = @("move_forward", "pop_casters")
    },
    @{
        id = "25"
        name = "Ascends curb 15cm"
        question = "How do I ascend a 15 centimeter curb in a wheelchair?"
        expectedActions = @("move_forward", "pop_casters")
    },
    @{
        id = "27"
        name = "Performs stationary wheelie 30sec"
        question = "How do I perform a stationary wheelie for 30 seconds in a wheelchair?"
        expectedActions = @("pop_casters", "brake")
    },
    @{
        id = "28"
        name = "Turns in place in wheelie position 180deg"
        question = "How do I turn 180 degrees in place while in a wheelie position?"
        expectedActions = @("pop_casters", "turn_left", "turn_right")
    },
    @{
        id = "29"
        name = "Ascends 10deg incline in wheelie position"
        question = "How do I ascend a 10 degree incline while in a wheelie position?"
        expectedActions = @("pop_casters", "move_forward", "brake")
    },
    @{
        id = "30"
        name = "Ascends curb in wheelie position 15cm"
        question = "How do I ascend a 15 centimeter curb while in a wheelie position?"
        expectedActions = @("pop_casters", "move_forward", "brake")
    }
)

# 4 Model tanımı
$allModels = @(
    "rag-gpt-5-mini",
    "rag-gemini-3-flash",
    "norag-gpt-5-mini",
    "norag-gemini-3-flash"
)

# Modelleri kontrol et
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "   RAG vs NO-RAG COMPARISON (4 MODELS)" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Models being tested:" -ForegroundColor Cyan
Write-Host "  1. RAG + GPT-5-mini" -ForegroundColor Green
Write-Host "  2. RAG + Gemini-3-Flash" -ForegroundColor Green
Write-Host "  3. No-RAG GPT-5-mini" -ForegroundColor Yellow
Write-Host "  4. No-RAG Gemini-3-Flash" -ForegroundColor Yellow
Write-Host ""
Write-Host "Total Skills to Test:  $($questions.Count)" -ForegroundColor Cyan

try {
    $models = Invoke-RestMethod -Uri "$baseUrl/models/available" -Method GET
    Write-Host "OpenRouter Configured: $($models.openrouter_configured)" -ForegroundColor Green
}
catch {
    Write-Host "ERROR: Cannot connect to backend.  Is it running?" -ForegroundColor Red
    exit 1
}

# Skorlar - 4 model için
$scores = @{
    "rag-gpt-5-mini" = @{ correct = 0; total = 0 }
    "rag-gemini-3-flash" = @{ correct = 0; total = 0 }
    "norag-gpt-5-mini" = @{ correct = 0; total = 0 }
    "norag-gemini-3-flash" = @{ correct = 0; total = 0 }
}

# Rapor başlığı
$report = ""
$report += "===============================================================================`n"
$report += "         RAG vs NO-RAG COMPARISON TEST REPORT (4 MODELS)`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"
$report += "Total Skills Tested: $($questions.Count)`n"
$report += "`n"
$report += "Models Tested:`n"
$report += "  - RAG + GPT-5-mini (openai/gpt-5-mini)`n"
$report += "  - RAG + Gemini-3-Flash (google/gemini-3-flash-preview)`n"
$report += "  - No-RAG GPT-5-mini (openai/gpt-5-mini)`n"
$report += "  - No-RAG Gemini-3-Flash (google/gemini-3-flash-preview)`n"
$report += "`n"

# Her soru için test
$skillNum = 0
foreach ($q in $questions) {
    $skillNum++
    Write-Host "`n[$skillNum/$($questions.Count)] Testing: $($q. name)..." -ForegroundColor Cyan
    
    $report += "-------------------------------------------------------------------------------`n"
    $report += "SKILL #$($q.id): $($q.name)`n"
    $report += "QUESTION: $($q. question)`n"
    $report += "EXPECTED ACTIONS:  $($q.expectedActions -join ', ')`n"
    $report += "-------------------------------------------------------------------------------`n"
    
    # Compare endpoint çağır - 4 model için
    $body = @{
        question = $q. question
        models = @("gpt-5-mini", "gemini-3-flash")
        rag_models = @("gpt-5-mini", "gemini-3-flash")
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "$baseUrl/ask/practice/compare" -Method POST -Body $body -ContentType "application/json"
        
        foreach ($modelKey in $allModels) {
            $result = $response.comparison.$modelKey
            
            if ($null -eq $result) {
                $report += "`n[$modelKey] NO RESULT`n"
                Write-Host "  [$modelKey] NO RESULT" -ForegroundColor Red
                continue
            }
            
            if ($result.error) {
                $report += "`n[$modelKey] ERROR: $($result. error)`n"
                Write-Host "  [$modelKey] ERROR: $($result.error)" -ForegroundColor Red
                continue
            }
            
            $modelName = $result.model
            $ragLabel = if ($result.rag_used) { "RAG" } else { "No-RAG" }
            $report += "`n[$modelKey] $ragLabel - Model: $modelName`n"
            $report += "Steps: $($result. step_count)`n"
            
            # Action doğruluğunu kontrol et
            $foundActions = @()
            foreach ($step in $result.steps) {
                $actions = $step.expected_actions -join ', '
                foreach ($action in $step.expected_actions) {
                    if ($action -and $action -ne "") {
                        $foundActions += $action
                    }
                }
                $stepText = $step.text
                if ($stepText. Length -gt 55) {
                    $stepText = $stepText.Substring(0, 55) + "..."
                }
                $report += "  Step $($step.step_number): [$actions] $stepText`n"
            }
            
            # Doğru action sayısı
            $correctCount = 0
            $missingActions = @()
            $foundUnique = $foundActions | Select-Object -Unique
            foreach ($expected in $q.expectedActions) {
                if ($foundUnique -contains $expected) {
                    $correctCount++
                }
                else {
                    $missingActions += $expected
                }
            }
            
            $accuracy = 0
            if ($q.expectedActions.Count -gt 0) {
                $accuracy = [math]::Round(($correctCount / $q.expectedActions. Count) * 100)
            }
            
            $report += "  Found: $($foundUnique -join ', ')`n"
            if ($missingActions. Count -gt 0) {
                $report += "  MISSING: $($missingActions -join ', ')`n"
            }
            $report += "  ACCURACY: $correctCount/$($q.expectedActions.Count) ($accuracy%)`n"
            
            # Renk ile göster
            $shortKey = $modelKey.Replace("rag-", "R: ").Replace("norag-", "N:")
            if ($accuracy -ge 80) {
                Write-Host "  [$shortKey] $accuracy%" -ForegroundColor Green
            }
            elseif ($accuracy -ge 50) {
                Write-Host "  [$shortKey] $accuracy%" -ForegroundColor Yellow
            }
            else {
                Write-Host "  [$shortKey] $accuracy%" -ForegroundColor Red
            }
            
            $scores[$modelKey]. correct += $correctCount
            $scores[$modelKey]. total += $q. expectedActions.Count
        }
    }
    catch {
        $report += "ERROR: $($_. Exception.Message)`n"
        Write-Host "  ERROR:  $($_.Exception. Message)" -ForegroundColor Red
    }
    
    $report += "`n"
}

# Özet
$report += "===============================================================================`n"
$report += "                              SUMMARY`n"
$report += "===============================================================================`n"
$report += "`n"

Write-Host "`n" -NoNewline
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "                 SUMMARY" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta

# Sonuçları sırala
$sortedResults = @()
foreach ($modelKey in $allModels) {
    $s = $scores[$modelKey]
    $pct = 0
    if ($s.total -gt 0) {
        $pct = [math]::Round(($s.correct / $s.total) * 100, 1)
    }
    $sortedResults += @{
        key = $modelKey
        correct = $s.correct
        total = $s.total
        pct = $pct
    }
}
$sortedResults = $sortedResults | Sort-Object -Property pct -Descending

# Sıralı göster
$rank = 0
foreach ($r in $sortedResults) {
    $rank++
    
    switch ($r.key) {
        "rag-gpt-5-mini" { $label = "RAG + GPT-5-mini      " }
        "rag-gemini-3-flash" { $label = "RAG + Gemini-3-Flash  " }
        "norag-gpt-5-mini" { $label = "No-RAG GPT-5-mini     " }
        "norag-gemini-3-flash" { $label = "No-RAG Gemini-3-Flash " }
    }
    
    # Progress bar
    $bar = ""
    $barLen = [math]::Round($r.pct / 5)
    for ($i = 0; $i -lt 20; $i++) {
        if ($i -lt $barLen) {
            $bar += "#"
        }
        else {
            $bar += "-"
        }
    }
    
    $medal = ""
    if ($rank -eq 1) { $medal = "[1st]" }
    elseif ($rank -eq 2) { $medal = "[2nd]" }
    elseif ($rank -eq 3) { $medal = "[3rd]" }
    elseif ($rank -eq 4) { $medal = "[4th]" }
    
    $report += "$medal $label :  $($r.correct)/$($r.total) ($($r.pct)%)`n"
    $report += "      [$bar]`n"
    $report += "`n"
    
    if ($r.pct -ge 80) {
        Write-Host "$medal $label : $($r.correct)/$($r.total) ($($r.pct)%) [$bar]" -ForegroundColor Green
    }
    elseif ($r. pct -ge 50) {
        Write-Host "$medal $label : $($r.correct)/$($r.total) ($($r.pct)%) [$bar]" -ForegroundColor Yellow
    }
    else {
        Write-Host "$medal $label : $($r. correct)/$($r.total) ($($r.pct)%) [$bar]" -ForegroundColor Red
    }
}

# RAG vs No-RAG karşılaştırması
$ragAvg = 0
$noragAvg = 0
$ragCount = 0
$noragCount = 0

foreach ($r in $sortedResults) {
    if ($r.key -like "rag-*") {
        $ragAvg += $r. pct
        $ragCount++
    }
    else {
        $noragAvg += $r. pct
        $noragCount++
    }
}

if ($ragCount -gt 0) { $ragAvg = $ragAvg / $ragCount }
if ($noragCount -gt 0) { $noragAvg = $noragAvg / $noragCount }

$improvement = $ragAvg - $noragAvg

$report += "-------------------------------------------------------------------------------`n"
$report += "`n"
$report += "RAG vs No-RAG Comparison:`n"
$report += "  RAG Average:      $([math]::Round($ragAvg, 1))%`n"
$report += "  No-RAG Average:  $([math]:: Round($noragAvg, 1))%`n"
if ($improvement -ge 0) {
    $report += "  RAG IMPROVEMENT: +$([math]::Round($improvement, 1))%`n"
}
else {
    $report += "  RAG IMPROVEMENT: $([math]::Round($improvement, 1))%`n"
}
$report += "`n"
$report += "===============================================================================`n"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "          RAG vs NO-RAG COMPARISON" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  RAG Average:     $([math]::Round($ragAvg, 1))%" -ForegroundColor Cyan
Write-Host "  No-RAG Average:  $([math]::Round($noragAvg, 1))%" -ForegroundColor Yellow

if ($improvement -gt 0) {
    Write-Host ""
    Write-Host "  RAG IMPROVEMENT: +$([math]::Round($improvement, 1))%" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "  RAG IMPROVEMENT: $([math]::Round($improvement, 1))%" -ForegroundColor Red
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta

# Sonucu kaydet
$reportPath = "rag_comparison_4models_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
$report | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "`nReport saved to: $reportPath" -ForegroundColor Green