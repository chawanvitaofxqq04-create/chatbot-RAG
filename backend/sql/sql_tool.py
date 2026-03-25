# เพิ่ม import ไว้ด้านบนสุดของไฟล์ sql_tool.py
import json
import urllib.parse
from langchain_core.tools import tool

@tool
def create_bar_chart(data_points: str, title: str = "Graph"):
    """
    ใช้สำหรับสร้างกราฟแท่งเมื่อผู้ใช้ต้องการเปรียบเทียบข้อมูลเชิงปริมาณจาก Database
    data_points: JSON string เช่น '[{"label": "RTX 4090", "value": 3}, ...]'
    """
    try:
        data = json.loads(data_points)
        labels = [str(item['label']) for item in data]
        values = [float(item['value']) for item in data]

        chart_config = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": title,
                    "data": values,
                    "backgroundColor": "rgba(54, 162, 235, 0.6)",
                    "borderColor": "rgb(54, 162, 235)",
                    "borderWidth": 1
                }]
            }
        }

        encoded_config = urllib.parse.quote(json.dumps(chart_config))
        chart_url = f"https://quickchart.io/chart?c={encoded_config}&width=500&height=300"
        
        return f"\n\n![{title}]({chart_url})\n\n"
    except Exception as e:
        return f"Error creating chart: {str(e)}"