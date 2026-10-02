# Ola Data Agent — RepoBrain retrieval baseline

Indexed commit: [`e923bcb`](https://github.com/b-amit11/ola-data-agent/tree/e923bcb09280b7f1b3962b890931b86b413444ec).

16 Python files; 195 structural chunks; no parse warnings. Source was inspected, not executed. No dependencies from the analyzed repository were installed.

**Mean exact-symbol recall@5: 53.3%.** All labeled symbols found in 12/25 questions; no labeled symbols found in 10/25.

This is a source-authored development benchmark, not held-out data. Gold answers and exact symbol targets were written from inspected source before querying the retriever. No retrieval tuning was performed. The score measures retrieval only; no live model answer quality was evaluated.

Exact symbol matching penalizes retrieval of an enclosing class/function even when it contains the relevant child code. Parent/child chunks overlap, and tests compete with implementation chunks. Module statements share the <module> label, but none are gold targets in this suite. These caveats matter when interpreting misses.

## Per-question results

| ID | Question | Recall@5 |
|---|---|---:|
| ola-01 | How does a question get routed to SQL, ETL, or clarification? | 100% |
| ola-02 | What happens when offline mode receives a question outside its examples? | 100% |
| ola-03 | Where are multiple SQL statements and database writes rejected? | 100% |
| ola-04 | Can an approved model review override the SQL safety checks? | 0% |
| ola-05 | How does SQLite remain read-only if the SQL validator is bypassed? | 100% |
| ola-06 | How are PostgreSQL queries prevented from writing or running indefinitely? | 0% |
| ola-07 | How are system schemas, unknown tables, and dangerous functions blocked? | 100% |
| ola-08 | Are recursive SQL queries allowed? | 100% |
| ola-09 | How does a query detect truncated results and limit returned rows? | 100% |
| ola-10 | When can a SQL execution failure trigger another generation attempt? | 50% |
| ola-11 | What happens if semantic review rejects the SQL twice? | 0% |
| ola-12 | What stops an ETL tool loop that never finishes? | 100% |
| ola-13 | Can the model execute arbitrary Python or choose arbitrary export paths? | 0% |
| ola-14 | Where do ETL exports go and how are filenames generated? | 0% |
| ola-15 | What protects downloaded CSV cells from formula injection? | 100% |
| ola-16 | Does an invalid second filter leave a partially modified dataframe? | 0% |
| ola-17 | What differs between offline and live Pokemon extraction? | 0% |
| ola-18 | What information does the ETL planner receive about the current dataframe? | 50% |
| ola-19 | Where are the live model timeout, retries, and model selection configured? | 100% |
| ola-20 | How are structured model responses validated and model calls counted? | 100% |
| ola-21 | How are SQL results checked independently of the generated query? | 33% |
| ola-22 | Why does live evaluation skip the Pokemon extraction case? | 100% |
| ola-23 | How is the synthetic ride dataset made reproducible? | 0% |
| ola-24 | How is ETL state kept separate between workflow runs? | 0% |
| ola-25 | Where are blank or excessively long workflow questions rejected? | 0% |

## Next experiment

Inspect the zero-hit and partial-hit questions in the JSON report. Test hierarchy-aware deduplication and retrieval of related definitions against this frozen baseline; then compare hybrid retrieval on a separate paraphrase set. Do not tune only to these 25 questions.

## Reproduce

From the RepoBrain project directory, with the environment active and this commit indexed:

```sh
repobrain eval benchmarks/ola-data-agent.json --repo 2
```

Repository ID 2 refers to the current local database. For another installation, use the ID returned by indexing. The benchmark JSON includes reference answers and commit-pinned evidence links; the baseline JSON records the retrieved symbols and missing targets.
