#!/usr/bin/env python3
"""
Convert dbt manifest.json and catalog.json to RAG-friendly Markdown documentation.

This script processes dbt artifacts and generates individual Markdown files
for each model, source, and macro, making them more suitable for RAG systems.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class DbtRagDocGenerator:
    """Generate RAG-friendly documentation from dbt artifacts."""
    
    def __init__(self, target_dir: str, output_dir: str = "rag_docs"):
        """
        Initialize the generator.
        
        Args:
            target_dir: Path to dbt target directory (contains manifest.json and catalog.json)
            output_dir: Output directory for generated Markdown files
        """
        self.target_dir = Path(target_dir)
        self.output_dir = Path(output_dir)
        self.manifest: Dict[str, Any] = {}
        self.catalog: Dict[str, Any] = {}
        self.child_map: Dict[str, List[str]] = {}  # Maps node_id to list of nodes that depend on it
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def load_artifacts(self):
        """Load manifest.json and catalog.json files."""
        manifest_path = self.target_dir / "manifest.json"
        catalog_path = self.target_dir / "catalog.json"
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.json not found at {manifest_path}")
        if not catalog_path.exists():
            raise FileNotFoundError(f"catalog.json not found at {catalog_path}")
        
        print(f"Loading {manifest_path}...")
        with open(manifest_path, 'r', encoding='utf-8') as f:
            self.manifest = json.load(f)
        
        print(f"Loading {catalog_path}...")
        with open(catalog_path, 'r', encoding='utf-8') as f:
            self.catalog = json.load(f)
        
        print(f"Loaded {len(self.manifest.get('nodes', {}))} nodes from manifest")
        print(f"Loaded {len(self.catalog.get('nodes', {}))} nodes from catalog")
        
        # Build child_map for lineage (reverse dependencies)
        self._build_lineage_map()
    
    def get_node_description(self, node: Dict[str, Any]) -> str:
        """Extract description from node, with fallback to empty string."""
        return node.get('description', '') or ''
    
    def get_column_description(self, column: Dict[str, Any]) -> str:
        """Extract column description from catalog or manifest."""
        return column.get('description', '') or ''
    
    def format_sql(self, sql: str) -> str:
        """Format SQL code for Markdown display."""
        if not sql:
            return ""
        # Basic SQL formatting - indent with 4 spaces
        lines = sql.split('\n')
        formatted = []
        for line in lines:
            formatted.append(f"    {line}")
        return '\n'.join(formatted)
    
    def _build_lineage_map(self):
        """Build reverse dependency map (child_map) for lineage tracking."""
        # Initialize child_map for all nodes and sources
        all_nodes = {**self.manifest.get('nodes', {}), **self.manifest.get('sources', {})}
        
        for unique_id in all_nodes.keys():
            self.child_map[unique_id] = []
        
        # Build reverse dependencies
        nodes = self.manifest.get('nodes', {})
        for unique_id, node in nodes.items():
            deps = node.get('depends_on', {})
            parent_nodes = deps.get('nodes', [])
            
            for parent_id in parent_nodes:
                if parent_id in self.child_map:
                    if unique_id not in self.child_map[parent_id]:
                        self.child_map[parent_id].append(unique_id)
        
        print(f"Built lineage map with {len([k for k, v in self.child_map.items() if v])} nodes with downstream dependencies")
    
    def get_dependencies(self, node: Dict[str, Any]) -> List[str]:
        """Extract dependency list from node (upstream dependencies)."""
        deps = node.get('depends_on', {})
        nodes = deps.get('nodes', [])
        return [self._format_unique_id(nid) for nid in nodes]
    
    def get_downstream_dependencies(self, unique_id: str) -> List[str]:
        """Get list of nodes that depend on this node (downstream dependencies)."""
        children = self.child_map.get(unique_id, [])
        return [self._format_unique_id(child_id) for child_id in children]
    
    def _format_unique_id(self, unique_id: str) -> str:
        """Format unique_id for display (remove model. prefix, etc.)."""
        if unique_id.startswith('model.'):
            return unique_id.replace('model.', '')
        if unique_id.startswith('source.'):
            return unique_id.replace('source.', '')
        return unique_id
    
    def get_catalog_info(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """Get catalog information for a node."""
        catalog_nodes = self.catalog.get('nodes', {})
        return catalog_nodes.get(unique_id)
    
    def generate_model_doc(self, unique_id: str, node: Dict[str, Any]) -> str:
        """Generate Markdown documentation for a dbt model."""
        model_name = node.get('name', '')
        resource_type = node.get('resource_type', '')
        schema = node.get('schema', '')
        database = node.get('database', '')
        
        # Get description
        description = self.get_node_description(node)
        
        # Get SQL
        raw_sql = node.get('raw_sql', '')
        compiled_sql = node.get('compiled_sql', '')
        
        # Get dependencies
        dependencies = self.get_dependencies(node)
        
        # Get catalog information
        catalog_info = self.get_catalog_info(unique_id)
        
        # Build Markdown content
        lines = []
        lines.append(f"# {model_name}")
        lines.append("")
        lines.append(f"**Type:** {resource_type}  ")
        lines.append(f"**Database:** `{database}`  ")
        lines.append(f"**Schema:** `{schema}`  ")
        lines.append(f"**Unique ID:** `{unique_id}`")
        lines.append("")
        
        if description:
            lines.append("## Description")
            lines.append("")
            lines.append(description)
            lines.append("")
        
        # Columns information
        if catalog_info:
            columns = catalog_info.get('columns', {})
            stats = catalog_info.get('stats', {})
            
            if columns:
                lines.append("## Columns")
                lines.append("")
                lines.append("| Column Name | Type | Description |")
                lines.append("|------------|------|-------------|")
                
                for col_name, col_info in sorted(columns.items()):
                    col_type = col_info.get('type', 'N/A')
                    col_desc = self.get_column_description(col_info)
                    lines.append(f"| `{col_name}` | `{col_type}` | {col_desc} |")
                
                lines.append("")
            
            # Statistics
            if stats:
                lines.append("## Statistics")
                lines.append("")
                for stat_id, stat_info in stats.items():
                    if stat_info.get('include', False):
                        label = stat_info.get('label', stat_id)
                        value = stat_info.get('value', 'N/A')
                        lines.append(f"- **{label}:** {value}")
                lines.append("")
        
        # Lineage (Upstream and Downstream)
        downstream = self.get_downstream_dependencies(unique_id)
        
        if dependencies or downstream:
            lines.append("## Lineage")
            lines.append("")
            
            if dependencies:
                lines.append("### Upstream Dependencies")
                lines.append("")
                lines.append("This model depends on:")
                lines.append("")
                for dep in dependencies:
                    lines.append(f"- `{dep}`")
                lines.append("")
            
            if downstream:
                lines.append("### Downstream Dependencies")
                lines.append("")
                lines.append("The following models depend on this model:")
                lines.append("")
                for child in downstream:
                    lines.append(f"- `{child}`")
                lines.append("")
            
            if not dependencies and not downstream:
                lines.append("No dependencies.")
                lines.append("")
        
        # SQL Code
        if compiled_sql:
            lines.append("## Compiled SQL")
            lines.append("")
            lines.append("```sql")
            lines.append(compiled_sql)
            lines.append("```")
            lines.append("")
        elif raw_sql:
            lines.append("## Raw SQL")
            lines.append("")
            lines.append("```sql")
            lines.append(raw_sql)
            lines.append("```")
            lines.append("")
        
        # Metadata
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **Materialized as:** {node.get('config', {}).get('materialized', 'view')}")
        lines.append(f"- **Tags:** {', '.join(node.get('tags', []))}")
        lines.append("")
        
        return '\n'.join(lines)
    
    def generate_source_doc(self, unique_id: str, node: Dict[str, Any]) -> str:
        """Generate Markdown documentation for a dbt source."""
        source_name = node.get('source_name', '')
        table_name = node.get('name', '')
        schema = node.get('schema', '')
        database = node.get('database', '')
        
        description = self.get_node_description(node)
        
        # Get catalog information
        catalog_info = self.get_catalog_info(unique_id)
        
        lines = []
        lines.append(f"# Source: {source_name}.{table_name}")
        lines.append("")
        lines.append(f"**Type:** Source Table  ")
        lines.append(f"**Database:** `{database}`  ")
        lines.append(f"**Schema:** `{schema}`  ")
        lines.append(f"**Unique ID:** `{unique_id}`")
        lines.append("")
        
        if description:
            lines.append("## Description")
            lines.append("")
            lines.append(description)
            lines.append("")
        
        # Columns
        if catalog_info:
            columns = catalog_info.get('columns', {})
            stats = catalog_info.get('stats', {})
            
            if columns:
                lines.append("## Columns")
                lines.append("")
                lines.append("| Column Name | Type | Description |")
                lines.append("|------------|------|-------------|")
                
                for col_name, col_info in sorted(columns.items()):
                    col_type = col_info.get('type', 'N/A')
                    col_desc = self.get_column_description(col_info)
                    lines.append(f"| `{col_name}` | `{col_type}` | {col_desc} |")
                
                lines.append("")
            
            # Statistics
            if stats:
                lines.append("## Statistics")
                lines.append("")
                for stat_id, stat_info in stats.items():
                    if stat_info.get('include', False):
                        label = stat_info.get('label', stat_id)
                        value = stat_info.get('value', 'N/A')
                        lines.append(f"- **{label}:** {value}")
                lines.append("")
        
        # Lineage for sources
        downstream = self.get_downstream_dependencies(unique_id)
        if downstream:
            lines.append("## Lineage")
            lines.append("")
            lines.append("### Downstream Dependencies")
            lines.append("")
            lines.append("The following models depend on this source:")
            lines.append("")
            for child in downstream:
                lines.append(f"- `{child}`")
            lines.append("")
        
        return '\n'.join(lines)
    
    def generate_index(self, all_docs: List[Dict[str, str]]):
        """Generate an index file listing all documentation."""
        lines = []
        lines.append("# dbt Project Documentation Index")
        lines.append("")
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("## Models")
        lines.append("")
        
        models = [d for d in all_docs if d['type'] == 'model']
        sources = [d for d in all_docs if d['type'] == 'source']
        
        for doc in sorted(models, key=lambda x: x['name']):
            lines.append(f"- [{doc['name']}]({doc['filename']})")
        
        lines.append("")
        lines.append("## Sources")
        lines.append("")
        
        for doc in sorted(sources, key=lambda x: x['name']):
            lines.append(f"- [{doc['name']}]({doc['filename']})")
        
        lines.append("")
        
        index_path = self.output_dir / "README.md"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"Generated index: {index_path}")
    
    def generate_all_docs(self):
        """Generate documentation for all nodes in manifest."""
        nodes = self.manifest.get('nodes', {})
        sources = self.manifest.get('sources', {})
        
        all_docs = []
        
        # Process models
        print("\nGenerating model documentation...")
        for unique_id, node in nodes.items():
            if node.get('resource_type') == 'model':
                model_name = node.get('name', 'unknown')
                filename = f"model_{model_name}.md"
                filepath = self.output_dir / filename
                
                content = self.generate_model_doc(unique_id, node)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                all_docs.append({
                    'type': 'model',
                    'name': model_name,
                    'filename': filename,
                    'unique_id': unique_id
                })
                print(f"  Generated: {filename}")
        
        # Process sources
        print("\nGenerating source documentation...")
        for unique_id, source_node in sources.items():
            source_name = source_node.get('source_name', 'unknown')
            table_name = source_node.get('name', 'unknown')
            filename = f"source_{source_name}_{table_name}.md"
            filepath = self.output_dir / filename
            
            content = self.generate_source_doc(unique_id, source_node)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            all_docs.append({
                'type': 'source',
                'name': f"{source_name}.{table_name}",
                'filename': filename,
                'unique_id': unique_id
            })
            print(f"  Generated: {filename}")
        
        # Generate index
        print("\nGenerating index...")
        self.generate_index(all_docs)
        
        # Generate lineage graph document
        print("\nGenerating lineage graph...")
        self.generate_lineage_graph(all_docs)
        
        print(f"\n✅ Generated {len(all_docs)} documentation files in {self.output_dir}")
        return all_docs
    
    def generate_lineage_graph(self, all_docs: List[Dict[str, str]]):
        """Generate a comprehensive lineage graph document."""
        lines = []
        lines.append("# dbt Project Lineage Graph")
        lines.append("")
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("This document shows the complete data lineage for all models and sources.")
        lines.append("")
        
        # Group by layer
        staging_models = []
        dimension_models = []
        fact_models = []
        mart_models = []
        sources = []
        
        nodes = self.manifest.get('nodes', {})
        source_nodes = self.manifest.get('sources', {})
        
        for doc in all_docs:
            unique_id = doc['unique_id']
            if doc['type'] == 'source':
                sources.append((unique_id, doc))
            elif unique_id in nodes:
                node = nodes[unique_id]
                schema = node.get('schema', '')
                if schema == 'staging':
                    staging_models.append((unique_id, doc))
                elif schema == 'dimensions':
                    dimension_models.append((unique_id, doc))
                elif schema == 'facts':
                    fact_models.append((unique_id, doc))
                elif schema == 'marts':
                    mart_models.append((unique_id, doc))
        
        # Sources section
        if sources:
            lines.append("## Sources")
            lines.append("")
            for unique_id, doc in sources:
                downstream = self.get_downstream_dependencies(unique_id)
                lines.append(f"### {doc['name']}")
                lines.append("")
                if downstream:
                    lines.append("**Used by:**")
                    for child in downstream:
                        lines.append(f"- `{child}`")
                else:
                    lines.append("*No downstream dependencies*")
                lines.append("")
        
        # Staging layer
        if staging_models:
            lines.append("## Staging Layer")
            lines.append("")
            for unique_id, doc in staging_models:
                upstream = self.get_dependencies(nodes[unique_id])
                downstream = self.get_downstream_dependencies(unique_id)
                lines.append(f"### {doc['name']}")
                lines.append("")
                if upstream:
                    lines.append("**Depends on:**")
                    for dep in upstream:
                        lines.append(f"- `{dep}`")
                    lines.append("")
                if downstream:
                    lines.append("**Used by:**")
                    for child in downstream:
                        lines.append(f"- `{child}`")
                    lines.append("")
                if not upstream and not downstream:
                    lines.append("*No dependencies*")
                    lines.append("")
        
        # Dimensions layer
        if dimension_models:
            lines.append("## Dimensions Layer")
            lines.append("")
            for unique_id, doc in dimension_models:
                upstream = self.get_dependencies(nodes[unique_id])
                downstream = self.get_downstream_dependencies(unique_id)
                lines.append(f"### {doc['name']}")
                lines.append("")
                if upstream:
                    lines.append("**Depends on:**")
                    for dep in upstream:
                        lines.append(f"- `{dep}`")
                    lines.append("")
                if downstream:
                    lines.append("**Used by:**")
                    for child in downstream:
                        lines.append(f"- `{child}`")
                    lines.append("")
        
        # Facts layer
        if fact_models:
            lines.append("## Facts Layer")
            lines.append("")
            for unique_id, doc in fact_models:
                upstream = self.get_dependencies(nodes[unique_id])
                downstream = self.get_downstream_dependencies(unique_id)
                lines.append(f"### {doc['name']}")
                lines.append("")
                if upstream:
                    lines.append("**Depends on:**")
                    for dep in upstream:
                        lines.append(f"- `{dep}`")
                    lines.append("")
                if downstream:
                    lines.append("**Used by:**")
                    for child in downstream:
                        lines.append(f"- `{child}`")
                    lines.append("")
        
        # Marts layer
        if mart_models:
            lines.append("## Marts Layer")
            lines.append("")
            for unique_id, doc in mart_models:
                upstream = self.get_dependencies(nodes[unique_id])
                downstream = self.get_downstream_dependencies(unique_id)
                lines.append(f"### {doc['name']}")
                lines.append("")
                if upstream:
                    lines.append("**Depends on:**")
                    for dep in upstream:
                        lines.append(f"- `{dep}`")
                    lines.append("")
                if downstream:
                    lines.append("**Used by:**")
                    for child in downstream:
                        lines.append(f"- `{child}`")
                    lines.append("")
                else:
                    lines.append("*End of lineage (no downstream dependencies)*")
                    lines.append("")
        
        lineage_path = self.output_dir / "LINEAGE.md"
        with open(lineage_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"Generated lineage graph: {lineage_path}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert dbt artifacts to RAG-friendly Markdown documentation'
    )
    parser.add_argument(
        '--target-dir',
        type=str,
        default='target',
        help='Path to dbt target directory (default: target)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='rag_docs',
        help='Output directory for Markdown files (default: rag_docs)'
    )
    
    args = parser.parse_args()
    
    generator = DbtRagDocGenerator(
        target_dir=args.target_dir,
        output_dir=args.output_dir
    )
    
    try:
        generator.load_artifacts()
        generator.generate_all_docs()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

