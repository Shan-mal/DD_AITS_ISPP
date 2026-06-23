# Попытка в выполнение диплома в ЦК
# НЕ ТЕСТИРОВАЛОСЬ ПОЛНОСТЬЮ!
1. Подготовка окружения
1.1 Установите Python
1.2 Установите PostgreSQL
Оставьте порт по умолчанию 5432.
1.3 Установите Redis
1.4 Установите Docker Desktop (для Redis)
1.5 Настройте структуру проекта
Создайте папку проекта, например C:\parking_system, и поместите в неё все файлы из объединённого проекта (core, models, schemas, tasks, license_plate, routers, dependencies.py, main.py).
3. Настройка базы данных PostgreSQL
3.1 Создайте базу данных и пользователя
Откройте SQL Shell (psql) или pgAdmin и выполните следующие команды.
В psql войдите под суперпользователем:
sql
-- Создать пользователя (если не хотите использовать postgres)
CREATE USER parking_user WITH PASSWORD 'strongpassword123';
-- Создать базу данных
CREATE DATABASE parking_db OWNER parking_user;
-- Дать все права
GRANT ALL PRIVILEGES ON DATABASE parking_db TO parking_user;
3.2 Настройка подключения в проекте
В файле core/database.py укажите корректную строку подключения. Рекомендуется использовать переменные окружения, чтобы не хранить пароль в коде. Для простоты на время тестирования можно записать напрямую:
DATABASE_URL = "postgresql://parking_user:strongpassword123@localhost:5432/parking_db"
Если оставили пользователя postgres, то строка будет такой:
DATABASE_URL = "postgresql://postgres:ваш_пароль@localhost:5432/parking_db"
4. Инициализация таблиц базы данных
Запустите файл init_db.py.
6. Запуск Redis (через Docker)
Если вы используете Docker, выполните в терминале:

bash
docker run --name redis-parking -p 6379:6379 -d redis:7-alpine
Проверьте, что контейнер запущен:

bash
docker ps
Если Docker не используется, а установлен Memurai или нативный порт Redis, убедитесь, что сервер запущен на порту 6379.
7. Запуск фоновых служб (Celery Worker и Beat)
Откройте два новых терминала (обязательно активируйте виртуальное окружение в каждом venv\Scripts\activate).

7.1 Запуск воркера Celery
В первом терминале перейдите в корень проекта и выполните:

bash
celery -A core.celery_app worker --loglevel=info -P solo
Флаг -P solo важен для Windows, потому что многопроцессный пул (prefork) не работает без дополнительных настроек. Для production-окружения на Windows рекомендуется использовать gevent или threads, но для теста достаточно solo.

7.2 Запуск планировщика Beat (отдельно)
Во втором терминале:

bash
celery -A core.celery_app beat --loglevel=info
Beat будет выполнять периодические задачи: проверку истекающих сессий, ночной отчёт, синхронизацию датчиков и очистку зависших сессий.

8. Запуск веб-сервера FastAPI
В третьем терминале (или в основном, где вы не запускали Celery) выполните:

bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
Флаг --reload удобен при разработке, он автоматически перезагружает сервер при изменениях кода.

После запуска вы увидите сообщение:

text
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
Откройте браузер и перейдите по адресу http://localhost:8000/docs – вы должны увидеть автоматическую документацию Swagger со всеми доступными эндпоинтами.

9. Первое тестирование системы
Теперь проверим ключевые сценарии. Действия можно выполнять прямо через Swagger UI или с помощью curl в четвёртом терминале.

9.1 Регистрация пользователя
В Swagger найдите POST /auth/register, нажмите «Try it out» и заполните параметры:

email: user@test.com

password: test123

full_name: Иван Иванов

Или через curl:

bash
curl -X POST "http://localhost:8000/auth/register?email=user@test.com&password=test123&full_name=Иван%20Иванов"
Ответ: {"msg": "User created"}.

9.2 Получение JWT токена
Используйте POST /auth/token. В Swagger это форма OAuth2, поэтому просто введите:

username: user@test.com

password: test123

Ответ будет содержать access_token. Скопируйте его.

9.3 Старт парковочной сессии
Для старта сессии требуется авторизация. В Swagger нажмите кнопку «Authorize» (замок вверху справа), вставьте токен в поле Value как Bearer ваш_токен и нажмите Authorize. Затем выполните POST /parking/start с телом:

json
{
  "plate_number": "А123БВ77"
}
Важно: В базе данных должны существовать хотя бы одно парковочное место со статусом free и один активный тариф. Если вы ещё не добавили их, создайте вручную через pgAdmin или добавьте SQL-скрипт. Для быстрого старта выполните в psql:

sql
-- Вставка тарифа
INSERT INTO tariffs (name, price_per_minute, max_daily, is_active) 
VALUES ('Стандартный', 2.5, 500, true);

-- Вставка нескольких парковочных мест
INSERT INTO parking_spots (section, spot_number, status, floor) 
VALUES 
('A', 1, 'free', 1),
('A', 2, 'free', 1),
('B', 1, 'free', 2);
Теперь повторите запрос старта сессии. В случае успеха вернётся JSON с данными созданной сессии:

json
{
  "id": 1,
  "vehicle_id": 1,
  "spot_id": 1,
  "entry_time": "2025-03-20T12:34:56",
  "tariff_id": 1,
  "status": "active"
}
Проверьте в базе, что статус места изменился на occupied.

9.4 Тест загрузки кадра с камеры (опционально)
Если вы настроили распознавание, можете отправить изображение через POST /camera/entry. В Swagger это файл. Ответ вернёт task_id задачи Celery. Результат выполнения можно отследить в логах воркера.

9.5 Проверка фоновых задач
Уведомления: Через 10 минут после старта сессии в логах воркера вы увидите сообщение от задачи send_expiry_notification. В реальности отправится email, сейчас просто печатается в консоль.

Отчёт: В 2 часа ночи (или в момент ручного вызова /task/check-expiring) сгенерируется CSV-файл в папке reports (если были завершённые сессии за предыдущий день).

10. Остановка всех компонентов
Остановите FastAPI: в терминале с uvicorn нажмите Ctrl+C.

Остановите Celery worker и beat: в соответствующих терминалах нажмите Ctrl+C.

Остановите контейнер Redis (если использовали Docker):

bash
docker stop redis-parking
Если PostgreSQL не нужен, можно остановить службу через «Службы» Windows или оставить работать для дальнейших экспериментов.
