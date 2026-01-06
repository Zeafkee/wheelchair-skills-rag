# Global Error Analytics Endpoints

This document describes the new global error analytics endpoints added to the Wheelchair Skills RAG API.

## Table of Contents
- [Overview](#overview)
- [New Endpoints](#new-endpoints)
- [Enhanced Endpoints](#enhanced-endpoints)
- [Error Types](#error-types)
- [Response Examples](#response-examples)

## Overview

The global error analytics feature provides insights into user performance across the entire system. It analyzes all user attempts to identify:
- Skills with highest failure rates
- Most problematic steps across all skills
- Common action confusions (what users press instead of expected)
- Individual user performance compared to global averages

## New Endpoints

### GET `/analytics/global-errors`

Returns global error statistics across all users.

**Parameters:** None

**Response:**
```json
{
  "total_attempts": 150,
  "total_users": 12,
  "skill_summary": [
    {
      "skill_id": "a02_2m_backward",
      "total_attempts": 25,
      "failed_attempts": 15,
      "failure_rate": 0.6,
      "total_errors": 18,
      "most_problematic_step": "2"
    }
  ],
  "problematic_steps": [
    {
      "skill_id": "a01_10m_forward",
      "step_number": 2,
      "error_count": 12,
      "most_common_error": "wrong_direction"
    }
  ],
  "action_confusion": [
    {
      "expected": "move_forward",
      "actual": "turn_right",
      "count": 8,
      "description": "Users press turn_right instead of move_forward"
    }
  ],
  "generated_at": "2026-01-06T21:30:00Z"
}
```

**Fields:**
- `total_attempts`: Total number of skill attempts across all users
- `total_users`: Number of unique users in the system
- `skill_summary`: Array of skills sorted by failure rate (highest first)
  - `failure_rate`: Percentage of failed attempts (0.0 to 1.0)
  - `most_problematic_step`: Step number with most errors
- `problematic_steps`: Top 20 steps with highest error counts across all skills
  - Sorted by `error_count` (highest first)
- `action_confusion`: Top 20 most common action confusions
  - Shows what action users tend to do instead of expected action
  - Sorted by `count` (highest first)

### GET `/analytics/skill/{skill_id}/errors`

Returns detailed error analysis for a specific skill.

**Parameters:**
- `skill_id` (path): The skill identifier (e.g., "a01_10m_forward")

**Response:**
```json
{
  "skill_id": "a01_10m_forward",
  "total_attempts": 50,
  "step_error_rates": [
    {
      "step_number": 2,
      "error_rate": 0.4,
      "total_errors": 20,
      "common_error_types": [
        {
          "type": "wrong_direction",
          "count": 12
        }
      ],
      "common_wrong_actions": [
        {
          "expected": "move_forward",
          "actual": "move_backward",
          "count": 12
        }
      ]
    }
  ],
  "most_difficult_step": {
    "step_number": 2,
    "error_rate": 0.4,
    "total_errors": 20,
    "common_error_types": [...],
    "common_wrong_actions": [...]
  },
  "generated_at": "2026-01-06T21:30:00Z"
}
```

**Fields:**
- `step_error_rates`: Array of steps sorted by error rate (highest first)
  - `error_rate`: Percentage of attempts with errors on this step
  - `common_error_types`: Top 3 error types for this step
  - `common_wrong_actions`: Top 3 wrong actions for this step
- `most_difficult_step`: The step with highest error rate

**Error Response (404):**
```json
{
  "detail": "Bu skill için veri bulunamadı"
}
```

### DELETE `/user/{user_id}/clear-progress`

Clears all progress data for a specific user.

**Parameters:**
- `user_id` (path): The user identifier

**Response (200):**
```json
{
  "success": true,
  "message": "Kullanıcı user_001 ilerleme verileri silindi"
}
```

**Error Response (404):**
```json
{
  "detail": "Kullanıcı bulunamadı"
}
```

**Warning:** This operation:
- Resets all skill_progress to empty
- Clears all sessions
- Removes all attempts for this user
- Cannot be undone

## Enhanced Endpoints

### POST `/user/{user_id}/generate-plan`

The training plan endpoint has been enhanced with global insights and comparisons.

**New Fields Added:**

```json
{
  "user_id": "sefa001",
  "current_phase": "Foundation",
  "generated_at": "2026-01-06T21:30:00Z",
  "recommended_skills": [...],
  "focus_skills": [...],
  "session_goals": [...],
  "notes": [...],
  
  "global_insights": {
    "most_failed_skills": ["a02_2m_backward", "a04_turn_backward"],
    "common_mistakes": [
      {
        "expected": "move_forward",
        "actual": "turn_right",
        "count": 8,
        "description": "Users press turn_right instead of move_forward"
      }
    ],
    "problematic_steps": [
      {
        "skill_id": "a01_10m_forward",
        "step_number": 2,
        "error_count": 12,
        "most_common_error": "wrong_direction"
      }
    ]
  },
  
  "your_common_errors": [
    {
      "skill_id": "a01_10m_forward",
      "step_number": 2,
      "error_type": "wrong_input",
      "expected_action": "move_forward",
      "actual_action": "turn_right",
      "count": 3
    }
  ],
  
  "skill_comparisons": [
    {
      "skill_id": "a01_10m_forward",
      "your_success_rate": 0.6,
      "global_success_rate": 0.45,
      "comparison": "above_average"
    }
  ]
}
```

**Field Descriptions:**

- `global_insights`: Insights from all users' data
  - `most_failed_skills`: Top 3 skills with highest failure rates globally
  - `common_mistakes`: Top 5 action confusions globally
  - `problematic_steps`: Top 5 most difficult steps globally

- `your_common_errors`: User's top 10 most frequent errors
  - Sorted by `count` (highest first)
  - Includes skill, step, error type, and actions involved

- `skill_comparisons`: Comparison of user vs global performance
  - Only includes skills the user has attempted
  - `comparison` values:
    - `"above_average"`: User success rate > global + 5%
    - `"average"`: Within ±5% of global rate
    - `"below_average"`: User success rate < global - 5%

## Error Types

The following error types are now supported:

| Error Type | Description | Severity |
|------------|-------------|----------|
| `wrong_input` | Genel yanlış tuş | medium |
| `wrong_direction` | İleri yerine geri veya tam tersi | medium |
| `wrong_turn_direction` | Sola yerine sağa veya tam tersi | medium |
| `stopped_instead_of_moving` | Durdu ama hareket etmeliydi | medium |
| `moved_instead_of_stopping` | Hareket etti ama durmalıydı | medium |
| `missed_pop_casters` | Pop casters yapılmadı | high |
| `timeout` | Süre doldu | high |
| `wrong_sequence` | Doğru tuşlar ama yanlış sırada | medium |
| `timing_error` | Doğru input ama yanlış zamanlama | low |
| `missing_input` | Gerekli input atlandı | high |
| `extra_input` | Gereksiz input yapıldı | low |
| `incomplete_action` | Hareket tamamlanmadı | medium |
| `balance_lost` | Denge kaybedildi | high |
| `collision` | Çarpışma oldu | high |
| `safety_violation` | Güvenlik ihlali | critical |

## Usage Notes

1. **Performance**: Global analytics queries analyze all attempts in the database. For large datasets, responses may take longer.

2. **Data Privacy**: All analytics are aggregated. No individual user data is exposed in global endpoints.

3. **Thresholds**: 
   - Maximum 20 items returned for `problematic_steps` and `action_confusion`
   - Success rate comparison uses ±5% threshold for "average" classification
   - These can be configured via constants in `user_progress.py`

4. **Empty Data**: When no data is available:
   - Global stats return zeros and empty arrays
   - Skill-specific stats return 404
   - Training plan still generates with empty insight arrays

5. **Timestamps**: All timestamps are in ISO 8601 format with UTC timezone (ending in 'Z')
