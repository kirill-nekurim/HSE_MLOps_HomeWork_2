# Model Registry (MVP)

REST-сервис для регистрации ML-моделей (метаданные + версии) и хранения ссылок на артефакты на диске (ФС) или по URI.

## Запуск

Установка зависимостей:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Настройки:

```bash
cp .env.example .env
```

Старт:

```bash
uvicorn app.main:app --reload
```

Откройте Swagger UI: `http://127.0.0.1:8000/docs`

## Примеры API

Создать модель:

```bash
curl -X POST http://127.0.0.1:8000/models \
  -H 'content-type: application/json' \
  -d '{"name":"my_model","description":"baseline"}'
```

Зарегистрировать версию:

```bash
curl -X POST http://127.0.0.1:8000/models/my_model/versions \
  -H 'content-type: application/json' \
  -d '{
    "version":"1",
    "artifact_path":"mlds_1/my_model_v1",
    "stage":"development",
    "metadata":{"framework":"pytorch","metric":{"auc":0.91}},
    "tags":{"team":"mlds_1","task":"ranker"}
  }'
```

Найти модели:

```bash
curl 'http://127.0.0.1:8000/models?name=my_model&stage=development&tag=team:mlds_1'
```

Получить артефакт:

```bash
curl http://127.0.0.1:8000/models/my_model/versions/1/artifact
```

## Тесты

```bash
pytest -q
```

