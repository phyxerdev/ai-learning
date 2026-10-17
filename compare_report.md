# Engine comparison - 2026-10-17 16:08

Document: `ads_handbook.txt`, 7 questions (2 should be refused).

## Summary

| Settings | Answer model | Embeddings | Threshold | Passed | Avg seconds |
| --- | --- | --- | --- | --- | --- |
| .env.gemini | gemini-3.8-flash | gemini-embedding-2 | 0.55 | 1/7 | 2.9 |
| .env.ollama | qwen3:8b | nomic-embed-text | 0.55 | 7/7 | 4.2 |

## .env.gemini (gemini-3.8-flash)

| Question | Verdict | Score | Sec | Answer |
| --- | --- | --- | --- | --- |
| What is the target cost per conversion? | ERROR | None | 2.4 | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more inf... |
| How much can I increase the daily budget when scaling? | ERROR | None | 2.7 | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more inf... |
| What should I do if the landing page domain is blocked? | ERROR | None | 2.5 | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more inf... |
| How long can a video ad be? | PASS | 0.681 | 4.8 | Videos must be under 15 seconds [chunk 2]. |
| When should I pause an ad because people don't click? | ERROR | None | 2.7 | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more inf... |
| What is our refund policy? | ERROR | None | 2.4 | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more inf... |
| What is the target cost per click? | ERROR | None | 2.6 | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more inf... |

## .env.ollama (qwen3:8b)

| Question | Verdict | Score | Sec | Answer |
| --- | --- | --- | --- | --- |
| What is the target cost per conversion? | PASS | 0.641 | 3.8 | The target cost per conversion is $8 [chunk 1]. |
| How much can I increase the daily budget when scaling? | PASS | 0.677 | 3.6 | When scaling, you can increase the daily budget by no more than 20% per day [chunk 0]. |
| What should I do if the landing page domain is blocked? | PASS | 0.6 | 4.7 | If the landing page domain is blocked by Nawala, switch the ads to the backup domain within 1 hour and inform the tech team [chunk 5]. |
| How long can a video ad be? | PASS | 0.651 | 3.7 | The video ad must be under 15 seconds [chunk 2]. |
| When should I pause an ad because people don't click? | PASS | 0.686 | 8.6 | Pause an ad if its click-through rate stays below 0.8% after 5,000 impressions, as this indicates the creative isn't attracting attention [chunk 1]. This rule i... |
| What is our refund policy? | PASS | 0.455 | 0.0 | That isn't covered in the document. |
| What is the target cost per click? | PASS | 0.647 | 4.7 | That isn't covered in the document. |

Verdicts: PASS = correct; CHECK = answered but a key fact is missing (read it); FAIL (refused) = said not covered but it is; FAIL (invented) = should have said not covered.
