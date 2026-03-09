import csv, io

def decode_byte(b):
    if b in (0x0a, 0x0d, 0x2c): return chr(b)
    if 0x01 <= b <= 0x60: return chr(0x0e00 + b)
    if 0x20 <= b <= 0x7e: return chr(b)
    return bytes([b]).decode('cp874', errors='replace') if 0x80 <= b <= 0xff else chr(b)

with open(r'c:\work\KSU\AAI\RAG\Doc\2026-01-29_export-readonly-2569_v1.csv', 'rb') as f:
    raw = f.read()

text = ''.join(decode_byte(b) for b in raw)
reader = csv.reader(io.StringIO(text, newline=''), quotechar='\x00', quoting=csv.QUOTE_NONE)
rows = list(reader)

print(f"Total rows: {len(rows)}")

# Show rows 23, 30 fully
for idx in [7, 8, 15, 16, 23, 30]:
    r = rows[idx]
    print(f"\nRow {idx} ({len(r)} cols):")
    for i, v in enumerate(r):
        print(f"  [{i:2d}] {v[:70]}")

# Check phone encoding — look at raw bytes for phone field
# Find row 23 in raw to check phone bytes
# Phone is "ะูอำืืูอาะึุ" — find its bytes
phone_sample = rows[23][9] if len(rows[23]) > 9 else ''
print(f"\nPhone sample: {repr(phone_sample)}")
print(f"Phone codepoints: {[hex(ord(c)) for c in phone_sample]}")
# Thai digits: ๐=0x0e50 ๑=0x0e51...๙=0x0e59
# Check if phone is digits shifted
for c in phone_sample:
    cp = ord(c)
    if 0x0e50 <= cp <= 0x0e59:
        print(f"  {c} = Thai digit {cp - 0x0e50}")
    elif 0x0e00 <= cp <= 0x0e7f:
        print(f"  {c} = Thai letter 0x{cp:04x}")
    else:
        print(f"  {c} = ASCII 0x{cp:02x}")
