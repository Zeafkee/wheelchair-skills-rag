# test_rag_comparison.ps1 - RAG vs No-RAG Karşılaştırma Testi (Hard Skills)

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
        id = "18"
        name = "Descends 10deg incline"
        question = "How do I descend a 10 degree incline ramp in a wheelchair safely?"
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
        id = "26"
        name = "Descends curb 15cm"
        question = "How do I descend a 15 centimeter curb in a wheelchair safely?"
        expectedActions = @("move_backward", "pop_casters", "brake")
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
        name = "Descends 10deg incline in wheelie position"
        question = "How do I descend a 10 degree incline while in a wheelie position?"
        expectedActions = @("pop_casters", "move_forward", "brake")
    },
    @{
        id = "30"
        name = "Descends curb in wheelie position 15cm"
        question = "How do I descend a 15 centimeter curb while in a wheelie position?"
        expectedActions = @("pop_casters", "move_forward", "brake")
    }
)

# Modelleri kontrol et
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "   RAG vs NO-RAG COMPARISON TEST (HARD MODE)" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Checking available models..." -ForegroundColor Cyan
try {
    $models = Invoke-RestMethod -Uri "$baseUrl/models/available" -Method GET
    Write-Host "RAG Model: $($models. rag_model)" -ForegroundColor Green
    Write-Host "OpenRouter Configured: $($models.openrouter_configured)" -ForegroundColor Green
    Write-Host "Total Skills to Test: $($questions.Count)" -ForegroundColor Yellow
}
catch {
    Write-Host "ERROR: Cannot connect to backend.  Is it running?" -ForegroundColor Red
    exit 1
}

# Skorlar
$scores = @{
    "rag" = @{ correct = 0; total = 0 }
    "gpt-5-mini" = @{ correct = 0; total = 0 }
    "gemini-3-flash" = @{ correct = 0; total = 0 }
}

# Detaylı sonuçlar
$detailedResults = @{
    "rag" = @()
    "gpt-5-mini" = @()
    "gemini-3-flash" = @()
}

# Rapor başlığı
$report = ""
$report += "===============================================================================`n"
$report += "         RAG vs NO-RAG COMPARISON TEST REPORT (HARD MODE)`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "Test Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"
$report += "Total Skills Tested: $($questions.Count)`n"
$report += "`n"

# Her soru için test
$skillNum = 0
foreach ($q in $questions) {
    $skillNum++
    Write-Host "`n[$skillNum/$($questions.Count)] Testing: $($q. name)..." -ForegroundColor Cyan
    
    $report += "-------------------------------------------------------------------------------`n"
    $report += "SKILL #$($q.id): $($q.name)`n"
    $report += "QUESTION: $($q.question)`n"
    $report += "EXPECTED ACTIONS: $($q. expectedActions -join ', ')`n"
    $report += "-------------------------------------------------------------------------------`n"
    
    # Compare endpoint çağır
    $body = @{
        question = $q.question
        models = @("gpt-5-mini", "gemini-3-flash")
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "$baseUrl/ask/practice/compare" -Method POST -Body $body -ContentType "application/json"
        
        foreach ($modelKey in @("rag", "gpt-5-mini", "gemini-3-flash")) {
            $result = $response.comparison.$modelKey
            
            if ($null -eq $result) {
                $report += "`n[$modelKey] NO RESULT`n"
                Write-Host "  [$modelKey] NO RESULT" -ForegroundColor Red
                continue
            }
            
            if ($result. error) {
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
                if ($stepText. Length -gt 60) {
                    $stepText = $stepText.Substring(0, 60) + "..."
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
            
            $report += "  Found Actions: $($foundUnique -join ', ')`n"
            if ($missingActions. Count -gt 0) {
                $report += "  MISSING Actions: $($missingActions -join ', ')`n"
            }
            $report += "  ACCURACY: $correctCount/$($q.expectedActions. Count) ($accuracy%)`n"
            
            # Detaylı sonuç kaydet
            $detailedResults[$modelKey] += @{
                skill = $q.name
                accuracy = $accuracy
                missing = $missingActions
            }
            
            # Renk ile göster
            if ($accuracy -ge 80) {
                Write-Host "  [$modelKey] $accuracy% ($correctCount/$($q. expectedActions.Count))" -ForegroundColor Green
            }
            elseif ($accuracy -ge 50) {
                Write-Host "  [$modelKey] $accuracy% ($correctCount/$($q.expectedActions.Count))" -ForegroundColor Yellow
            }
            else {
                Write-Host "  [$modelKey] $accuracy% ($correctCount/$($q. expectedActions.Count))" -ForegroundColor Red
            }
            
            $scores[$modelKey]. correct += $correctCount
            $scores[$modelKey].total += $q.expectedActions.Count
        }
    }
    catch {
        $report += "ERROR: $($_.Exception.Message)`n"
        Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
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

foreach ($modelKey in @("rag", "gpt-5-mini", "gemini-3-flash")) {
    $s = $scores[$modelKey]
    $pct = 0
    if ($s.total -gt 0) {
        $pct = [math]::Round(($s.correct / $s.total) * 100, 1)
    }
    
    switch ($modelKey) {
        "rag" { $label = "RAG + GPT-5-mini      " }
        "gpt-5-mini" { $label = "No-RAG GPT-5-mini    " }
        "gemini-3-flash" { $label = "No-RAG Gemini 3 Flash" }
    }
    
    # Progress bar
    $bar = ""
    $barLen = [math]::Round($pct / 5)
    for ($i = 0; $i -lt 20; $i++) {
        if ($i -lt $barLen) {
            $bar += "#"
        }
        else {
            $bar += "-"
        }
    }
    
    $report += "$label :  $($s.correct)/$($s.total) ($pct%)`n"
    $report += "  [$bar]`n"
    $report += "`n"
    
    if ($pct -ge 80) {
        Write-Host "$label :  $($s.correct)/$($s.total) ($pct%) [$bar]" -ForegroundColor Green
    }
    elseif ($pct -ge 50) {
        Write-Host "$label : $($s. correct)/$($s.total) ($pct%) [$bar]" -ForegroundColor Yellow
    }
    else {
        Write-Host "$label : $($s.correct)/$($s.total) ($pct%) [$bar]" -ForegroundColor Red
    }
}

# RAG farkını hesapla
$ragPct = 0
if ($scores["rag"].total -gt 0) {
    $ragPct = ($scores["rag"]. correct / $scores["rag"].total) * 100
}

$noRagAvg = 0
$noRagCount = 0
foreach ($mk in @("gpt-5-mini", "gemini-3-flash")) {
    if ($scores[$mk]. total -gt 0) {
        $noRagAvg += ($scores[$mk].correct / $scores[$mk].total) * 100
        $noRagCount++
    }
}
if ($noRagCount -gt 0) {
    $noRagAvg = $noRagAvg / $noRagCount
}

$improvement = $ragPct - $noRagAvg

$report += "-------------------------------------------------------------------------------`n"
$report += "`n"
$report += "RAG vs No-RAG Comparison:`n"
$report += "  RAG Score:       $([math]::Round($ragPct, 1))%`n"
$report += "  No-RAG Average: $([math]::Round($noRagAvg, 1))%`n"
$report += "  RAG IMPROVEMENT: +$([math]:: Round($improvement, 1))%`n"
$report += "`n"

# En başarısız skill'leri bul
$report += "-------------------------------------------------------------------------------`n"
$report += "SKILLS WHERE RAG HELPED MOST:`n"
$report += "-------------------------------------------------------------------------------`n"

for ($i = 0; $i -lt $detailedResults["rag"].Count; $i++) {
    $ragAcc = $detailedResults["rag"][$i].accuracy
    $noRagAcc1 = if ($detailedResults["gpt-5-mini"].Count -gt $i) { $detailedResults["gpt-5-mini"][$i].accuracy } else { 0 }
    $noRagAcc2 = if ($detailedResults["gemini-3-flash"].Count -gt $i) { $detailedResults["gemini-3-flash"][$i]. accuracy } else { 0 }
    $noRagAvgAcc = ($noRagAcc1 + $noRagAcc2) / 2
    $diff = $ragAcc - $noRagAvgAcc
    
    if ($diff -gt 20) {
        $skillName = $detailedResults["rag"][$i]. skill
        $report += "  + $skillName :  RAG $ragAcc% vs No-RAG $([math]::Round($noRagAvgAcc))% (+$([math]::Round($diff))%)`n"
    }
}

$report += "`n"
$report += "===============================================================================`n"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "             RAG IMPROVEMENT" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  RAG Score:       $([math]:: Round($ragPct, 1))%" -ForegroundColor Cyan
Write-Host "  No-RAG Average:   $([math]::Round($noRagAvg, 1))%" -ForegroundColor Yellow

if ($improvement -gt 0) {
    Write-Host ""
    Write-Host "  RAG IMPROVEMENT:  +$([math]::Round($improvement, 1))%" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "  RAG IMPROVEMENT:  $([math]::Round($improvement, 1))%" -ForegroundColor Red
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta

# Sonucu kaydet
$reportPath = "rag_comparison_report_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
$report | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "`nReport saved to:  $reportPath" -ForegroundColor Green