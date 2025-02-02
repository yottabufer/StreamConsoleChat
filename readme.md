# StreamConsoleChat

## Консольный чат построенных на встроенных библиотеках python: asyncio и содержащиеся в ней StreamWriter, StreamReader

### Проект можно запустить только на linux системах, т.к. в windows плохо реализована работа с потоками (они же threads)

## Основной стек сервиса:

- `Python = ^3.11.4`
- Нет сторонних библиотек :)

## Для запуска потребуется запустить server.py

```commandline
python -m console_chat/server.py
```

### После чего можно запускать client.py в нужном количестве для "чата"

```commandline
python -m console_chat/client.py
```
