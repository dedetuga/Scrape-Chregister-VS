# Swiss Company Enricher

Enrich Swiss company CSV files with publicly available website/contact information.

## Usage

```bash
python main.py --input input/empresas.csv --output output/empresas_enriched.csv
```

For an external CSV, pass either an absolute path or a relative path from the directory where you run the command:

```bash
python main.py --input /full/path/to/valais_completo.csv --output output/empresas_enriched.csv --workers 100
```

If you use a relative path such as `../valais_completo.csv`, it must exist relative to your current working directory. The CLI now reports the current working directory and the resolved input path when the file is missing, which makes path mistakes easier to diagnose.
