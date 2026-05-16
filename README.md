# L2J Play Fun Launcher

Автоматична збірка Windows EXE для лаунчера Lineage II сервера L2J Play Fun.

## 🚀 Як це працює

1. Кожен push в `main` — GitHub Actions автоматично збирає `.exe`
2. Реліз створюється автоматично з тегом версії
3. EXE доступний у розділі [Releases](../../releases)

## 📦 Файли

| Файл | Призначення |
|------|-------------|
| `launcher/L2JPlayFun-Launcher.py` | Ісходний код лаунчера |
| `launcher/launcher.ico` | Іконка програми |
| `launcher/logo_128.png` | Логотип в GUI |
| `launcher/launcher_api.php` | API для серверного маніфесту |

## 🛠️ Збірка вручну (якщо потрібно)

```bash
cd launcher
pip install pyinstaller
pyinstaller --onefile --windowed --icon=launcher.ico L2JPlayFun-Launcher.py
```

## 📥 Скачати готовий лаунчер

Перейдіть у [Releases](../../releases/latest) та скачайте `L2J-PlayFun-Launcher.exe`
