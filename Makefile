up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	ruff check .

test:
	pytest -q

seed-rdc:
	python -m scripts.seed_rdc

worker:
	celery -A app.celery_app.celery_app worker --loglevel=info

beat:
	celery -A app.celery_app.celery_app beat --loglevel=info
