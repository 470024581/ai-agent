#!/usr/bin/env python3
"""
Basic Data Statistics Script for Shanghai Transport Card Database
上海交通卡数据库基本数据统计脚本

Note: Detailed data validation and cleaning logic should be implemented in dbt tests.
This script only provides basic statistics and connection testing.
"""

import os
import sys
import json
import argparse
from datetime import datetime, time
from decimal import Decimal
from collections import defaultdict
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('SUPABASE_DB_HOST', 'db.your-project.supabase.co'),
    'port': int(os.getenv('SUPABASE_DB_PORT', '5432')),
    'database': os.getenv('SUPABASE_DB_NAME', 'postgres'),
    'user': os.getenv('SUPABASE_DB_USER', 'postgres'),
    'password': os.getenv('SUPABASE_DB_PASSWORD')
}


class DataStatistics:
    """Basic data statistics class - detailed validation should be done in dbt tests"""
    
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor(cursor_factory=RealDictCursor)
        self.stats = {}
        
    def check_table_exists(self, table_name):
        """Check if table exists"""
        self.cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """, (table_name,))
        return self.cursor.fetchone()['exists']
    
    def get_table_statistics(self, table_name):
        """Get basic statistics for a table"""
        if not self.check_table_exists(table_name):
            print(f"  ⚠ Table '{table_name}' does not exist")
            return None
        
        stats = {}
        
        # Row count
        self.cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        stats['row_count'] = self.cursor.fetchone()['count']
        
        # Column information
        self.cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        stats['columns'] = self.cursor.fetchall()
        
        # Date range (if date columns exist)
        date_columns = ['created_at', 'transaction_date', 'topup_date']
        for col in date_columns:
            if any(c['column_name'] == col for c in stats['columns']):
                self.cursor.execute(f"""
                    SELECT MIN({col}) as min_date, MAX({col}) as max_date
                    FROM {table_name}
                    WHERE {col} IS NOT NULL
                """)
                date_range = self.cursor.fetchone()
                if date_range and date_range['min_date']:
                    stats[f'{col}_range'] = {
                        'min': str(date_range['min_date']),
                        'max': str(date_range['max_date'])
                    }
        
        return stats
    
    def get_all_statistics(self):
        """Get statistics for all tables"""
        tables = ['users', 'stations', 'routes', 'transactions', 'topups']
        
        print("Collecting table statistics...")
        for table in tables:
            print(f"  Analyzing {table}...")
            stats = self.get_table_statistics(table)
            if stats:
                self.stats[table] = stats
    
    def generate_report(self, output_format='json', output_file=None):
        """Generate statistics report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'note': 'For detailed data validation and cleaning, use dbt tests (dbt test)'
        }
        
        if output_format == 'json':
            report_str = json.dumps(report, indent=2, default=str)
        elif output_format == 'html':
            report_str = self.generate_html_report(report)
        else:
            report_str = self.generate_text_report(report)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_str)
            print(f"\nReport saved to: {output_file}")
        else:
            print("\n" + "=" * 60)
            print("VALIDATION REPORT")
            print("=" * 60)
            print(report_str)
        
        return report
    
    def generate_text_report(self, report):
        """Generate text format report"""
        lines = []
        lines.append(f"Data Statistics Report - {report['timestamp']}")
        lines.append("=" * 60)
        lines.append("\n" + report.get('note', ''))
        lines.append("\nTable Statistics:")
        lines.append("-" * 60)
        
        for table_name, stats in report['statistics'].items():
            lines.append(f"\n{table_name.upper()}:")
            lines.append(f"  Row Count: {stats.get('row_count', 0):,}")
            
            if 'columns' in stats:
                lines.append(f"  Columns: {len(stats['columns'])}")
            
            # Show date ranges if available
            for key, value in stats.items():
                if key.endswith('_range'):
                    col_name = key.replace('_range', '')
                    lines.append(f"  {col_name} Range: {value.get('min', 'N/A')} to {value.get('max', 'N/A')}")
        
        lines.append("\n" + "=" * 60)
        lines.append("Note: For detailed data validation, run 'dbt test' after setting up dbt models")
        
        return "\n".join(lines)
    
    def generate_html_report(self, report):
        """Generate HTML format report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Data Statistics Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .statistics {{ background: #f5f5f5; padding: 15px; margin: 10px 0; }}
        .note {{ background: #fff3cd; padding: 15px; margin: 10px 0; border-left: 4px solid #ffc107; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Data Statistics Report</h1>
    <p>Generated: {report['timestamp']}</p>
    
    <div class="note">
        <strong>Note:</strong> {report.get('note', 'For detailed data validation, use dbt tests')}
    </div>
    
    <div class="statistics">
        <h2>Table Statistics</h2>
"""
        for table_name, stats in report['statistics'].items():
            html += f"""
        <h3>{table_name.upper()}</h3>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Row Count</td><td>{stats.get('row_count', 0):,}</td></tr>
            <tr><td>Columns</td><td>{len(stats.get('columns', []))}</td></tr>
"""
            for key, value in stats.items():
                if key.endswith('_range'):
                    col_name = key.replace('_range', '')
                    html += f"<tr><td>{col_name} Range</td><td>{value.get('min', 'N/A')} to {value.get('max', 'N/A')}</td></tr>"
            html += "</table>"
        
        html += """
    </div>
</body>
</html>
"""
        return html
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
    
    def generate_report(self, output_format='json', output_file=None):
        """Generate statistics report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'note': 'For detailed data validation and cleaning, use dbt tests (dbt test)'
        }
        
        if output_format == 'json':
            report_str = json.dumps(report, indent=2, default=str)
        elif output_format == 'html':
            report_str = self.generate_html_report(report)
        else:
            report_str = self.generate_text_report(report)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_str)
            print(f"\nReport saved to: {output_file}")
        else:
            print("\n" + "=" * 60)
            print("STATISTICS REPORT")
            print("=" * 60)
            print(report_str)
        
        return report
    
    def generate_text_report(self, report):
        """Generate text format report"""
        lines = []
        lines.append(f"Data Statistics Report - {report['timestamp']}")
        lines.append("=" * 60)
        lines.append("\n" + report.get('note', ''))
        lines.append("\nTable Statistics:")
        lines.append("-" * 60)
        
        for table_name, stats in report['statistics'].items():
            lines.append(f"\n{table_name.upper()}:")
            lines.append(f"  Row Count: {stats.get('row_count', 0):,}")
            
            if 'columns' in stats:
                lines.append(f"  Columns: {len(stats['columns'])}")
            
            # Show date ranges if available
            for key, value in stats.items():
                if key.endswith('_range'):
                    col_name = key.replace('_range', '')
                    lines.append(f"  {col_name} Range: {value.get('min', 'N/A')} to {value.get('max', 'N/A')}")
        
        lines.append("\n" + "=" * 60)
        lines.append("Note: For detailed data validation, run 'dbt test' after setting up dbt models")
        
        return "\n".join(lines)
    
    def generate_html_report(self, report):
        """Generate HTML format report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Data Statistics Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .statistics {{ background: #f5f5f5; padding: 15px; margin: 10px 0; }}
        .note {{ background: #fff3cd; padding: 15px; margin: 10px 0; border-left: 4px solid #ffc107; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Data Statistics Report</h1>
    <p>Generated: {report['timestamp']}</p>
    
    <div class="note">
        <strong>Note:</strong> {report.get('note', 'For detailed data validation, use dbt tests')}
    </div>
    
    <div class="statistics">
        <h2>Table Statistics</h2>
"""
        for table_name, stats in report['statistics'].items():
            html += f"""
        <h3>{table_name.upper()}</h3>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Row Count</td><td>{stats.get('row_count', 0):,}</td></tr>
            <tr><td>Columns</td><td>{len(stats.get('columns', []))}</td></tr>
"""
            for key, value in stats.items():
                if key.endswith('_range'):
                    col_name = key.replace('_range', '')
                    html += f"<tr><td>{col_name} Range</td><td>{value.get('min', 'N/A')} to {value.get('max', 'N/A')}</td></tr>"
            html += "</table>"
        
        html += """
    </div>
</body>
</html>
"""
        return html


def get_db_connection():
    """Establish database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Get basic statistics for Shanghai Transport Card database. '
                    'For detailed validation, use dbt tests (dbt test).'
    )
    parser.add_argument('--format', choices=['json', 'html', 'text'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--output', type=str, help='Output file path (optional)')
    
    args = parser.parse_args()
    
    # Validate database password
    if not DB_CONFIG['password']:
        print("Error: SUPABASE_DB_PASSWORD not set in .env file")
        sys.exit(1)
    
    print("=" * 60)
    print("Shanghai Transport Card - Data Statistics")
    print("=" * 60)
    print(f"Database: {DB_CONFIG['host']}")
    print(f"Output Format: {args.format}")
    if args.output:
        print(f"Output File: {args.output}")
    print("=" * 60)
    print("Note: Detailed validation should be done using dbt tests")
    print("=" * 60)
    
    conn = get_db_connection()
    stats = DataStatistics(conn)
    
    try:
        stats.get_all_statistics()
        
        # Generate report
        report = stats.generate_report(args.format, args.output)
        
        print("\n✓ Statistics collection completed!")
        print("  Run 'dbt test' for detailed data validation")
    
    except Exception as e:
        print(f"\nError during statistics collection: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        stats.close()
        conn.close()


if __name__ == '__main__':
    main()

