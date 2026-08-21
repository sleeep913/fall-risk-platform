.PHONY: up down logs test test-api test-web

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api web

test: test-api test-web

test-api:
	docker compose --profile test run --rm api-test

test-web:
	docker compose --profile test run --rm web-test

