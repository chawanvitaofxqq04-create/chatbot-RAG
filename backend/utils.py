import time
from functools import wraps

def resilient_retry(max_attempts=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    # พยายามรัน Tool ปกติ (SQL หรือ RAG)
                    return func(*args, **kwargs) 
                except Exception as e:
                    # พิมพ์บอกใน Terminal ให้บอสรู้ว่ามันกำลัง "ตื๊อ" อยู่
                    print(f"⚠️ [Retry {attempt+1}/{max_attempts}] เกิดข้อผิดพลาด: {e}")
                    
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                    else:
                        # 💥 จุดสำคัญ: ห้ามส่ง String ให้ส่งลิสต์ว่าง [] กลับไป
                        # เพื่อให้ Agent รู้ว่า SQL หาไม่เจอ แล้วมันจะวิ่งไปหาใน PDF (RAG) เองครับ
                        print("❌ ตื๊อครบ 3 รอบแล้วยังพัง ส่งค่าว่างคืนให้ AI ประมวลผลต่อ")
                        return [] 
        return wrapper
    return decorator