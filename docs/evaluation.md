# Evaluation

Status: **designed**. Implementation is Phase 11. The goal is to treat RAG quality as an engineering metric, not a vibe.

## Dataset record

```json
{
  "question": "How many annual leave days do employees currently receive?",
  "expected_answer": "22 days",
  "relevant_document_ids": ["..."]
}
```

The Acme Systems demo corpus (Phase 12/59) includes conflicting handbook versions so evaluation can prove **current-version retrieval**.

## Retrieval metrics

- Recall@K
- Precision@K
- MRR
- nDCG

## Answer metrics

- Groundedness / faithfulness
- Answer relevance
- Citation correctness
- Citation completeness

## Experiments

Configurations are first-class (chunk size, retrieval mode, top_k, reranker on/off). A comparison run should produce a table, for example:

```text
               dense     hybrid+rerank
Recall@10      0.73      0.91
MRR            0.61      0.80
Groundedness   0.84      0.92
Latency        420ms     680ms
```

API sketch: `POST /api/v1/evaluation/run`, `GET /api/v1/evaluation/runs`.
