# Bind evaluation to the model log

## Decision

After every submission is frozen, record the complete model log's
SHA-256 or its absence. Store this identity before held-out access.
Check it on resume, before replay, and after measurement. Include it
in the final report. Replay uses the original log and checks that its
own pipeline run has no new model log.

Validate cached completed records against their request, provider,
binary, model, Standard service tier, token counts, and computed charge.
Reject inconsistent records with a provider error.

## Evidence

An independent synthetic review changed a cached completion's model
name. The previous implementation accepted it. New regression tests
reject altered completion metadata and changed evaluation log bytes.

## Limits

The hash identifies the recorded bytes. It does not independently
authenticate the provider's reported usage. Publish the identity with
each final evaluation report so that replay can check the same record.
