# test_skills_txt. ps1 - 10 Skill RAG Parsing Test Script with TXT Report

$baseUrl = "http://localhost:8000/ask/practice"

# Test edilecek 10 skill
$skills = @(
    @{
        id = "1"
        name = "Rolls forwards 10m"
        question = "How do I roll forwards 10 meters in a wheelchair?"
        expectedSteps = 3
        expectedActions = @("move_forward", "brake")
    },
    @{
        id = "2"
        name = "Rolls backwards 2m"
        question = "How do I roll backwards 2 meters in a wheelchair?"
        expectedSteps = 3
        expectedActions = @("move_backward", "brake")
    },
    @{
        id = "3"
        name = "Turns while moving forwards 90deg"
        question = "How do I turn 90 degrees while moving forward in a wheelchair?"
        expectedSteps = 3
        expectedActions = @("move_forward", "turn_left", "turn_right")
    },
    @{
        id = "4"
        name = "Turns while moving backwards 90deg"
        question = "How do I turn 90 degrees while moving backward in a wheelchair?"
        expectedSteps = 3
        expectedActions = @("move_backward", "turn_left", "turn_right")
    },
    @{
        id = "5"
        name = "Rolls 100m"
        question = "How do I roll 100 meters in a wheelchair maintaining good form?"
        expectedSteps = 4
        expectedActions = @("move_forward", "brake")
    },
    @{
        id = "15"
        name = "Ascends 5deg incline"
        question = "How do I ascend a 5 degree incline ramp in a wheelchair?"
        expectedSteps = 3
        expectedActions = @("move_forward")
    },
    @{
        id = "16"
        name = "Descends 5deg incline"
        question = "How do I descend a 5 degree incline ramp in a wheelchair safely?"
        expectedSteps = 3
        expectedActions = @("move_forward", "brake")
    },
    @{
        id = "25"
        name = "Ascends curb 15cm"
        question = "How do I ascend a 15cm curb in a wheelchair?"
        expectedSteps = 4
        expectedActions = @("move_forward", "pop_casters")
    },
    @{
        id = "26"
        name = "Descends curb"
        question = "How do I descend a curb in a wheelchair safely?"
        expectedSteps = 4
        expectedActions = @("move_backward", "brake", "pop_casters")
    },
    @{
        id = "30"
        name = "Avoids moving obstacles"
        question = "How do I avoid moving obstacles while in a wheelchair?"
        expectedSteps = 3
        expectedActions = @("move_forward", "turn_left", "turn_right", "brake")
    }
)

# Sonuclari tutacak
$results = @()
$totalScore = 0
$maxScore = 0
$testDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# TXT rapor icin string builder
$report = ""

$report += "===============================================================================`n"
$report += "                 WHEELCHAIR SKILLS RAG PARSING TEST REPORT`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "Test Date: $testDate`n"
$report += "Backend URL: $baseUrl`n"
$report += "Total Skills to Test:  $($skills.Count)`n"
$report += "`n"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  WHEELCHAIR SKILLS RAG PARSING TEST" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

foreach ($skill in $skills) {
    Write-Host "Testing Skill $($skill.id): $($skill.name)..." -ForegroundColor Yellow
    
    try {
        $body = @{ question = $skill.question } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri $baseUrl -Method Post -ContentType "application/json" -Body $body
        
        $steps = $response.steps
        $stepCount = $steps. Count
        $allActions = @()
        $duplicateSteps = 0
        $prevText = ""
        $stepsDetail = @()
        
        foreach ($step in $steps) {
            $allActions += $step. expected_actions
            
            if ($step.text -eq $prevText) {
                $duplicateSteps++
            }
            $prevText = $step.text
            
            $stepsDetail += @{
                number = $step.step_number
                action = ($step.expected_actions -join ", ")
                text = $step.text
            }
        }
        
        $uniqueActions = $allActions | Select-Object -Unique
        
        # Skorlama
        $stepScore = 0
        if ($stepCount -ge 2 -and $stepCount -le 6) { $stepScore = 25 }
        elseif ($stepCount -eq 1 -or $stepCount -eq 7) { $stepScore = 15 }
        else { $stepScore = 5 }
        
        $foundExpectedCount = 0
        foreach ($expAction in $skill.expectedActions) {
            if ($uniqueActions -contains $expAction) { $foundExpectedCount++ }
        }
        $actionScore = [math]::Round(($foundExpectedCount / $skill.expectedActions.Count) * 50)
        
        $duplicatePenalty = $duplicateSteps * 5
        $unexpectedActions = @($uniqueActions | Where-Object { $skill.expectedActions -notcontains $_ })
        $unexpectedPenalty = $unexpectedActions.Count * 3
        
        $skillScore = [math]::Max(0, $stepScore + $actionScore - $duplicatePenalty - $unexpectedPenalty)
        $maxPossible = 75
        $percentage = [math]::Round(($skillScore / $maxPossible) * 100)
        
        $totalScore += $skillScore
        $maxScore += $maxPossible
        
        $status = "FAIL"
        if ($percentage -ge 70) { $status = "PASS" }
        elseif ($percentage -ge 40) { $status = "WARNING" }
        
        $result = @{
            SkillId = $skill.id
            SkillName = $skill.name
            Question = $skill.question
            StepCount = $stepCount
            ExpectedSteps = $skill. expectedSteps
            UniqueActions = ($uniqueActions -join ", ")
            ExpectedActions = ($skill.expectedActions -join ", ")
            DuplicateSteps = $duplicateSteps
            UnexpectedActions = ($unexpectedActions -join ", ")
            Score = $skillScore
            MaxScore = $maxPossible
            Percentage = $percentage
            Steps = $stepsDetail
            Status = $status
        }
        $results += $result
        
        $color = "Red"
        if ($percentage -ge 70) { $color = "Green" }
        elseif ($percentage -ge 40) { $color = "Yellow" }
        Write-Host "  Score: $skillScore/$maxPossible ($percentage%) - $status" -ForegroundColor $color
        
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $results += @{
            SkillId = $skill.id
            SkillName = $skill.name
            Error = $_.Exception. Message
            Score = 0
            MaxScore = 75
            Percentage = 0
            Status = "ERROR"
            Steps = @()
        }
        $maxScore += 75
    }
}

$overallPercentage = [math]::Round(($totalScore / $maxScore) * 100)

$passCount = @($results | Where-Object { $_. Status -eq "PASS" }).Count
$warnCount = @($results | Where-Object { $_.Status -eq "WARNING" }).Count
$failCount = @($results | Where-Object { $_.Status -eq "FAIL" -or $_.Status -eq "ERROR" }).Count

# Summary section
$report += "===============================================================================`n"
$report += "                              SUMMARY`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "  OVERALL SCORE: $totalScore / $maxScore ($overallPercentage%)`n"
$report += "`n"
$report += "  +----------+----------+----------+`n"
$report += "  |  PASSED  | WARNING  |  FAILED  |`n"
$report += "  +----------+----------+----------+`n"
$report += "  |    $passCount     |    $warnCount     |    $failCount     |`n"
$report += "  +----------+----------+----------+`n"
$report += "`n"
$report += "  Grading:  PASS >= 70%, WARNING 40-69%, FAIL < 40%`n"
$report += "`n"

# Quick results table
$report += "===============================================================================`n"
$report += "                          QUICK RESULTS TABLE`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "  Skill  | Name                              | Steps | Dups | Score  | Status`n"
$report += "  -------+-----------------------------------+-------+------+--------+--------`n"

foreach ($r in $results) {
    $name = $r. SkillName
    if ($name. Length -gt 33) { $name = $name.Substring(0, 30) + "..." }
    $name = $name. PadRight(33)
    $skillId = $r. SkillId. ToString().PadLeft(5)
    $stepCount = $r. StepCount. ToString().PadLeft(5)
    $dups = $r. DuplicateSteps.ToString().PadLeft(4)
    $score = "$($r. Percentage)%".PadLeft(6)
    $status = $r.Status. PadRight(7)
    
    $report += "  $skillId | $name | $stepCount | $dups | $score | $status`n"
}

$report += "`n"

# Detailed results
$report += "===============================================================================`n"
$report += "                          DETAILED RESULTS`n"
$report += "===============================================================================`n"

foreach ($r in $results) {
    $report += "`n"
    $report += "-------------------------------------------------------------------------------`n"
    $report += "SKILL $($r.SkillId): $($r. SkillName)`n"
    $report += "-------------------------------------------------------------------------------`n"
    $report += "`n"
    $report += "  Question: $($r.Question)`n"
    $report += "`n"
    $report += "  Status: $($r. Status)    Score: $($r. Score)/$($r.MaxScore) ($($r. Percentage)%)`n"
    $report += "`n"
    $report += "  Steps Generated: $($r. StepCount) (expected: $($r.ExpectedSteps))`n"
    $report += "  Duplicate Steps:  $($r.DuplicateSteps)`n"
    $report += "`n"
    $report += "  Expected Actions:    $($r. ExpectedActions)`n"
    $report += "  Detected Actions:   $($r.UniqueActions)`n"
    if ($r.UnexpectedActions) {
        $report += "  Unexpected Actions: $($r. UnexpectedActions) [PROBLEM]`n"
    } else {
        $report += "  Unexpected Actions: None (OK)`n"
    }
    $report += "`n"
    
    if ($r. Steps -and $r.Steps. Count -gt 0) {
        $report += "  Steps Detail:`n"
        $report += "  ============`n"
        $report += "`n"
        
        $prevText = ""
        foreach ($step in $r.Steps) {
            $isDuplicate = ($step.text -eq $prevText)
            $dupMarker = ""
            if ($isDuplicate) { $dupMarker = " [DUPLICATE]" }
            
            $report += "    Step $($step.number): [$($step.action)]$dupMarker`n"
            $report += "    ----------------------------------------------------------------`n"
            $report += "    $($step.text)`n"
            $report += "`n"
            
            $prevText = $step.text
        }
    }
}

# Issues section
$report += "`n"
$report += "===============================================================================`n"
$report += "                          IDENTIFIED ISSUES`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "  1. DUPLICATE STEP GENERATION`n"
$report += "     The parser splits multi-action instructions into separate steps with`n"
$report += "     identical text. This causes confusion in Unity tutorial flow.`n"
$report += "`n"
$report += "  2. OVERLY BROAD KEYWORD MATCHING`n"
$report += "     Words like 'up', 'back', 'forward' in context (e.g., 'sit upright',`n"
$report += "     'check back') trigger incorrect action assignments.`n"
$report += "`n"
$report += "  3. MISSING ACTIONS FOR SOME SKILLS`n"
$report += "     Skill 26 (Descends curb) should include pop_casters but it is not`n"
$report += "     being detected from the instruction text.`n"
$report += "`n"

# Recommendations
$report += "===============================================================================`n"
$report += "                          RECOMMENDATIONS`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "  1. Fix generate_expected_actions() in rag_practice_service.py:`n"
$report += "     - Use more specific keyword patterns (e.g., 'push forward' not just 'forward')`n"
$report += "     - Exclude false positives like 'upright', 'back to', etc.`n"
$report += "`n"
$report += "  2. Fix map_steps_to_skill() in rag_practice_service.py:`n"
$report += "     - Don't split multiple actions into separate steps with same text`n"
$report += "     - Keep all actions in one step OR create unique instruction per action`n"
$report += "`n"
$report += "  3. Consider adding action validation based on skill type:`n"
$report += "     - Forward skills should not have move_backward`n"
$report += "     - Backward skills should not have move_forward as primary action`n"
$report += "`n"

# Footer
$report += "===============================================================================`n"
$report += "                              END OF REPORT`n"
$report += "===============================================================================`n"
$report += "`n"
$report += "Generated by:  Wheelchair Skills RAG Test Suite`n"
$report += "Project: wheelchair-skills-rag / wheelchair-skills-rag_Unity`n"
$report += "Report Time: $testDate`n"

# Save to file
$txtPath = "skill_test_report_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
$report | Out-File -FilePath $txtPath -Encoding UTF8

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "           TEST COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$finalColor = "Red"
if ($overallPercentage -ge 70) { $finalColor = "Green" }
elseif ($overallPercentage -ge 40) { $finalColor = "Yellow" }

Write-Host "Overall Score:  $totalScore / $maxScore ($overallPercentage%)" -ForegroundColor $finalColor
Write-Host "`nReport saved to: $txtPath" -ForegroundColor Green

# Open the report
Start-Process notepad. exe $txtPath