# Phase Log


## Phase 0: Setup (done)
Scaffold, virtual environment, PostgreSQL connection check, GitHub connected.

## Phase 1: Business foundation (done)
Transaction lifecycle, failure taxonomy (16 codes, 5 retry classes), final metric dictionary v1.0, phase Q&A doc.
Key decisions: 30-minute journey window (to be tested), PENDING excluded from rates, CUS_03 excluded, matching denominators for recovery and abandonment.

## Phase 2 design (done)
Data model, 13 planted patterns (ground truth) and generator plan approved.
Decisions: fictional names, 1 Apr to 30 Sep 2026, about 300k attempts with about 20k retries, ground truth committed before Phase 3, no journey_id in raw data.
