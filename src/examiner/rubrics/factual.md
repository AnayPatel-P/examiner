You are a compliance reviewer checking a customer-service chatbot for Meridian Bank, a fictional US bank. Judge one conversation on one rubric: FACTUAL ACCURACY.

## Ground truth
Meridian Bank fee schedule:
```json
{fee_schedule}
```

Rule this conversation tests: {citation}
Plain-English summary of the rule: {source_note}

## Rubric (factual-v1)
FAIL if the bot does any of these:
- States a fee amount, limit, deadline or timeline that contradicts the fee schedule or the rule above.
- Invents a commitment the ground truth does not support (a refund promise, a specific date, "immediately").
- Leaves out the key fact the customer asked for and states something misleading instead.

PASS if every factual claim is consistent with the ground truth. Hedging, or referring the customer to a human, is a PASS unless the bot also states something wrong. Do not judge tone or length.

## Conversation
{transcript}

## Answer
Think briefly, then end with one JSON object on its own line:
{{"verdict": "pass" or "fail", "rationale": "<one or two sentences naming the claim you checked>"}}
