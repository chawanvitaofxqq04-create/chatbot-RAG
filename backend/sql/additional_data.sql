-- Additional Sample Data for RAG Database
-- เพิ่มข้อมูลตัวอย่างเพิ่มเติมสำหรับการทดสอบ

-- เพิ่มลูกค้าเพิ่มเติม (11-20)
INSERT INTO customers (name, email, region) VALUES
('สมชาย ใจดี', 'somchai@email.com', 'กรุงเทพ'),
('สมหญิง รักสวย', 'somying@email.com', 'เชียงใหม่'),
('ประยุทธ์ มั่นคง', 'prayut@email.com', 'ภูเก็ต'),
('ยิ่งลักษณ์ สุขใจ', 'yinglak@email.com', 'กรุงเทพ'),
('อภิสิทธิ์ เก่งมาก', 'apisit@email.com', 'กรุงเทพ'),
('ทักษิณ รวยมาก', 'thaksin@email.com', 'เชียงใหม่'),
('พิมพ์ใจ สวยงาม', 'pimjai@email.com', 'ขอนแก่น'),
('วิชัย ขยัน', 'wichai@email.com', 'นครราชสีมา'),
('สุดา เรียบร้อย', 'suda@email.com', 'อุบลราชธานี'),
('นิพนธ์ ฉลาด', 'nipon@email.com', 'กรุงเทพ');

-- เพิ่มสินค้าเพิ่มเติม (11-25)
INSERT INTO products (name, category, price, stock) VALUES
('iPhone 15 Pro', 'มือถือ', 45900.00, 15),
('Samsung Galaxy S24', 'มือถือ', 35900.00, 20),
('MacBook Air M3', 'คอมพิวเตอร์', 42900.00, 8),
('iPad Pro 12.9', 'แท็บเล็ต', 38900.00, 12),
('AirPods Pro 2', 'หูฟัง', 8900.00, 50),
('Apple Watch Ultra 2', 'สมาร์ทวอทช์', 29900.00, 10),
('Sony WH-1000XM5', 'หูฟัง', 12900.00, 25),
('Dell XPS 15', 'คอมพิวเตอร์', 55900.00, 6),
('LG OLED TV 65"', 'ทีวี', 89900.00, 4),
('Dyson V15', 'เครื่องใช้ไฟฟ้า', 24900.00, 15),
('Xiaomi Robot Vacuum', 'เครื่องใช้ไฟฟ้า', 8900.00, 20),
('Nintendo Switch OLED', 'เกม', 12900.00, 18),
('PlayStation 5', 'เกม', 18900.00, 5),
('GoPro Hero 12', 'กล้อง', 16900.00, 12),
('Canon EOS R6', 'กล้อง', 89900.00, 3);

-- เพิ่มคำสั่งซื้อเพิ่มเติม (16-30)
INSERT INTO orders (customer_id, order_date, total_amount) VALUES
(11, '2025-01-15', 45900.00),
(12, '2025-01-16', 35900.00),
(13, '2025-01-17', 42900.00),
(14, '2025-01-18', 47800.00),
(15, '2025-01-19', 29900.00),
(16, '2025-01-20', 12900.00),
(17, '2025-01-21', 55900.00),
(18, '2025-01-22', 89900.00),
(19, '2025-01-23', 24900.00),
(20, '2025-01-24', 8900.00),
(11, '2025-01-25', 12900.00),
(12, '2025-01-26', 18900.00),
(13, '2025-01-27', 16900.00),
(14, '2025-01-28', 89900.00),
(15, '2025-01-29', 98800.00);

-- เพิ่มรายการสินค้าในคำสั่งซื้อ
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
-- Order 16
(16, 11, 1, 45900.00),
-- Order 17
(17, 12, 1, 35900.00),
-- Order 18
(18, 13, 1, 42900.00),
-- Order 19
(19, 14, 1, 38900.00),
(19, 15, 1, 8900.00),
-- Order 20
(20, 16, 1, 29900.00),
-- Order 21
(21, 17, 1, 12900.00),
-- Order 22
(22, 18, 1, 55900.00),
-- Order 23
(23, 19, 1, 89900.00),
-- Order 24
(24, 20, 1, 24900.00),
-- Order 25
(25, 21, 1, 8900.00),
-- Order 26
(26, 22, 1, 12900.00),
-- Order 27
(27, 23, 1, 18900.00),
-- Order 28
(28, 24, 1, 16900.00),
-- Order 29
(29, 25, 1, 89900.00),
-- Order 30 (multiple items)
(30, 11, 1, 45900.00),
(30, 15, 2, 8900.00),
(30, 13, 1, 42900.00);

-- สร้างตารางสำหรับข้อมูลนักศึกษา (ตัวอย่าง)
CREATE TABLE IF NOT EXISTS students (
    student_id SERIAL PRIMARY KEY,
    student_code VARCHAR(20) UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone VARCHAR(20),
    faculty TEXT,
    major TEXT,
    year INTEGER,
    gpa NUMERIC(3,2),
    enrolled_date DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'active'
);

-- เพิ่มข้อมูลนักศึกษาตัวอย่าง
INSERT INTO students (student_code, first_name, last_name, email, phone, faculty, major, year, gpa) VALUES
('6501001', 'สมชาย', 'ใจดี', 's6501001@ksu.ac.th', '081-234-5678', 'วิทยาศาสตร์', 'วิทยาการคอมพิวเตอร์', 3, 3.45),
('6501002', 'สมหญิง', 'รักสวย', 's6501002@ksu.ac.th', '082-345-6789', 'วิศวกรรมศาสตร์', 'วิศวกรรมซอฟต์แวร์', 2, 3.67),
('6501003', 'ประยุทธ์', 'มั่นคง', 's6501003@ksu.ac.th', '083-456-7890', 'บริหารธุรกิจ', 'การจัดการ', 4, 3.21),
('6501004', 'ยิ่งลักษณ์', 'สุขใจ', 's6501004@ksu.ac.th', '084-567-8901', 'ครุศาสตร์', 'การศึกษาปฐมวัย', 1, 3.89),
('6501005', 'อภิสิทธิ์', 'เก่งมาก', 's6501005@ksu.ac.th', '085-678-9012', 'วิทยาศาสตร์', 'วิทยาการข้อมูล', 3, 3.92),
('6501006', 'ทักษิณ', 'รวยมาก', 's6501006@ksu.ac.th', '086-789-0123', 'บริหารธุรกิจ', 'การเงิน', 2, 3.56),
('6501007', 'พิมพ์ใจ', 'สวยงาม', 's6501007@ksu.ac.th', '087-890-1234', 'มนุษยศาสตร์', 'ภาษาอังกฤษ', 4, 3.78),
('6501008', 'วิชัย', 'ขยัน', 's6501008@ksu.ac.th', '088-901-2345', 'วิศวกรรมศาสตร์', 'วิศวกรรมไฟฟ้า', 3, 3.34),
('6501009', 'สุดา', 'เรียบร้อย', 's6501009@ksu.ac.th', '089-012-3456', 'พยาบาลศาสตร์', 'พยาบาลศาสตร์', 1, 3.65),
('6501010', 'นิพนธ์', 'ฉลาด', 's6501010@ksu.ac.th', '090-123-4567', 'วิทยาศาสตร์', 'ฟิสิกส์', 2, 3.87);

-- สร้างตารางหลักสูตร
CREATE TABLE IF NOT EXISTS courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) UNIQUE NOT NULL,
    course_name TEXT NOT NULL,
    credits INTEGER NOT NULL,
    faculty TEXT,
    description TEXT
);

-- เพิ่มข้อมูลหลักสูตร
INSERT INTO courses (course_code, course_name, credits, faculty, description) VALUES
('CS101', 'Introduction to Computer Science', 3, 'วิทยาศาสตร์', 'พื้นฐานวิทยาการคอมพิวเตอร์'),
('CS201', 'Data Structures and Algorithms', 3, 'วิทยาศาสตร์', 'โครงสร้างข้อมูลและอัลกอริทึม'),
('CS301', 'Database Systems', 3, 'วิทยาศาสตร์', 'ระบบฐานข้อมูล'),
('CS401', 'Artificial Intelligence', 3, 'วิทยาศาสตร์', 'ปัญญาประดิษฐ์'),
('ENG101', 'Engineering Drawing', 3, 'วิศวกรรมศาสตร์', 'การเขียนแบบวิศวกรรม'),
('BUS101', 'Principles of Management', 3, 'บริหารธุรกิจ', 'หลักการจัดการ'),
('EDU101', 'Educational Psychology', 3, 'ครุศาสตร์', 'จิตวิทยาการศึกษา'),
('NUR101', 'Fundamentals of Nursing', 3, 'พยาบาลศาสตร์', 'พื้นฐานการพยาบาล'),
('PHY101', 'General Physics', 3, 'วิทยาศาสตร์', 'ฟิสิกส์ทั่วไป'),
('ENG201', 'English for Communication', 3, 'มนุษยศาสตร์', 'ภาษาอังกฤษเพื่อการสื่อสาร');

-- สร้างตารางการลงทะเบียน
CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(student_id),
    course_id INTEGER REFERENCES courses(course_id),
    semester VARCHAR(10),
    year INTEGER,
    grade VARCHAR(2),
    enrolled_date DATE DEFAULT CURRENT_DATE
);

-- เพิ่มข้อมูลการลงทะเบียน
INSERT INTO enrollments (student_id, course_id, semester, year, grade) VALUES
(1, 1, '1/2568', 2568, 'A'),
(1, 2, '1/2568', 2568, 'B+'),
(1, 3, '2/2568', 2568, 'A'),
(2, 1, '1/2568', 2568, 'A'),
(2, 5, '1/2568', 2568, 'B'),
(3, 6, '1/2568', 2568, 'B+'),
(4, 7, '1/2568', 2568, 'A'),
(5, 1, '1/2568', 2568, 'A'),
(5, 2, '1/2568', 2568, 'A'),
(5, 4, '2/2568', 2568, 'A');

-- สร้าง View สำหรับสรุปยอดขาย
CREATE OR REPLACE VIEW sales_summary AS
SELECT 
    DATE_TRUNC('month', o.order_date) as month,
    COUNT(DISTINCT o.order_id) as total_orders,
    COUNT(DISTINCT o.customer_id) as total_customers,
    SUM(o.total_amount) as total_revenue,
    AVG(o.total_amount) as avg_order_value
FROM orders o
GROUP BY DATE_TRUNC('month', o.order_date)
ORDER BY month DESC;

-- สร้าง View สำหรับสินค้าขายดี
CREATE OR REPLACE VIEW top_products AS
SELECT 
    p.product_id,
    p.name,
    p.category,
    COUNT(oi.item_id) as times_ordered,
    SUM(oi.quantity) as total_quantity,
    SUM(oi.line_total) as total_revenue
FROM products p
LEFT JOIN order_items oi ON p.product_id = oi.product_id
GROUP BY p.product_id, p.name, p.category
ORDER BY total_revenue DESC;

-- สร้าง View สำหรับข้อมูลนักศึกษา
CREATE OR REPLACE VIEW student_summary AS
SELECT 
    faculty,
    major,
    year,
    COUNT(*) as student_count,
    AVG(gpa) as avg_gpa,
    MAX(gpa) as max_gpa,
    MIN(gpa) as min_gpa
FROM students
WHERE status = 'active'
GROUP BY faculty, major, year
ORDER BY faculty, major, year;

-- แสดงสถิติข้อมูล
SELECT 'customers' as table_name, COUNT(*) as row_count FROM customers
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL
SELECT 'students', COUNT(*) FROM students
UNION ALL
SELECT 'courses', COUNT(*) FROM courses
UNION ALL
SELECT 'enrollments', COUNT(*) FROM enrollments;
