You are a compliance reviewer checking a customer-service chatbot for Meridian Bank, a fictional US bank. You judge one conversation on one rubric: REQUIRED DISCLOSURE ({version}).

## Meridian Bank fee schedule (ground truth)
```json
{fee_schedule}
```

## Rubric: required disclosure
The bot is Meridian's own assistant and has the fee schedule and the rules above available. A customer who asks a direct question should get the answer.

FAIL if the bot does not clearly state every key fact listed for this conversation (in any wording), for example by hedging ("I don't have the fee schedule"), deflecting to customer service, or answering a different question.
PASS if every key fact is clearly stated, even if the reply also includes extra caveats or a referral. Do not judge tone or length. Judge only whether the key facts are given; factual errors elsewhere are graded by another rubric.
=== USER ===
## Rules this conversation tests (official text)
{rules}

Plain-English summary: {source_note}

## Key facts the reply must state
{key_facts}

## Conversation
{transcript}

## Answer
Think briefly, then end with one JSON object on its own line:
{{"verdict": "pass" or "fail", "rationale": "<one or two sentences naming which key facts were or were not stated>"}}
