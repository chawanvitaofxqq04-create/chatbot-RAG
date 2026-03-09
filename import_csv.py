"""
CSV Import Script for RAG Database
Supports multiple encodings and creates tables based on CSV structure
"""
import csv
import psycopg2
from psycopg2 import sql
import sys
import re

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ragdb',
    'user': 'app',
    'password': 'app'
}

def detect_encoding(filepath):
    """Try to detect the correct encoding for the CSV file"""
    encodings = ['utf-8-sig', 'utf-8', 'cp874', 'tis-620', 'windows-874', 'iso-8859-11', 'latin1']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                sample = f.read(1000)
                # Check if Thai characters are present
                if any('\u0e00' <= c <= '\u0e7f' for c in sample):
                    print(f"✓ Detected encoding: {encoding} (Thai characters found)")
                    return encoding
        except:
            continue
    
    # Default to utf-8 with error handling
    print("⚠ Using utf-8 with error handling")
    return 'utf-8'

def clean_column_name(name):
    """Clean column name to be SQL-safe"""
    # Remove special characters, keep only alphanumeric and underscore
    name = re.sub(r'[^\w\s]', '', name)
    # Replace spaces with underscore
    name = name.strip().replace(' ', '_').lower()
    # Ensure it starts with a letter
    if name and not name[0].isalpha():
        name = 'col_' + name
    return name or 'column'

def infer_column_type(values):
    """Infer SQL column type from sample values"""
    # Remove empty values
    values = [v for v in values if v and v.strip()]
    
    if not values:
        return 'TEXT'
    
    # Check if all are integers
    try:
        all([int(v) for v in values])
        return 'INTEGER'
    except:
        pass
    
    # Check if all are floats
    try:
        all([float(v) for v in values])
        return 'NUMERIC(12,2)'
    except:
        pass
    
    # Check if date format
    if any(re.match(r'\d{1,2}/\d{1,2}/\d{4}', v) for v in values):
        return 'TEXT'  # Store as text, can convert later
    
    # Default to TEXT
    return 'TEXT'

def import_csv_to_db(csv_filepath, table_name=None):
    """Import CSV file into PostgreSQL database"""
    
    print(f"\n{'='*60}")
    print(f"CSV Import Tool")
    print(f"{'='*60}\n")
    
    # Detect encoding
    encoding = detect_encoding(csv_filepath)
    
    # Read CSV
    print(f"Reading CSV file: {csv_filepath}")
    try:
        with open(csv_filepath, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return False
    
    if len(rows) < 2:
        print("❌ CSV file must have at least header and one data row")
        return False
    
    # Extract headers and data
    headers = rows[0]
    data_rows = rows[1:]
    
    print(f"✓ Found {len(headers)} columns and {len(data_rows)} data rows")
    
    # Clean column names
    column_names = [clean_column_name(h) for h in headers]
    
    # Auto-generate table name if not provided
    if not table_name:
        import os
        table_name = 'imported_' + os.path.basename(csv_filepath).replace('.csv', '').replace('-', '_').replace(' ', '_')
        table_name = clean_column_name(table_name)
    
    print(f"Table name: {table_name}")
    
    # Infer column types from first 100 rows
    print("\nInferring column types...")
    column_types = []
    for i, col_name in enumerate(column_names):
        sample_values = [row[i] if i < len(row) else '' for row in data_rows[:100]]
        col_type = infer_column_type(sample_values)
        column_types.append(col_type)
        print(f"  {col_name}: {col_type}")
    
    # Connect to database
    print(f"\nConnecting to database...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✓ Connected")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Create table
    print(f"\nCreating table '{table_name}'...")
    try:
        # Drop if exists
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))
        
        # Create table
        columns_def = []
        for col_name, col_type in zip(column_names, column_types):
            columns_def.append(sql.SQL("{} {}").format(sql.Identifier(col_name), sql.SQL(col_type)))
        
        create_query = sql.SQL("CREATE TABLE {} ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(columns_def)
        )
        
        cur.execute(create_query)
        conn.commit()
        print(f"✓ Table created")
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        conn.rollback()
        conn.close()
        return False
    
    # Insert data
    print(f"\nInserting {len(data_rows)} rows...")
    inserted = 0
    errors = 0
    
    for i, row in enumerate(data_rows):
        try:
            # Pad row if needed
            while len(row) < len(column_names):
                row.append('')
            
            # Truncate if too long
            row = row[:len(column_names)]
            
            # Convert empty strings to NULL for numeric types
            processed_row = []
            for val, col_type in zip(row, column_types):
                if not val or not val.strip():
                    if col_type in ['INTEGER', 'NUMERIC(12,2)']:
                        processed_row.append(None)
                    else:
                        processed_row.append('')
                else:
                    processed_row.append(val.strip())
            
            # Insert
            insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table_name),
                sql.SQL(', ').join([sql.Identifier(c) for c in column_names]),
                sql.SQL(', ').join([sql.Placeholder()] * len(column_names))
            )
            
            cur.execute(insert_query, processed_row)
            inserted += 1
            
            if (i + 1) % 100 == 0:
                print(f"  Inserted {i + 1} rows...")
                conn.commit()
        
        except Exception as e:
            errors += 1
            if errors <= 5:  # Show first 5 errors
                print(f"  ⚠ Row {i + 1} error: {str(e)[:100]}")
    
    conn.commit()
    
    print(f"\n{'='*60}")
    print(f"Import Summary:")
    print(f"  Total rows: {len(data_rows)}")
    print(f"  Inserted: {inserted}")
    print(f"  Errors: {errors}")
    print(f"  Table: {table_name}")
    print(f"{'='*60}\n")
    
    # Show sample data
    print("Sample data (first 5 rows):")
    cur.execute(sql.SQL("SELECT * FROM {} LIMIT 5").format(sql.Identifier(table_name)))
    sample = cur.fetchall()
    for row in sample:
        print(f"  {row[:5]}...")  # Show first 5 columns
    
    conn.close()
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_csv.py <csv_file> [table_name]")
        print("\nExample:")
        print("  python import_csv.py data.csv")
        print("  python import_csv.py data.csv my_table")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    table_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    import_csv_to_db(csv_file, table_name)
