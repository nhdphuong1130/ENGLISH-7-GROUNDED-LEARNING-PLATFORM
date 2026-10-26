-include .env
COMPOSE := docker compose -f docker-compose.yml
SPEECH_COMPOSE := $(COMPOSE) -f compose.speech.yml
DB_NAME := english7
DB_USER := sa
DB_PASSWORD ?= $(if $(SQLSERVER_SA_PASSWORD),$(SQLSERVER_SA_PASSWORD),$(if $(MSSQL_SA_PASSWORD),$(MSSQL_SA_PASSWORD),English7DefaultPass!))
BACKUP_DIR := backups
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)
BACKUP_BAK := $(DB_NAME)_$(TIMESTAMP).bak
BACKUP_SQL := $(DB_NAME)_$(TIMESTAMP).sql
SQLCMD := /opt/mssql-tools18/bin/sqlcmd -S localhost -U $(DB_USER) -P "$(DB_PASSWORD)" -C

UV := $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
FLUTTER := $(shell which flutter 2>/dev/null || echo $(HOME)/.local/opt/flutter/bin/flutter)

.PHONY: help run up up-full down ps logs restart backup-db restore test test-launcher test-backend test-mobile test-pwa build-pwa analyze seed clean migrate seed-flashcards speech-setup speech-up speech-down test-speech test-learning-live

help:
	@echo "English 7 Grounded Learning Platform - Lệnh quản trị & phát triển"
	@echo ""
	@echo "Docker & Dịch vụ:"
	@echo "  make run           Khởi động backend, chờ sẵn sàng và mở app trên Android emulator"
	@echo "  make up            Khởi động backend cơ bản, không tải worker OCR"
	@echo "  make up-full       Khởi động cả worker OCR (lần đầu tải thư viện AI lớn)"
	@echo "  make down          Dừng cụm container"
	@echo "  make ps            Xem trạng thái các container"
	@echo "  make logs          Xem live logs của cụm container"
	@echo "  make restart       Khởi động lại toàn bộ dịch vụ"
	@echo "  make speech-setup  Cài runtime giọng nói và tải mô hình miễn phí (lần đầu)"
	@echo "  make speech-up     Bật runtime giọng nói riêng, không tải worker OCR"
	@echo "  make speech-down   Dừng riêng runtime giọng nói"
	@echo ""
	@echo "Cơ sở dữ liệu (Backups & Restore):"
	@echo "  make backup-db     Sao lưu toàn bộ SQL Server thành file .bak và .sql trong backups/"
	@echo "  make restore FILE=backups/<file>  Khôi phục CSDL từ file .bak hoặc .sql"
	@echo ""
	@echo "Kiểm thử & Chất lượng mã nguồn:"
	@echo "  make test          Chạy toàn bộ kiểm thử backend và mobile"
	@echo "  make test-backend  Chạy bộ kiểm thử backend pytest"
	@echo "  make test-mobile   Chạy bộ kiểm thử mobile Flutter test"
	@echo "  make analyze       Chạy phân tích tĩnh Flutter analyze"
	@echo "  make test-pwa      Kiểm tra manifest và cấu hình PWA"
	@echo "  make build-pwa     Build Flutter Web để chạy tại /app/"
	@echo "  make test-speech   Kiểm thử runtime giọng nói (cần môi trường speech)"
	@echo "  make test-learning-live  Kiểm tra SQL Server, tự rollback dữ liệu kiểm thử"
	@echo ""
	@echo "Dữ liệu tri thức:"
	@echo "  make seed          Nạp dữ liệu SGK và build Knowledge Graph trong Neo4j"
	@echo "  make clean         Xóa bỏ cache và file build tạm"

up:
	bash scripts/run_app.sh --backend-only

run:
	bash scripts/run_app.sh $(if $(DEVICE),$(DEVICE),android)

up-full:
	bash scripts/run_app.sh --backend-only
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

restart: down up

backup-db:
	mkdir -p $(BACKUP_DIR)
	$(COMPOSE) exec -T sqlserver mkdir -p /var/opt/mssql/backup
	$(COMPOSE) exec -T sqlserver $(SQLCMD) -Q "BACKUP DATABASE [$(DB_NAME)] TO DISK = N'/var/opt/mssql/backup/$(BACKUP_BAK)' WITH INIT, COPY_ONLY"
	$(COMPOSE) cp sqlserver:/var/opt/mssql/backup/$(BACKUP_BAK) $(BACKUP_DIR)/$(BACKUP_BAK)
	$(COMPOSE) run --rm -T api python -m english7.cli dump-sql --database $(DB_NAME) > $(BACKUP_DIR)/$(BACKUP_SQL)
	@echo "Sao lưu thành công vào $(BACKUP_DIR)/$(BACKUP_BAK) và $(BACKUP_DIR)/$(BACKUP_SQL)"

restore:
	@test -n "$(FILE)" || (echo "Sử dụng: make restore FILE=$(BACKUP_DIR)/<file.sql|file.bak>"; exit 1)
	@case "$(FILE)" in \
	  *.bak) \
	    cp "$(FILE)" /tmp/restore.bak && \
	    $(COMPOSE) exec -T sqlserver mkdir -p /var/opt/mssql/backup && \
	    $(COMPOSE) cp /tmp/restore.bak sqlserver:/var/opt/mssql/backup/restore.bak && \
	    $(COMPOSE) exec -T sqlserver $(SQLCMD) -Q "USE master; IF DB_ID('$(DB_NAME)') IS NOT NULL BEGIN ALTER DATABASE [$(DB_NAME)] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [$(DB_NAME)]; END; RESTORE DATABASE [$(DB_NAME)] FROM DISK = N'/var/opt/mssql/backup/restore.bak' WITH MOVE '$(DB_NAME)' TO '/var/opt/mssql/data/$(DB_NAME).mdf', MOVE '$(DB_NAME)_log' TO '/var/opt/mssql/data/$(DB_NAME)_log.ldf', REPLACE";; \
	  *.sql) \
	    $(COMPOSE) exec -T sqlserver $(SQLCMD) -d $(DB_NAME) -i /dev/stdin < "$(FILE)";; \
	  *) \
	    echo "Không hỗ trợ định dạng file: $(FILE)"; exit 1;; \
	esac
	@echo "Khôi phục CSDL thành công từ $(FILE)"

test: test-launcher test-backend test-mobile

test-launcher:
	python3 scripts/test_run_app.py

test-backend:
	cd backend && $(UV) run pytest tests --ignore=tests/integration -q

test-mobile:
	cd mobile && $(FLUTTER) test

test-pwa:
	python3 scripts/test_pwa_assets.py

build-pwa: test-pwa
	cd mobile && $(FLUTTER) build web --release --base-href /app/ --web-content-hash \
		--dart-define=API_BASE_URL=https://13.229.72.146.sslip.io \
		--dart-define=IMAGE_POLL_INTERVAL_MS=1000 \
		--dart-define=IMAGE_POLL_MAX_ATTEMPTS=30

analyze:
	cd mobile && $(FLUTTER) analyze

migrate:
	$(COMPOSE) exec -T api alembic upgrade head

seed-flashcards:
	$(COMPOSE) exec -T api python -m english7.modules.flashcards.seed

speech-setup:
	bash scripts/setup_speech.sh

speech-up: up
	$(SPEECH_COMPOSE) up -d --build --wait --wait-timeout 240 speech-runtime

speech-down:
	$(SPEECH_COMPOSE) stop speech-runtime

test-speech:
	@test -x speech/.venv/bin/python || (echo "Chạy bash scripts/setup_speech.sh --deps-only trước."; exit 1)
	speech/.venv/bin/python -m pytest speech -q

test-learning-live:
	$(COMPOSE) exec -T api python -c "import sys; scope={}; exec(compile(sys.stdin.read(), 'test_learning_sqlserver.py', 'exec'),scope); scope['test_learning_transactions_on_live_database'](); print('Live SQL learning smoke passed; test records rolled back')" < backend/tests/integration/test_learning_sqlserver.py

seed:
	./scripts/build_full_knowledge_graph.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf mobile/build mobile/.dart_tool 2>/dev/null || true
