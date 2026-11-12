# PRD: Failure Experience Redesign (PayFlow)

Status: draft for experiment. All numbers come from synthetic data.

## Problem
Most unrecovered failed journeys were never retried (about 81 percent). Failures show a generic message, with no next step and no status information. Customers abandon, and for timeouts the status is unknown, so a blind retry risks a duplicate debit.

## Goal
Raise journey recovery without raising duplicate payments or reducing customer trust.

## Users
Customers who see a failed or pending payment in the PayFlow app.

## Requirements
1. Specific message by failure type (decision-table group: retry, customer action, wait for status, do not retry).
2. One clear next action (for example "Re-enter your PIN", "Add funds", "Try a different amount").
3. Status visibility: for timeouts and pending payments show "We are checking your payment" and prevent a new attempt until the status is known.
4. Safe retry guidance only where the decision table says Eligible for retry evaluation.
5. For limit errors: explain the limit and offer an alternative option where one exists.
6. No automatic retries in this release (messaging only).

## User stories and acceptance criteria
- As a customer whose PIN failed, I see "Incorrect PIN, try again" and a retry button. Accept: shown for CUS_01 and CUS_02 only.
- As a customer whose payment timed out, I see that the status is being checked and cannot start a duplicate payment. Accept: new attempt blocked until status resolved or 30 minutes pass.
- As a customer who hit a limit, I see the limit and one alternative. Accept: shown for LIM codes only.
- As an operations analyst, I can see which message each customer saw. Accept: message variant logged with each failed attempt.

## Out of scope
Automatic retries, new payment rails, changes to bank integrations.

## Risks
- Blocking new attempts during status checks may reduce recovery for payments that did fail.
- Messaging may increase duplicate payments if customers misread it (guardrail).
- Effect may differ by failure type; the first test reads the pooled effect.

## Success metrics
Primary: journey recovery rate. Guardrail: duplicate-payment rate. Secondary: abandonment, time to successful completion, retry rate. See docs/experiment_plan.md.
