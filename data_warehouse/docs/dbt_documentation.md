# dbt Documentation Guide
# dbt 文档生成指南

This guide covers generating and serving dbt documentation.

## Overview

dbt automatically generates documentation for your entire data warehouse:
- Data lineage graphs (DAG)
- Model descriptions
- Column-level documentation
- Test results
- Source freshness
- Interactive web interface

## Generate Documentation

### Step 1: Navigate to dbt Directory

```bash
cd data_warehouse/dbt
```

### Step 2: Generate Documentation

```bash
dbt docs generate
```

This creates two files:
- `target/manifest.json` - Project metadata
- `target/catalog.json` - Database metadata

Expected output:
```
Running with dbt=1.7.0
Found 16 models, 100 tests, 0 snapshots, 0 analyses, 2 macros, 0 operations, 0 seed files, 5 sources, 0 exposures, 0 metrics

Building catalog
Catalog written to target/catalog.json
```

### Step 3: Serve Documentation

```bash
dbt docs serve
```

This starts a local web server (default: http://localhost:8080)

Expected output:
```
Serving docs at 8080
To access from your browser, navigate to: http://localhost:8080

Press Ctrl+C to exit.
```

### Step 4: View Documentation

Open browser and navigate to: http://localhost:8080

## Documentation Features

### 1. Project Overview
- Summary of models, tests, sources
- Project structure
- dbt version and configuration

### 2. Data Lineage Graph (DAG)
- Visual representation of data flow
- Source → Staging → Dimensions → Facts → Marts
- Click nodes to see model details
- Filter by model type, tags, or search

### 3. Model Documentation
For each model:
- Description
- Column definitions
- Tests applied
- Materialization strategy
- Dependencies (upstream/downstream)
- SQL code
- Compiled SQL

### 4. Source Documentation
- Source table definitions
- Freshness checks
- Column descriptions

### 5. Test Results
- All tests defined
- Test status (pass/fail)
- Test SQL

## Enhancing Documentation

### Add Model Descriptions

In `schema.yml`:
```yaml
models:
  - name: dim_user
    description: |
      User dimension table containing all user attributes.
      
      This table includes:
      - Surrogate key (user_key) for joins
      - Business key (user_id) from source
      - Card information (card_number, card_type)
      - Verification status
      
      Updated daily via dbt pipeline.
    columns:
      - name: user_key
        description: "Surrogate key - hash of user_id"
```

### Add Column Descriptions

```yaml
columns:
  - name: card_type
    description: |
      Type of transport card:
      - Regular: Standard adult card
      - Student: Discounted student card
      - Senior: Senior citizen card
      - Disabled: Disability card
```

### Add Model Meta

```yaml
models:
  - name: dim_user
    meta:
      owner: "Data Team"
      priority: "high"
      contains_pii: true
```

### Add Tags

```yaml
models:
  - name: dim_user
    tags: ["daily", "dimension", "pii"]
```

## Documentation Best Practices

### 1. Document All Models
- Add description to every model
- Explain purpose and business context
- Document any complex logic

### 2. Document All Columns
- Describe what each column represents
- Explain calculation logic for derived columns
- Note any data quality considerations

### 3. Use Markdown
- Use markdown for rich formatting
- Add lists, code blocks, links
- Include examples where helpful

### 4. Keep Documentation Updated
- Update docs when models change
- Review docs during code reviews
- Regenerate docs after changes

### 5. Include Business Context
- Explain business meaning
- Document business rules
- Link to external resources

## Sharing Documentation

### Option 1: dbt Cloud (Hosted)
- Automatic documentation hosting
- Always up-to-date
- Access control
- No setup required

### Option 2: Static Hosting
Generate static files and host on web server:

```bash
# Generate docs
dbt docs generate

# Copy files to web server
cp target/manifest.json /var/www/docs/
cp target/catalog.json /var/www/docs/
cp target/index.html /var/www/docs/
```

### Option 3: GitHub Pages
Host documentation on GitHub Pages:

```bash
# Generate docs
dbt docs generate

# Copy to docs folder
mkdir -p docs
cp target/*.json docs/
cp target/index.html docs/

# Commit and push
git add docs/
git commit -m "Update documentation"
git push
```

Then enable GitHub Pages in repository settings.

## Lineage Graph Usage

### Navigate the Graph
- **Zoom**: Mouse wheel or pinch
- **Pan**: Click and drag
- **Select**: Click node to highlight
- **Expand**: Double-click to expand upstream/downstream

### Filter the Graph
- **By model type**: staging, dimensions, facts, marts
- **By tag**: daily, dimension, fact, mart
- **By search**: Type model name

### View Model Details
Click any node to see:
- Model description
- Columns and tests
- Dependencies
- SQL code
- Run results

## Documentation in CI/CD

### Automatic Documentation Updates

```yaml
# .github/workflows/dbt-docs.yml
name: Update dbt Docs
on:
  push:
    branches: [main]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dbt
        run: pip install dbt-databricks
      - name: Generate docs
        run: |
          cd data_warehouse/dbt
          dbt deps
          dbt docs generate
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./data_warehouse/dbt/target
```

## Troubleshooting

### Error: Cannot generate catalog

**Issue**: `dbt docs generate` fails

**Solutions**:
- Ensure models have been run: `dbt run`
- Check database connection: `dbt debug`
- Verify permissions to query metadata

### Error: Port already in use

**Issue**: `dbt docs serve` fails with port error

**Solutions**:
- Use different port: `dbt docs serve --port 8081`
- Kill existing process: `lsof -ti:8080 | xargs kill`

### Documentation not updating

**Issue**: Changes not reflected in docs

**Solutions**:
- Regenerate docs: `dbt docs generate`
- Clear browser cache
- Restart docs server

## Next Steps

After generating documentation:

1. ✅ Review data lineage graph
2. ✅ Verify all models are documented
3. ✅ Share documentation URL with team
4. ➡️ Set up scheduling (dbt Cloud or Airflow)
5. ➡️ Connect Power BI for visualization

## Additional Resources

- [dbt Documentation](https://docs.getdbt.com/docs/collaborate/documentation)
- [dbt Docs Commands](https://docs.getdbt.com/reference/commands/cmd-docs)
- [Markdown Guide](https://www.markdownguide.org/basic-syntax/)

