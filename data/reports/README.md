# Annual report PDFs

The 15 annual reports are not stored in Git: they are large and remain the companies' copyright.

To recreate this folder, download each file listed in `../curated/documents.csv` from its `source_url`
(official BSE filings) and save it here under the name in the `file_name` column. Then run:

```
python scripts/check_documents.py
```

The script confirms each file is identical to the one used in this project (SHA-256 fingerprint),
and that the recorded statement pages are correct.
