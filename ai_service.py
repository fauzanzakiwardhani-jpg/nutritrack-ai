import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)

def analyze_food_image(image, health_goal="Jaga Berat Badan"):
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
    Analisis foto makanan ini secara presisi untuk pengguna dengan target kesehatan: {health_goal}.

    Kembalikan HANYA format JSON murni tanpa teks/markdown tambahan dengan struktur berikut:
    {{
      "meal_name": "Nama Sesi Makan (misal: Nasi Ayam Goreng & Tempe)",
      "items": [
        {{
          "item_name": "Nama Makanan/Item",
          "estimated_weight_g": 150,
          "calories": 250,
          "protein_g": 12.0,
          "carbs_g": 30.0,
          "fat_g": 8.0
        }}
      ],
      "total_calories": 250,
      "total_protein_g": 12.0,
      "total_carbs_g": 30.0,
      "total_fat_g": 8.0,
      "ai_feedback": "Saran gizi singkat 1-2 kalimat mengenai kecukupan nutrisi hidangan ini."
    }}
    """

    response = model.generate_content([image, prompt])
    clean_json = response.text.replace('json', '').replace('', '').strip()
    return json.loads(clean_json)
