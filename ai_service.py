"""
ai_service.py — semua pemanggilan Gemini (SDK baru `google-genai`) untuk NutriTrack AI.

Fitur:
- Timeout berlapis: timeout HTTP di client + batas `future.result(timeout=...)`
  sehingga UI Streamlit tidak pernah hanging tanpa batas.
- Schema Pydantic ringkas untuk output JSON terstruktur.
- Fallback otomatis jika versi SDK menolak `generation_config`.
"""
import base64
import concurrent.futures
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Ganti di sini jika Google merilis model lebih baru / model ini dideprecate.
GEMINI_MODEL = "gemini-3.6-flash"

TEXT_TIMEOUT_S = 45      # analisis teks — dinaikkan dari 15s: gemini-3.6-flash (thinking) sering >15s
RECIPE_TIMEOUT_S = 45    # rekomendasi resep (3 resep, output lebih panjang)
CHAT_TIMEOUT_S = 35      # asisten Nutri
IMAGE_TIMEOUT_S = 60     # analisis foto (upload gambar + thinking = paling lama)

TEXT_MAX_TOKENS = 2000   # naik dari 800 — thinking tokens bisa memakan ratusan token sebelum JSON mulai ditulis
RECIPE_MAX_TOKENS = 3000
CHAT_MAX_TOKENS = 1500
IMAGE_MAX_TOKENS = 3000


class AITimeoutError(Exception):
    """AI tidak merespons dalam batas waktu yang ditentukan."""


class AINotConfiguredError(Exception):
    """GEMINI_API_KEY belum diisi."""


def _make_client(timeout_s: int):
    if not API_KEY:
        return None
    # http_options.timeout memakai satuan milidetik
    return genai.Client(api_key=API_KEY, http_options=types.HttpOptions(timeout=timeout_s * 1000))


_clients = {
    "text": _make_client(TEXT_TIMEOUT_S),
    "recipe": _make_client(RECIPE_TIMEOUT_S),
    "chat": _make_client(CHAT_TIMEOUT_S),
    "image": _make_client(IMAGE_TIMEOUT_S),
}


def is_configured() -> bool:
    return bool(API_KEY)


# ----------------------------------------------------
# SCHEMA STRUCTURED OUTPUT
# ----------------------------------------------------
class NutritionAnalysis(BaseModel):
    """Schema lengkap untuk analisis FOTO (Computer Vision)."""
    food_name: str = Field(description="Nama makanan dalam Bahasa Indonesia")
    estimated_weight_min_g: float = Field(description="Batas bawah (min) estimasi berat porsi dalam gram, hasil kalibrasi visual 2D")
    estimated_weight_max_g: float = Field(description="Batas atas (max) estimasi berat porsi dalam gram, hasil kalibrasi visual 2D")
    estimated_weight_g: float = Field(description="Berat porsi terpilih (nilai tengah terkuat) dalam gram — dasar perhitungan kalori & makro")
    confidence_score: int = Field(description="Skor keyakinan estimasi 1-100, berdasarkan kejelasan foto, pencahayaan, dan keterlihatan komponen makanan", ge=1, le=100)
    calories: float = Field(description="Total kalori dalam kcal, dihitung dari estimated_weight_g")
    protein_g: float = Field(description="Kandungan protein dalam gram")
    carbs_g: float = Field(description="Kandungan karbohidrat dalam gram")
    fat_g: float = Field(description="Kandungan lemak dalam gram")
    ai_feedback: str = Field(description="Ulasan gizi dan saran singkat dalam Bahasa Indonesia")


class TextNutrition(BaseModel):
    """Schema RINGKAS untuk analisis TEKS — output pendek = respons lebih cepat."""
    food_name: str = Field(description="Nama makanan (total, Bahasa Indonesia), maks 60 karakter")
    estimated_weight_g: float = Field(description="Estimasi total berat porsi dalam gram")
    calories: float = Field(description="Total kalori (kcal)")
    protein_g: float = Field(description="Protein (gram)")
    carbs_g: float = Field(description="Karbohidrat (gram)")
    fat_g: float = Field(description="Lemak (gram)")
    ai_feedback: str = Field(description="Saran gizi singkat, maksimal 2 kalimat")


class RecipeIdea(BaseModel):
    name: str = Field(description="Nama resep/menu dalam Bahasa Indonesia")
    estimated_calories: float = Field(description="Estimasi kalori dalam kcal")
    protein_g: float = Field(description="Estimasi protein dalam gram")
    carbs_g: float = Field(description="Estimasi karbohidrat dalam gram")
    fat_g: float = Field(description="Estimasi lemak dalam gram")
    reason: str = Field(description="Alasan singkat (maks 1 kalimat) kenapa menu ini cocok")


class RecipeSuggestions(BaseModel):
    recipes: list[RecipeIdea] = Field(description="Daftar 3 ide resep/menu makanan sehat")


FOOD_VISION_SYSTEM_PROMPT = """
Kamu adalah pakar nutrisi AI dan spesialis Computer Vision khusus analisis makanan khas Indonesia dan internasional.

Tugas utama kamu adalah menganalisis foto makanan yang diunggah pengguna, mendeteksi semua komponen bahan, mengestimasi berat (gram) secara rasional, dan menghitung total kandungan makronutrisinya.

---

### TAHAPAN ANALISIS (CHAIN-OF-THOUGHT):
Lakukan penalaran secara berurutan sebelum menentukan hasil akhir:

1. DETEKSI VISUAL & PEMISAHAN ITEM:
   - Identifikasi setiap komponen makanan yang ada di dalam wadah/piring secara terpisah.
   - Amati tekstur permukaannya: Apakah mengilap/berminyak (gorengan/tumisan/balado) atau bersantan? Jika ya, tambahkan estimasi 5-10g lemak ekstra per porsi dari minyak/santan.

2. ANCHOR & KALIBRASI UKURAN 2D:
   - Gunakan piring, mangkuk, sendok/garpu, atau batas wadah di sekitar makanan sebagai referensi skala visual.
   - Pakai standar porsi lokal Indonesia sebagai acuan dasar:
     * 1 centong nasi putih standar (rata) = ~100g (130 kcal).
     * 1 centong nasi menumpuk/penuh = ~150-200g.
     * 1 potong ayam bagian dada/paha sedang = ~80-100g.
     * 1 sendok makan sambal/bumbu tumis = ~15-20g.

3. UNCERTAINTY & RANGE ESTIMATION:
   - Tentukan batas bawah (min) dan batas atas (max) estimasi gramasi berdasarkan perspektif foto 2D.
   - Tentukan nilai tengah terkuat (estimated_weight_g) berdasarkan analisis visual tersebut.
   - Berikan confidence_score (1-100) berdasarkan kejelasan foto, tingkat pencahayaan, dan keterlihatan komponen makanan.

4. PERHITUNGAN MAKRONUTRISI:
   - Hitung total kalori, protein, karbohidrat, dan lemak berdasarkan estimated_weight_g dan komposisi bahan yang terdeteksi (jumlahkan semua komponen jika makanan terdiri dari beberapa item).
   - Sertakan feedback gizi singkat dan relevan dengan target kesehatan pengguna.

---

### FORMAT OUTPUT (STRICT JSON ONLY):
Kembalikan respons HANYA dalam format JSON valid sesuai skema yang ditentukan, tanpa teks pembuka, penjelasan proses berpikir, atau penutup tambahan.
""".strip()


# ----------------------------------------------------
# HELPER INTERNAL
# ----------------------------------------------------
def _run_with_timeout(fn, timeout_s: int):
    """Jalankan fn di thread terpisah; lempar AITimeoutError jika melewati batas.

    Tidak memakai `with ThreadPoolExecutor` agar tidak ikut menunggu thread yang macet.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        raise AITimeoutError(f"AI tidak merespons dalam {timeout_s} detik.")
    finally:
        executor.shutdown(wait=False)


def _create(client, *, max_tokens: int, temperature: float = 0.2, thinking_level: str = "low", **kwargs):
    """Panggil client.interactions.create dengan generation_config; fallback bertahap jika SDK/parameter ditolak.

    thinking_level="low" penting untuk output JSON singkat: tanpa ini, model bisa
    menghabiskan sebagian besar (atau semua) token budget untuk bernalar sebelum
    sempat menulis JSON, sehingga responsnya terpotong (lihat ValidationError
    'EOF while parsing a value').
    """
    base_config = {"max_output_tokens": max_tokens, "temperature": temperature}
    try:
        return client.interactions.create(
            generation_config={**base_config, "thinking_level": thinking_level},
            **kwargs,
        )
    except TypeError:
        pass  # SDK versi ini tidak mengenal salah satu parameter -> coba tanpa thinking_level
    except Exception as e:
        # Beberapa versi API menolak thinking_level dengan error API (bukan TypeError)
        if "thinking_level" not in str(e).lower():
            raise
    try:
        return client.interactions.create(generation_config=base_config, **kwargs)
    except TypeError:
        # Versi SDK sangat lama: tidak kenal generation_config sama sekali
        return client.interactions.create(**kwargs)


def _json_format(model_cls):
    return {
        "type": "text",
        "mime_type": "application/json",
        "schema": model_cls.model_json_schema(),
    }


def _require(name: str):
    client = _clients.get(name)
    if client is None:
        raise AINotConfiguredError("GEMINI_API_KEY belum dikonfigurasi.")
    return client


# ----------------------------------------------------
# FUNGSI PUBLIK
# ----------------------------------------------------
def analyze_food_text(description: str, goal: str = "Jaga Berat Badan") -> TextNutrition:
    client = _require("text")
    prompt = (
        f'Deskripsi makanan: "{description}"\n'
        f"Target kesehatan pengguna: {goal}\n"
        "Estimasi total gizi (jumlahkan jika ada beberapa item) memakai porsi standar Indonesia. "
        "Jawab HANYA JSON sesuai skema, tanpa penjelasan tambahan. ai_feedback maksimal 2 kalimat."
    )

    def _call():
        return _create(
            client,
            max_tokens=TEXT_MAX_TOKENS,
            model=GEMINI_MODEL,
            input=prompt,
            response_format=_json_format(TextNutrition),
        )

    interaction = _run_with_timeout(_call, TEXT_TIMEOUT_S)
    return TextNutrition.model_validate_json(interaction.output_text)


def analyze_food_image(image_bytes: bytes, mime_type: str, goal: str = "Jaga Berat Badan") -> NutritionAnalysis:
    client = _require("image")
    user_prompt = (
        "Analisis foto makanan ini mengikuti tahapan chain-of-thought yang sudah ditentukan. "
        f"Target kesehatan pengguna saat ini: '{goal}'. "
        "Sertakan feedback gizi singkat yang relevan dengan target kesehatan tersebut."
    )

    def _call():
        return _create(
            client,
            max_tokens=IMAGE_MAX_TOKENS,
            model=GEMINI_MODEL,
            input=[
                {"type": "text", "text": FOOD_VISION_SYSTEM_PROMPT},
                {"type": "text", "text": user_prompt},
                {"type": "image", "data": base64.b64encode(image_bytes).decode("utf-8"), "mime_type": mime_type},
            ],
            response_format=_json_format(NutritionAnalysis),
        )

    interaction = _run_with_timeout(_call, IMAGE_TIMEOUT_S)
    return NutritionAnalysis.model_validate_json(interaction.output_text)


def suggest_recipes(sisa_kcal: float, sisa_p: float, sisa_c: float, sisa_f: float, goal: str) -> list[RecipeIdea]:
    client = _require("recipe")
    prompt = f"""
    Berikan 3 ide resep/menu makanan sehat khas Indonesia dalam Bahasa Indonesia,
    yang cocok dengan sisa kuota gizi pengguna hari ini:
    - Sisa kalori: {sisa_kcal:.0f} kcal
    - Sisa protein: {sisa_p:.0f} g
    - Sisa karbohidrat: {sisa_c:.0f} g
    - Sisa lemak: {sisa_f:.0f} g
    - Target kesehatan pengguna: {goal}

    Setiap resep harus muat dalam sisa kuota kalori tersebut (tidak melebihi).
    Alasan cukup 1 kalimat singkat. Jawab HANYA JSON sesuai skema.
    """

    def _call():
        return _create(
            client,
            max_tokens=RECIPE_MAX_TOKENS,
            temperature=0.6,
            model=GEMINI_MODEL,
            input=prompt,
            response_format=_json_format(RecipeSuggestions),
        )

    interaction = _run_with_timeout(_call, RECIPE_TIMEOUT_S)
    return RecipeSuggestions.model_validate_json(interaction.output_text).recipes


def chat_reply(prompt: str, previous_interaction_id: str | None = None):
    """Balasan asisten Nutri. Return (teks_jawaban, interaction_id)."""
    client = _require("chat")

    def _call():
        kwargs = dict(model=GEMINI_MODEL, input=prompt)
        if previous_interaction_id:
            kwargs["previous_interaction_id"] = previous_interaction_id
        return _create(client, max_tokens=CHAT_MAX_TOKENS, temperature=0.5, **kwargs)

    interaction = _run_with_timeout(_call, CHAT_TIMEOUT_S)
    return interaction.output_text, interaction.id
