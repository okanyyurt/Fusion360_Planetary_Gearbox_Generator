# -*- coding: utf-8 -*-
"""
AI asistanı testleri — gerçek Gemini yerine sahte sunucu (ağ ve API anahtarı gerekmez):
  * araç çağrısı -> gereksinim çözücü -> öneri kartı -> metin yanıtı
  * modelin düşünce imzası (thoughtSignature) sonraki istekte aynen geri gönderiliyor
  * functionResponse adı/id'si çağrıyla eşleşiyor
  * 429/503 geri çekilmeli yeniden deneme, kota yoksa sıradaki modele geçiş
  * API anahtarı ayar dosyasında şifreli; arayüze yalnızca maskeli hali dönüyor
Çalıştırma:  py -3.14 tests/test_ai.py
"""
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["PLANETARY_GEARBOX_HOME"] = tempfile.mkdtemp(prefix="pgb_ai_ş_")

from standalone import paths                       # noqa: E402
from standalone.ai import gemini                   # noqa: E402
from standalone.api import Api                     # noqa: E402

FAKE_KEY = "test-key-" + "x" * 30
MODELS = {"models": [
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-pro-preview", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
    {"name": "models/gemini-3.1-pro-preview-tts", "supportedGenerationMethods": ["generateContent"]},
]}


class FakeGemini:
    """Senaryolu sahte sunucu: tur sayısına göre araç çağrısı veya metin döndürür."""

    def __init__(self, fail_first=None, quota_models=()):
        self.calls = []
        self.fail_first = fail_first            # ilk POST'ta fırlatılacak hata
        self.quota_models = set(quota_models)

    def __call__(self, method, url, key, body):
        assert key == FAKE_KEY, "anahtar yalnızca istek başlığında gitmeli"
        if method == "GET":
            return MODELS
        self.calls.append((url, json.loads(json.dumps(body))))
        model = url.split("/models/")[1].split(":")[0]
        if model in self.quota_models:
            raise gemini.GeminiError("Quota exceeded ... limit: 0", 429, quota=True)
        if self.fail_first is not None:
            err, self.fail_first = self.fail_first, None
            raise err
        contents = body["contents"]
        if not body.get("tools"):                          # ai_test
            return {"candidates": [{"content": {"role": "model", "parts": [{"text": "OK"}]}}]}
        responses = [p["functionResponse"] for c in contents for p in c.get("parts", []) if "functionResponse" in p]
        if not responses:
            return {"candidates": [{"content": {"role": "model", "parts": [
                {"functionCall": {"id": "call-1", "name": "solve_requirements",
                                  "args": {"motor_preset": "NEMA17", "ratio": 25, "max_od": 120}},
                 "thoughtSignature": "SIG-ONE"}]}, "finishReason": "STOP"}]}
        last = responses[-1]
        if last["name"] == "solve_requirements":
            # önceki model içeriği (imza dahil) aynen geri gelmiş olmalı
            sigs = [p.get("thoughtSignature") for c in contents if c.get("role") == "model" for p in c["parts"]]
            assert "SIG-ONE" in sigs, "thoughtSignature geri gönderilmedi"
            assert last.get("id") == "call-1", "functionResponse id eşleşmiyor"
            sols = last["response"]["solutions"]
            assert sols and sols[0]["id"].startswith("R1."), sols
            return {"candidates": [{"content": {"role": "model", "parts": [
                {"functionCall": {"name": "propose_design",
                                  "args": {"solution_id": sols[0]["id"], "title": "Önerilen tasarım",
                                           "summary": "En küçük uygun gövde."}},
                 "thoughtSignature": "SIG-TWO"}]}}]}
        return {"candidates": [{"content": {"role": "model", "parts": [
            {"text": "düşünce", "thought": True}, {"text": "Önerim hazır: 25:1, PLA."}]}}]}


def _wait(api, job, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = api.ai_poll(job)
        if st["status"] != "running":
            return st
        time.sleep(0.1)
    raise AssertionError("AI işi zaman aşımı")


def test_key_storage():
    api = Api()
    r = api.ai_settings_set({"api_key": FAKE_KEY})
    assert r["success"] and r["has_key"] and r["key_hint"] == "••••" + FAKE_KEY[-4:]
    raw = open(paths.settings_path(), encoding="utf-8").read()
    assert FAKE_KEY not in raw, "anahtar düz metin saklanmış"
    if os.name == "nt":
        assert r["protected"], "Windows'ta DPAPI kullanılmalı"
    assert FAKE_KEY not in json.dumps(api.ai_settings_get()), "anahtar arayüze dönmemeli"
    assert Api()._ai_key() == FAKE_KEY, "yeni oturum anahtarı çözebilmeli"
    bad = api.ai_settings_set({"api_key": "kısa"})
    assert not bad["success"]
    print("  [OK] anahtar DPAPI ile şifreli, arayüze yalnızca ••••" + FAKE_KEY[-4:])


def test_models_ranking():
    ranked = gemini.rank_models([{"id": m["name"].split("/")[1]} for m in MODELS["models"]])
    assert ranked[0] == "gemini-3.1-pro-preview", ranked
    assert all("tts" not in m and "embedding" not in m for m in ranked)
    assert gemini.rank_models([{"id": "gemini-4-argon"}, {"id": "gemini-3.8-flash"}, {"id": "gemini-3.1-pro"}])[0] == \
        "gemini-4-argon"
    print("  [OK] model sıralama:", ranked)


def test_agent_flow():
    api = Api()
    api._ai_transport = FakeGemini()
    api.ai_settings_set({"api_key": FAKE_KEY, "model": "auto"})
    lm = api.ai_list_models()
    assert lm["success"] and lm["auto"] == "gemini-3.1-pro-preview"
    form = {"lang": "tr", "bed_x": 220, "bed_y": 220, "bed_z": 250}
    r = api.ai_send("NEMA17 ile 25:1 redüktör, en fazla 120 mm çap", form)
    assert r["success"], r
    st = _wait(api, r["job"])
    assert st["status"] == "done", st
    assert st["reply"] == "Önerim hazır: 25:1, PLA.", st["reply"]       # düşünce parçası yanıta karışmamalı
    assert len(st["proposals"]) == 1
    card = st["proposals"][0]
    assert card["payload"]["stages"] and card["payload"]["bed_x"] == 220, "yazıcı tablası formdan gelmeli"
    assert card["metrics"]["outer_diameter"] <= 120
    kinds = [s["kind"] for s in st["steps"]]
    assert "tool" in kinds and "result" in kinds, st["steps"]
    # ikinci mesaj: geçmiş korunur (çok turlu konuşma)
    n_hist = len(api._ai().history)
    r2 = api.ai_send("teşekkürler", form)
    _wait(api, r2["job"])
    assert len(api._ai().history) > n_hist
    assert api.ai_reset()["success"] and not api._ai().history
    print(f"  [OK] ajan akışı: araç→çözücü→öneri ({card['title']}: Ø{card['metrics']['outer_diameter']} mm), "
          f"{len(st['steps'])} adım")


def test_retry_and_fallback():
    gemini.time.sleep = lambda s: None                 # geri çekilme beklemesini atla
    api = Api()
    api.ai_settings_set({"api_key": FAKE_KEY, "model": "auto"})
    api._ai_transport = FakeGemini(fail_first=gemini.GeminiError("busy", 503, retry=True),
                                   quota_models={"gemini-3.1-pro-preview"})
    api._ai_model_cache = None
    r = api.ai_send("NEMA17 25:1", {"lang": "tr"})
    st = _wait(api, r["job"])
    assert st["status"] == "done", st
    assert st["model"] != "gemini-3.1-pro-preview", st["model"]
    assert any("deneniyor" in s["text"] for s in st["steps"]), st["steps"]
    t = api.ai_test()
    assert t["success"] and t["reply"] == "OK", t
    print(f"  [OK] 503 yeniden deneme + kota yokken {st['model']} modeline geçiş; bağlantı testi")


def test_no_key():
    os.environ["PLANETARY_GEARBOX_HOME"] = tempfile.mkdtemp(prefix="pgb_ai2_")
    api = Api()
    r = api.ai_send("merhaba", {"lang": "tr"})
    st = _wait(api, r["job"])
    assert st["status"] == "error" and "anahtar" in st["error"], st
    print("  [OK] anahtar yokken anlaşılır hata")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("AI ASİSTAN TESTLERİ")
    test_key_storage()
    test_models_ranking()
    test_agent_flow()
    test_retry_and_fallback()
    test_no_key()
    print("TÜM AI TESTLERİ GEÇTİ")
