import csv

filepath = r'c:\work\KSU\AAI\RAG\Doc\2026-01-29_export-readonly-2569_v1.csv'

# Read raw bytes to check
with open(filepath, 'rb') as f:
    raw_sample = f.read(1000)
    print('First 200 bytes (hex):')
    print(raw_sample[:200].hex())
    print('\nFirst 200 bytes (repr):')
    print(repr(raw_sample[:200]))

print('\n' + '='*60)

# Try reading with different encodings and show actual Thai text
for encoding in ['utf-8-sig', 'utf-8', 'cp874', 'tis-620', 'windows-874']:
    try:
        with open(filepath, 'r', encoding=encoding) as f:
            first_line = f.readline()
            print(f'\n{encoding}: {first_line[:100]}')
            
            # Try to read as CSV
            f.seek(0)
            reader = csv.reader(f)
            header = next(reader)
            row1 = next(reader)
            
            if 'ช' in str(header) or 'ก' in str(header):  # Check for Thai characters
                print(f'  ✓ Thai characters detected!')
                print(f'  Columns: {len(header)}')
                print(f'  Headers: {header[:5]}')
                print(f'  Sample: {row1[:5]}')
    except Exception as e:
        print(f'{encoding}: Error - {str(e)[:50]}')
