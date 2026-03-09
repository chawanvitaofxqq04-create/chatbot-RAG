"""
Final correct import for applicants CSV.

Structure (after CSV parsing with proper embedded newline handling):
- Row 0: headers1 (13 cols) — รอบ,คณะ,ระดับ,หลักสูตร,หลักสูตรย่อ,โควต้า,จังหวัดภูมิกำเนิด,อำเภอ,ตำบล,โรงเรียน,จังหวัดโรงเรียน,คำนำหน้า
- Row 1: headers2 (7 cols) — ชื่อ,นามสกุล,เบอร์โทร,LINE,FACEBOOK,ปีการศึกษา,สถานะ
- Row 2: headers3 (2 cols) — ชำระเงิน,วันที่สมัคร

Each student = one "DATA13" row (13 cols, col[0]=program details, col[1..12]=academic info)
             + one "DATA_PERS" row (7-15 cols, col[0]=ชื่อ, col[1]=นามสกุล, ...)

The DATA13 rows always have col[2]= รอบ description starting with 'รอบ'
OR col[0] = suffix of a section + cols 1..N = academic data.

Looking at Row 7 (13 cols):
  [0] ่างกลโรงงาน      <- program name suffix
  [1] ปวสฮ             <- level abbreviation
  [2] รอบภัภ...        <- รอบ description (section)
  [3] กา               <- จังหวัดภูมิกำเนิด? NO...

Actually studying more carefully:
Row 7 cols: program_suffix, level, rob, province_origin, province_school_suffix,
            district, subdistrict, school, province_school_prefix, province_school_suffix2, prefix, first_name

Let me just look at rows with 13 cols — those are "full academic rows"
And rows where col[5] is ปีการศึกษา (e.g. าีึู = 2568) are personal rows.

CORRECT APPROACH:
- A row is "personal" if col[5] contains 'าีึู' (2568 in this encoding) or 'าีีั' or similar year pattern
  AND col[6] contains 'ยืนยัน' or 'รอตรวจสอบ' (status)
- A row is "academic" if col[1] contains 'คณะ' or ends with faculty name AND col[2] starts with 'รอบ'

From Row 23 (15 cols - most complete personal row):
  [0] าตรีภีภคณะษ  <- this is the LAST chunk of รอบ description
  [1] สกลนคร      <- province_school  
  [2] ส่องดาว     <- district
  [3] วัฒนา       <- subdistrict
  [4] ส่องดาววิทยาคม <- school
  [5] สกลนคร      <- province_school
  [6] นางสาว      <- prefix
  [7] ปวีณ์ธิดา   <- first_name
  [8] คำคุณคำ     <- last_name
  [9] เบอร์โทร
  [10] LINE
  [11] FACEBOOK
  [12] ปีการศึกษา
  [13] สถานะ
  [14] วันที่สมัคร/ชำระเงิน

So personal rows end with: ...prefix, first_name, last_name, phone, line, fb, year, status, date

SIMPLEST DETECTION: 
- If 2nd-to-last col is in {'ยืนยันการตรวจสอบแล้ว','รอตรวจสอบ'} → personal row
- If col[-2] matches status → personal row, and we extract from the right side
"""

import csv, io, psycopg2

DB_CONFIG = dict(host='localhost', port=5432, database='ragdb', user='app', password='app')
FILEPATH = r'c:\work\KSU\AAI\RAG\Doc\2026-01-29_export-readonly-2569_v1.csv'

# Status strings as they appear after full Thai decode (0x01-0x5f → Thai)
STATUS_VALUES = {'ยืนยันการตรวจสอบแล้ว', 'รอตรวจสอบ'}

# Reverse map: Thai 0x0e20-0x0e5f back to ASCII 0x20-0x5f (for phone/LINE/year)
_THAI_TO_ASCII = {chr(0x0e00 + b): chr(b) for b in range(0x20, 0x60)}


def thai_to_ascii(s: str) -> str:
    """Reverse-decode Thai-encoded ASCII fields (phone numbers, LINE IDs, years)."""
    return ''.join(_THAI_TO_ASCII.get(c, c) for c in s)


# Safe placeholders for bytes that are both Thai chars AND CSV control chars
# byte 0x0d = ญ (CR) and byte 0x0a = ๊ (LF) — use rare Unicode PUA characters
_CR_PLACEHOLDER  = '\ue00d'   # PUA char for byte 0x0d (ญ)
_LF_PLACEHOLDER  = '\ue00a'   # PUA char for byte 0x0a (๊)


def decode_byte(b):
    # Keep comma as CSV field separator, map everything else
    if b == 0x2c:
        return chr(b)
    # Full Thai range: bytes 0x01-0x5f → Thai unicode 0x0e01-0x0e5f
    # NOTE: 0x0a(ช) and 0x0d(ญ) are in this range and decoded here
    # They only appear mid-field (Thai words), never as record separators
    if 0x01 <= b <= 0x5f:
        return chr(0x0e00 + b)
    # Normal ASCII (0x61-0x7e = a-z etc.)
    if 0x20 <= b <= 0x7e:
        return chr(b)
    # High bytes 0x80-0xff: cp874 Thai extension
    if 0x80 <= b <= 0xff:
        return bytes([b]).decode('cp874', errors='replace')
    return chr(b)


def restore_placeholders(s: str) -> str:
    """No-op: placeholders no longer needed since we split at raw byte level."""
    return s


def is_personal_row(row):
    """Detect personal info row: has status in col[-2] (or near end)."""
    for i, v in enumerate(row):
        if v.strip() in STATUS_VALUES:
            # status found — this is a personal row
            return True, i
    return False, -1


def extract_personal(row, status_idx):
    """Extract personal fields from right side of row, anchored at status_idx."""
    # From status_idx going left: status, year, facebook, line, phone, last, first, prefix
    # Going right from status: date
    r = [v.strip() for v in row]
    status = r[status_idx]
    
    # Extract from right, working backwards from status_idx
    def get(idx):
        return r[idx] if 0 <= idx < len(r) else ''
    
    # Pattern: ..., province_school, prefix, first_name, last_name, phone, line, fb, year, STATUS, date
    date_apply  = get(status_idx + 1) if status_idx + 1 < len(r) else ''
    year        = get(status_idx - 1)
    facebook    = get(status_idx - 2)
    line_id     = get(status_idx - 3)
    phone       = get(status_idx - 4)
    last_name   = get(status_idx - 5)
    first_name  = get(status_idx - 6)
    prefix      = get(status_idx - 7)

    # Left side: province_school, subdistrict?, district?, ...
    left = r[:max(0, status_idx - 7)]

    return {
        'prefix': restore_placeholders(prefix),
        'first_name': restore_placeholders(first_name),
        'last_name': restore_placeholders(last_name),
        'phone': thai_to_ascii(phone),
        'line_id': thai_to_ascii(line_id),
        'facebook': thai_to_ascii(facebook),
        'academic_year': thai_to_ascii(year),
        'status': restore_placeholders(status),
        'apply_date': thai_to_ascii(date_apply),
        'left_cols': [restore_placeholders(v) for v in left],
    }


def main():
    with open(FILEPATH, 'rb') as f:
        raw = f.read()

    # Real record separators are CRLF (0x0d 0x0a).
    # Thai ช=0x0a and ญ=0x0d appear mid-field but NEVER together as 0x0d+0x0a.
    raw_lines = raw.split(b'\x0d\x0a')
    rows = []
    for raw_line in raw_lines:
        if not raw_line:
            continue
        # Decode each raw line independently — Thai ช/ญ within are preserved
        decoded = ''.join(decode_byte(b) for b in raw_line)
        try:
            rows.append(next(csv.reader([decoded])))
        except Exception:
            rows.append([decoded])
    print(f"Total CSV rows: {len(rows)}")
    # Collect personal rows
    personal_rows = []
    for i, row in enumerate(rows):
        ok, sidx = is_personal_row(row)
        if ok:
            p = extract_personal(row, sidx)
            p['row_idx'] = i
            personal_rows.append(p)

    print(f"Personal rows found: {len(personal_rows)}")

    # Show samples
    print("\nSample personal rows (5):")
    for p in personal_rows[:5]:
        print(f"\n  Row {p['row_idx']}:")
        print(f"    prefix={p['prefix']}  first={p['first_name']}  last={p['last_name']}")
        print(f"    phone={p['phone']}  LINE={p['line_id']}")
        print(f"    year={p['academic_year']}  status={p['status']}")
        print(f"    left_cols={p['left_cols'][:5]}")

    # Now find the academic info for each personal row
    # The academic row comes BEFORE the personal row
    # Academic rows contain: faculty, level, program, rob, and geo info
    # We look backwards from each personal row for the nearest row that has:
    # - col[1] starts with 'คณะ' or contains faculty keyword

    def find_academic(row_idx):
        """Search backwards from row_idx for the academic info."""
        # Try rows from row_idx-1 going back up to 20 rows
        for j in range(row_idx - 1, max(0, row_idx - 25), -1):
            r = rows[j]
            if not r:
                continue
            # Academic row: one of the cols starts with 'คณะ'
            for k, v in enumerate(r):
                if v.strip().startswith('คณะ') and len(v.strip()) > 3:
                    return r, j, k
        return None, -1, -1

    students = []
    for p in personal_rows:
        acad_row, acad_idx, faculty_col = find_academic(p['row_idx'])
        if acad_row is None:
            continue
        
        r = [restore_placeholders(v.strip()) for v in acad_row]

        # Extract from academic row
        faculty      = r[faculty_col]
        level        = r[faculty_col + 1] if faculty_col + 1 < len(r) else ''
        program      = r[faculty_col + 2] if faculty_col + 2 < len(r) else ''
        program_abbr = r[faculty_col + 3] if faculty_col + 3 < len(r) else ''

        # Geo info: look in left_cols of personal row
        left = p['left_cols']
        province_school = left[-1] if len(left) >= 1 else ''
        school          = left[-2] if len(left) >= 2 else ''
        subdistrict     = left[-3] if len(left) >= 3 else ''
        district        = left[-4] if len(left) >= 4 else ''
        province_origin = left[-5] if len(left) >= 5 else ''
        
        student = {
            'faculty':          faculty,
            'level':            level,
            'program':          program,
            'program_abbr':     program_abbr,
            'province_origin':  province_origin,
            'district':         district,
            'subdistrict':      subdistrict,
            'school':           school,
            'province_school':  province_school,
            'prefix':           p['prefix'],
            'first_name':       p['first_name'],
            'last_name':        p['last_name'],
            'phone':            p['phone'],
            'line_id':          p['line_id'],
            'facebook':         p['facebook'],
            'academic_year':    p['academic_year'],
            'status':           p['status'],
            'apply_date':       p['apply_date'],
        }
        students.append(student)

    print(f"\nStudents with academic info: {len(students)}")

    print("\nSample complete records (5):")
    for i, s in enumerate(students[:5]):
        print(f"\n  [{i+1}] {s['prefix']} {s['first_name']} {s['last_name']}")
        print(f"       คณะ: {s['faculty'][:50]}")
        print(f"       ระดับ: {s['level']}  หลักสูตร: {s['program'][:30]}")
        print(f"       จังหวัด: {s['province_origin']}  อำเภอ: {s['district']}")
        print(f"       โรงเรียน: {s['school'][:30]}  จว.โรงเรียน: {s['province_school']}")
        print(f"       เบอร์: {s['phone']}  LINE: {s['line_id'][:20]}")
        print(f"       ปีการศึกษา: {s['academic_year']}  สถานะ: {s['status']}")

    # ── Connect and insert ────────────────────────────────────────────
    print("\nConnecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS applicants CASCADE")
    cur.execute("""
        CREATE TABLE applicants (
            id               SERIAL PRIMARY KEY,
            faculty          TEXT,        -- คณะ
            level            TEXT,        -- ระดับ (ปวส/ปริญญาตรี)
            program          TEXT,        -- หลักสูตร
            program_abbr     TEXT,        -- รหัสหลักสูตร
            province_origin  TEXT,        -- จังหวัดภูมิกำเนิด
            district         TEXT,        -- อำเภอ
            subdistrict      TEXT,        -- ตำบล
            school           TEXT,        -- โรงเรียน
            province_school  TEXT,        -- จังหวัดที่โรงเรียนตั้งอยู่
            prefix           TEXT,        -- คำนำหน้า
            first_name       TEXT,        -- ชื่อ
            last_name        TEXT,        -- นามสกุล
            phone            TEXT,        -- เบอร์โทร
            line_id          TEXT,        -- LINE ID
            facebook         TEXT,        -- Facebook
            academic_year    TEXT,        -- ปีการศึกษา
            status           TEXT,        -- สถานะ (ยืนยัน/รอตรวจสอบ)
            apply_date       TEXT,        -- วันที่สมัคร
            created_at       TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX idx_app_faculty   ON applicants(faculty)")
    cur.execute("CREATE INDEX idx_app_level     ON applicants(level)")
    cur.execute("CREATE INDEX idx_app_province  ON applicants(province_origin)")
    cur.execute("CREATE INDEX idx_app_year      ON applicants(academic_year)")
    cur.execute("CREATE INDEX idx_app_status    ON applicants(status)")
    cur.execute("CREATE INDEX idx_app_school    ON applicants(school)")
    conn.commit()
    print("✓ Table 'applicants' created with indexes")

    inserted = errors = 0
    for s in students:
        try:
            cur.execute("""
                INSERT INTO applicants (
                    faculty, level, program, program_abbr,
                    province_origin, district, subdistrict, school, province_school,
                    prefix, first_name, last_name, phone, line_id, facebook,
                    academic_year, status, apply_date
                ) VALUES (
                    %(faculty)s, %(level)s, %(program)s, %(program_abbr)s,
                    %(province_origin)s, %(district)s, %(subdistrict)s, %(school)s, %(province_school)s,
                    %(prefix)s, %(first_name)s, %(last_name)s, %(phone)s, %(line_id)s, %(facebook)s,
                    %(academic_year)s, %(status)s, %(apply_date)s
                )
            """, s)
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ⚠ {e}")

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM applicants")
    total = cur.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"✓ Import complete: {inserted} inserted, {errors} errors, {total} in DB")
    print(f"{'='*60}")

    print("\n📊 Faculty distribution:")
    cur.execute("SELECT faculty, COUNT(*) cnt FROM applicants GROUP BY faculty ORDER BY cnt DESC LIMIT 8")
    for r in cur.fetchall():
        print(f"  {str(r[0])[:50]:50s}: {r[1]}")

    print("\n📊 Level distribution:")
    cur.execute("SELECT level, COUNT(*) cnt FROM applicants GROUP BY level ORDER BY cnt DESC")
    for r in cur.fetchall():
        print(f"  {str(r[0])[:40]:40s}: {r[1]}")

    print("\n📊 Status distribution:")
    cur.execute("SELECT status, COUNT(*) cnt FROM applicants GROUP BY status ORDER BY cnt DESC")
    for r in cur.fetchall():
        print(f"  {str(r[0])[:40]:40s}: {r[1]}")

    print("\n📊 Top provinces:")
    cur.execute("""
        SELECT province_origin, COUNT(*) cnt FROM applicants
        WHERE province_origin != '' AND length(province_origin) < 25
        GROUP BY province_origin ORDER BY cnt DESC LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {str(r[0])[:30]:30s}: {r[1]}")

    conn.close()


if __name__ == '__main__':
    main()
