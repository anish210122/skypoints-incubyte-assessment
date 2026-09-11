# Architecture and scaling notes

## Local executable demonstration

The Python implementation is intentionally small enough to run on a laptop. It reads the supplied USA CSV, India CSV and Australia XLSX files, normalizes the different schemas, writes a raw landing table, creates a validated staging layer, quarantines invalid records, applies latest-record-wins, routes valid records to country targets, and flattens the redemption JSON.

SQLite is used only as a lightweight demonstration database. It is **not** presented as the production technology for billions of daily records.

## Production direction

```text
Member files / Partner JSON
          |
          v
Cloud object storage / Snowflake external stage
          |
          v
COPY INTO raw tables (raw strings + VARIANT JSON)
          |
          +--> reject/quarantine + load audit
          |
          v
Set-based Snowflake SQL transformations
          |
          v
Validated staging tables
          |
          +--> ROW_NUMBER / QUALIFY latest-record-wins
          |
          +--> country target tables
          |
          +--> redemption fact table via LATERAL FLATTEN
```

For very large volumes, ingestion should be bulk/append-only rather than row-by-row, with files partitioned by feed date and source. Snowflake can scale compute independently from storage and execute the parsing/deduplication as set-based SQL. The pipeline should also be idempotent by tracking source file name/checksum and processing batch id, so replaying a file does not duplicate data.

## Important ambiguity in the supplied samples

The three supplied country files each contain local IDs `1`, `2`, `3`, but they refer to different people. Therefore the local demonstration creates `member_key = <country>:<member_id>` to avoid incorrectly merging unrelated records. In production, if SkyPoints guarantees a globally unique membership-card/member identifier, that global identifier should replace this namespaced key and becomes the partition key for the cross-country "latest record wins" rule.

This assumption is documented rather than silently treating overlapping local IDs as the same person.

## Idempotency and operational controls

The Snowflake scripts use replay-safe patterns rather than blind inserts:

- member staging is `MERGE`d using `source_file + source_row_number` as the physical source-record identity;
- redemption facts are `MERGE`d by `txn_id`;
- country targets are rebuilt from the latest-member snapshot so a member who moves countries is removed from the old target and appears only in the new target;
- rejected member rows are guarded against duplicate insertion on re-run.

For a real production scheduler, I would add a `LOAD_AUDIT` table containing batch ID, source filename, file checksum, row counts, start/end timestamps and status. A successfully processed checksum would not be loaded twice, while failed batches would remain replayable.
