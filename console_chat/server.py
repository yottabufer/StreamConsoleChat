import asyncio
import logging
from asyncio import StreamReader, StreamWriter


class ChatServer:

    def __init__(self):
        self._username_to_writer = {}

    async def start_chat_server(self, host: str, port: int) -> None:
        """Запускает сервер чата на указанном хосте и порту
        :param host: хост для запуска сервера
        :param port: порт для запуска сервера
        :return: None"""
        server = await asyncio.start_server(self.client_connected, host, port)
        async with server:
            await server.serve_forever()

    async def client_connected(self, reader: StreamReader, writer: StreamWriter) -> None:
        """Обрабатывает подключение клиента к серверу
        :param reader: объект чтения данных от клиента
        :param writer: объект записи данных клиенту
        :return: None"""
        command = await reader.readline()
        print(f'Подключение --  {reader} {writer}')
        command, args = command.split(b' ')
        if command == b'CONNECT':
            username = args.replace(b'\n', b'').decode()
            self._add_user(username, reader, writer)
            await self._on_connect(username, writer)
        else:
            logging.error('Получена неверная команда от клиента -- отключаю')
            writer.close()
            await writer.wait_closed()

    def _add_user(self, username: str, reader: StreamReader, writer: StreamWriter) -> None:
        """Добавляет нового пользователя в список активных пользователей и начинает слушать сообщения от него
        :param username: имя пользователя
        :param reader: объект чтения данных от клиента
        :param writer: объект записи данных клиенту
        :return: None"""
        self._username_to_writer[username] = writer
        asyncio.create_task(self._listen_for_messages(username, reader))

    async def _on_connect(self, username: str, writer: StreamWriter) -> None:
        """Отправляет приветственное сообщение новому пользователю и уведомляет всех о его подключении
        :param username: имя пользователя
        :param writer: объект записи данных клиенту
        :return: None"""
        writer.write(f'Добро пожаловать! {len(self._username_to_writer)} юзер(а) онлайн\n'.encode())
        await writer.drain()
        await self._notify_all(f'{username} подключился!!!!\n')

    async def _remove_user(self, username: str) -> None:
        """Удаляет пользователя из списка активных пользователей и закрывает соединение
        :param username: имя пользователя
        :return: None"""
        writer = self._username_to_writer[username]
        del self._username_to_writer[username]
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logging.exception('Ошибка при закрытии программы записи клиента -- игнорирую...', exc_info=e)

    async def _listen_for_messages(self, username: str, reader: StreamReader) -> None:
        """Слушает сообщения от пользователя и рассылает их всем активным пользователям
        :param username: имя пользователя
        :param reader: объект чтения данных от клиента
        :return: None"""
        try:
            while (data := await asyncio.wait_for(reader.readline(), 60)) != b'':
                await self._notify_all(f'{username}: {data.decode()}')
            await self._notify_all(f'{username} вышел из чата\n')
        except Exception as e:
            logging.exception('Ошибка чтения с клиента...', exc_info=e)
            await self._remove_user(username)

    async def _notify_all(self, message: str) -> None:
        """Рассылает сообщение всем активным пользователям
        :param message: сообщение для рассылки
        :return: None"""
        inactive_users = []
        for username, writer in self._username_to_writer.items():
            try:
                writer.write(message.encode())
                await writer.drain()
            except ConnectionError as e:
                logging.exception('Не удалось написать клиенту...', exc_info=e)
                inactive_users.append(username)

        [await self._remove_user(username) for username in inactive_users]


async def main():
    chat_server = ChatServer()
    await chat_server.start_chat_server('127.0.0.1', 8000)


asyncio.run(main())
