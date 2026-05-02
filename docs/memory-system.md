# Student Memory System

The memory system should help OpenTeacher teach better over time while respecting privacy and the vulnerability of minors.

## Memory Goals

Memory should answer:

- What is this student learning?
- What does this student often misunderstand?
- How should the teacher explain things to this student?
- What learning behaviors should be reinforced or corrected?
- What progress should be remembered and reflected back?

Memory should not become a general personal diary.

## Memory Types

### 1. Profile Memory

Stable, minimal student context.

Fields:

- student_id
- preferred_name
- school_stage: primary | junior | senior
- grade
- region_level: optional, coarse only
- active_subjects
- textbook_version: optional

### 2. Academic Memory

Learning state by subject and knowledge point.

Fields:

- subject
- grade
- knowledge_point_id
- mastery_level: 0-5
- evidence
- last_practiced_at
- common_errors
- recommended_next_steps

### 3. Teaching Preference Memory

How this student learns better.

Fields:

- explanation_preference: concrete_examples | step_by_step | visual | exam_strategy
- response_length_preference
- strictness_tolerance: low | medium | high
- needs_more_checkpoints
- avoids_direct_answer: true

### 4. Learning Behavior Memory

Patterns observed in learning behavior.

Fields:

- often_skips_steps
- often_requests_direct_answer
- checks_work_carefully
- persists_after_error
- recent_attention_pattern

### 5. Encouragement Memory

Concrete progress worth remembering.

Fields:

- progress_event
- subject
- evidence
- date
- reusable_encouragement

## Privacy Rules

Do not store:

- Exact home address
- Family income
- Parent phone numbers
- Health conditions unless necessary and explicitly provided for accessibility
- Political or religious beliefs
- Sensitive family situations
- Psychological labels or diagnoses

## Memory Update Policy

Memory should be updated only when:

- The student shows a repeated academic pattern
- The student completes a meaningful learning step
- The student makes the same mistake multiple times
- The student explicitly sets a learning preference
- A teacher or volunteer confirms an observation

Memory should not be updated from one weak signal.

