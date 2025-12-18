---
name: test-retrieval
description: Test hybrid retrieval (pgvector + Elasticsearch) and RAG answer generation
---

You are helping test the hybrid retrieval and RAG pipeline for the BH Accounting Knowledge Base. This validates that vector search, BM25, reranking, and answer generation work correctly for BiH legal/accounting queries.

## Prerequisites

- Docker services running: `docker compose ps` (postgres, elasticsearch, api)
- Elasticsearch healthy: `curl http://localhost:9200/_cluster/health`
- PostgreSQL/pgvector ready: `psql -h localhost -U postgres -d bhkb -c "SELECT COUNT(*) FROM chunk;"`
- Sample documents ingested and embedded

## Test Queries

Run these representative BiH accounting queries to validate retrieval quality:

### 1. VAT Rate Query (Jurisdiction-Specific)
**Query**: "Koja je stopa PDV-a u Federaciji BiH?"
**Expected**: Should return FBiH-specific VAT rate with citation to official source, effective dates

### 2. CIT Threshold Query (Entity Comparison)
**Query**: "Koji je prag za porez na dobit u RS i FBiH?"
**Expected**: Should return thresholds for both entities with clear jurisdiction labels and citations

### 3. Effective Date Query (Temporal)
**Query**: "Kada stupa na snagu novi pravilnik o PDV-u?"
**Expected**: Should extract effective date phrases and return current/future regulations with dates

### 4. Article Lookup Query (Precision)
**Query**: "Šta kaže Član 23. Zakona o PDV-u?"
**Expected**: Should return exact article text with article number, source law, and jurisdiction

### 5. Cyrillic Query (Script Handling)
**Query**: "Порез на додату вриједност у Републици Српској"
**Expected**: Should handle Cyrillic search, return RS-specific results, preserve original script in citations

## Validation Steps

1. **Run Query via API**
   ```bash
   curl -X POST http://localhost:8000/api/v1/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Koja je stopa PDV-a u FBiH?", "jurisdiction": "FBIH", "topic": "VAT"}'
   ```

2. **Check Response Quality**
   - ✅ Answer is in Bosnian/Croatian/Serbian (BCS)
   - ✅ Citations include: source URL, article number, jurisdiction, effective dates
   - ✅ No hallucination (all facts have citations)
   - ✅ Jurisdiction filter applied correctly
   - ✅ Temporal filter applied (only current/valid clauses)

3. **Inspect Retrieval Pipeline**
   - Check logs for hybrid search (dense + sparse)
   - Verify RRF/MMR fusion happened
   - Confirm reranking applied (top 50 → top 12)
   - Validate embedding model used (bge-m3 or Gemini Flash Lite)

4. **Validate Metadata**
   - Check retrieved chunks have: `jurisdiction_id`, `topic_id`, `effective_from`, `effective_to`
   - Verify temporal filter: `(effective_to IS NULL OR effective_to >= CURRENT_DATE)`
   - Confirm consolidated laws preferred over base laws

## Performance Checks

- Latency < 3s for simple queries (without ReAct/Reflection)
- Top-12 retrieval includes at least 3 unique sources
- Citation formatting consistent: `[Source: <URL>, Član X, FBiH, Važi od: YYYY-MM-DD]`

## Troubleshooting

If retrieval fails:
- Check Elasticsearch index exists: `curl http://localhost:9200/_cat/indices?v`
- Check pgvector embeddings: `SELECT COUNT(*) FROM embedding;`
- Check Temporal workflows ran: `docker compose logs worker`
- Validate chunk text is clean (no HTML artifacts, OCR noise)

If citations missing:
- Verify `chunk` table has `page_number`, `heading_path`
- Check `document` table has `url`, `jurisdiction_id`, `effective_from`
- Review answer generation prompt (should enforce citation blocks)

## Report Results

Summarize:
- Which queries worked / failed
- Retrieval quality (relevance, jurisdiction accuracy, temporal correctness)
- Citation integrity (completeness, formatting)
- Performance metrics (latency, source diversity)
- Recommendations for tuning (chunk size, rerank threshold, MMR diversity)
