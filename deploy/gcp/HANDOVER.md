# OpenSearch → Google Cloud: status & handover

*Written 6 Sep 2026. Shareable — contains no passwords or keys.*

---

## TL;DR

We are moving OpenSearch off the Oracle VM onto Google Cloud. **All 465,398 chunks
are already copied across and verified.** Production is still served by Oracle and
is untouched — the switch has not happened yet.

Nothing is at risk. Rolling back is a one-line change until we deliberately cut over.

---

## Why we moved

Oracle cut its "Always Free" allowance from 4 CPU / 24 GB RAM to **2 CPU / 12 GB on
15 June 2026**, and started shutting down instances above that limit from 18 August.

Our VM was already at that new ceiling, so there was no free way to get more memory.
That mattered because the box was memory-starved: the index is 11.6 GB but only
~3 GB could be held in RAM cache, which is what caused the `/api/search` timeouts and
502 errors a few weeks back (fixed short-term in commit `5a5cce1`).

The new machine has **16 GB**, enough to hold the whole index in memory.

---

## What now exists on Google Cloud

| | |
|---|---|
| Project | `project-cab4f89d-cfd5-4949-802` |
| VM | `law-opensearch`, `e2-highmem-2` (2 CPU, 16 GB RAM, 100 GB disk) |
| Region | `us-west1` (Oregon) — same place as our Render backend |
| Static IP | `34.187.155.254` |
| OpenSearch | 2.19.5 — identical version to Oracle |
| Index | `case_chunks_v2` |
| Cost | ~$80/month (~₹7,600) |
| Free credit | ₹28,664, **expires 6 December 2026** |

Credentials live only on the VM (`~/law-opensearch/.env`, locked down) and in
Render's environment variables. They are never in git and are not in this document.

---

## Current status

| Step | Status |
|---|---|
| GCP project, VM, firewall | Done |
| OpenSearch running | Done |
| **Copy 465,398 chunks from Oracle** | **Done — exact match, zero failures** |
| Compacting the index (see below) | **Done — 23 pieces → 1, and 11.6 GB → 4.4 GB** |
| Search quality check vs Oracle | Next |
| Switch production over | Not started |
| Shut down Oracle | Not started |

The copy took 86 minutes and finished with the document count matching Oracle
exactly (465,398 on both sides).

**What "compacting" means:** the copy wrote the data as 23 separate chunks of index.
For vector search that is slow, because each chunk holds its own separate search
graph and every query has to walk all 23 and combine the results. Merging them into
one is a one-time job that makes every future search faster. Oracle has this problem
too — 35 pieces there — and it is part of why search is slow today. This is now done:
**23 pieces → 1**, and as a side effect the index shrank from 15 GB mid-merge to
**4.4 GB**.

---

## One change we made to the index

We stopped storing a **duplicate copy** of each chunk's embedding.

OpenSearch was keeping every 1024-number vector twice: once in the search structure
(needed), and once as raw text so it could hand it back in results (never used — our
API has never requested that field).

Result: **25.5 KB per document → 9.5 KB**, i.e. **11.6 GB → 4.4 GB, a 63% cut**.
Search behaviour is completely unchanged. The whole index now fits in the machine's
memory with room to roughly 2.5x the corpus before we need a bigger box.

### ⚠️ Important for the ingestion pipeline

**Adding new cases works exactly as before — no changes needed.** `stage_05_index.py`
writes whole documents, which is the safe pattern.

**But two operations are now dangerous on this index:**

1. **Never use `update_by_query` or partial `_update`.** These read a document, patch
   it, and write it back — and since the embedding is no longer stored, every document
   they touch would come back *without its vector*. No error, no warning, search
   quality silently degrades. Something like "backfill `case_type` across all cases"
   would do real damage.
2. **Never use `_reindex` from this index to a new one** — same reason, you would get
   documents with no vectors. If the mapping ever needs to change, rebuild from the
   pipeline output instead.

**Please keep `output/03_enriched/` and `output/04_embedded/` safe and backed up.**
Those are now the only way to regenerate vectors without paying for embeddings again.
We should get them into cloud storage rather than leaving them on one laptop.

---

## What changes for you

**Nothing right now.** Ingestion keeps pointing at Oracle until we switch over.

**After the switch,** `stage_05_index.py` needs two small changes to talk to the new
cluster — it currently connects with no username/password:

```python
# stage_05_index.py, around line 293
OpenSearch(
    hosts=[...],
    http_auth=("admin", "<password>"),   # new — the cluster requires login
    verify_certs=False,                  # new — self-signed certificate
    http_compress=True,
    timeout=30,
)
```

Also worth adding the same "don't store the embedding twice" setting to
`docker/opensearch/index_mappings/case_chunks.json`, so a freshly created index
matches production.

I will send the password separately — not over WhatsApp.

---

## PDF storage (separate piece of work)

We have hit the Supabase free storage limit, so the ~11 GB of case PDFs are moving to
Google Cloud Storage too.

The good news: PDFs are found purely by naming convention — `{case_id}.pdf` — with no
database mapping. So nothing in Postgres changes, only where the files sit.

**You have the source PDFs and the `01_extracted` files that map case IDs to
filenames, so the upload is easiest run from your machine.** Rough shape:

1. I create the storage bucket and give your Google account access
2. You run a script that reads `output/01_extracted/{case_id}.json`, finds the matching
   PDF in `sample_cases/{year}/`, and uploads it as `{case_id}.pdf`
3. I switch the app over to serve from there

Cost is about $0.26/month for 11 GB. I will send the bucket details once it exists.

**Question:** how many PDFs are currently in Supabase? The free tier only allows 1 GB,
so I suspect most were never uploaded — which would make this a first full upload
rather than a migration.

---

## Anything urgent?

No. Production is running normally on Oracle. Everything above is preparation.

The one real deadline is **6 December 2026**, when the free credit expires. After that
it is ~₹7,600/month, or we move again.

Keep Oracle running until we have switched over and confirmed everything works — it is
our rollback.
