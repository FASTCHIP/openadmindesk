# Post-Release Fix Plan

## Issue 1 (P0): RDP не запускается, нет ошибок

**Проблема:** Встроенный RDP-клиент (FreeRDP ctypes) не выдаёт ни запросов сертификата, ни ошибок при подключении. `_on_frame_update` — stub.

**План:**
- [ ] 1.1 Добавить `error_occurred` сигнал с читаемой диагностикой в `_RdpWorker.run()`: перехват исключений, проверка `freerdp_connect` (rc != 0), проверка `freerdp_client_start`.
- [ ] 1.2 В `RdpSessionTab` отображать ошибку в info_text красным цветом при сбое.
- [ ] 1.3 Добавить логгирование каждого шага: `freerdp_new → configure → register_callbacks → connect → start`.
- [ ] 1.4 Если библиотека FreeRDP не найдена — показать вместо таба сообщение «FreeRDP not installed: sudo apt install libfreerdp-client3».

## Issue 2 (P0): Vault — потеря настроек при создании подключения

**Проблема:** При создании профиля с сохранением пароля в vault, если vault заблокирован — ошибка в конце мастера, все настройки теряются.

**План:**
- [ ] 2.1 В Session Wizard на странице Summary перед Finish проверять: если профиль требует vault (пароль/ключ) и vault заблокирован — показать диалог «Vault locked. Unlock now?» с кнопками Unlock / Save without password / Cancel.
- [ ] 2.2 При Unlock — открыть диалог ввода мастер-пароля, разблокировать, сохранить профиль.
- [ ] 2.3 При «Save without password» — сохранить профиль без сохранения пароля в vault.
- [ ] 2.4 Добавить настройку `vault_auto_lock_minutes = 0` = «не блокировать на этом рабочем месте».
- [ ] 2.5 При старте приложения: если `prompt_master_password_on_startup = True` — сразу показать диалог разблокировки vault, чтобы все последующие операции не прерывались.

## Issue 3 (P1): Account Manager — странная форма

**Проблема:** Форма создания учётной записи vault требует host, port, private key — это свойства подключения, а не учётной записи.

**План:**
- [ ] 3.1 Упростить `AccountDialog` / `VaultAccount`: оставить только поля name, username, password, notes. Убрать host, port, private_key_path, private_key_passphrase.
- [ ] 3.2 В Profile Editor: поле credential_id выбирает из vault account (логин+пароль), host/port/key берутся из самого профиля.
- [ ] 3.3 Добавить миграцию: существующие vault accounts с host/port не ломать, поля оставить в JSON но скрыть из UI.

## Issue 4 (P1): Tools Hub — внешние утилиты

**Проблема:** Tools Hub показывает ping, curl, nmap и запускает их через системный терминал. По условию «все инструменты внутри» — должны быть встроенные аналоги.

**План:**
- [ ] 4.1 Удалить `shutil.which()` и внешний запуск из `ToolsHub`.
- [ ] 4.2 Заменить на встроенные Python-утилиты: `BuiltinPing` (icmp через subprocess ping), `BuiltinPortScanner` (socket.connect), `BuiltinDnsLookup` (socket.getaddrinfo), `BuiltinTraceroute` (scapy/udp).
- [ ] 4.3 Каждая утилита — отдельная кнопка, открывающая диалог с полем ввода и областью вывода.
- [ ] 4.4 Утилиты работают асинхронно (QThread) — не блокируют UI.

## Issue 5 (P1): Настройки — непонятное расположение

**Проблема:** Пользователь не знает где лежат настройки и не может забрать их на флешку.

**План:**
- [ ] 5.1 В Settings → General добавить отображение пути к файлам: `Settings: ~/.local/share/openadmindesk/settings.json`, `Profiles: ~/.local/share/openadmindesk/profiles.db`, `Vault: ~/.local/share/openadmindesk/vault.json`.
- [ ] 5.2 Добавить кнопку «Open data folder» — открывает файловый менеджер.
- [ ] 5.3 Добавить «Portable mode»: если рядом с исполняемым файлом есть папка `data/` — использовать её вместо `~/.local/share/openadmindesk/`.

## Issue 6 (P2): Масштабирование окна

**Проблема:** Часть окна обрезается при масштабировании.

**План:**
- [ ] 6.1 Проверить `window_width`/`window_height` в AppSettings — скорректировать минимальные размеры.
- [ ] 6.2 В MainWindow добавить `setMinimumSize(800, 600)`.
- [ ] 6.3 Проверить `QSplitter` stretch factors — tree/tab area.
- [ ] 6.4 Установить `Qt.HighDpiScaleFactorRoundingPolicy.PassThrough` для дробного масштабирования.

## Приоритеты

| Приоритет | Задача | Оценка |
|-----------|--------|--------|
| P0 | Issue 1: RDP диагностика | 2 файла |
| P0 | Issue 2: Vault unlock flow | 3 файла |
| P1 | Issue 3: Account Manager | 2 файла |
| P1 | Issue 4: Tools Hub → Built-in | 1 файл |
| P1 | Issue 5: Settings location | 2 файла |
| P2 | Issue 6: Window scaling | 1 файл |

## Порядок выполнения

1. Issue 1 (RDP) + Issue 2 (Vault) — критические
2. Issue 3 (Account Manager) + Issue 5 (Settings) — UX
3. Issue 4 (Tools Hub) — функциональность
4. Issue 6 (Scaling) — косметика
