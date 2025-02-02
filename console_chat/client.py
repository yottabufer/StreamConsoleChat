import os
import logging
import tty
from asyncio import StreamWriter, StreamReader
import asyncio

import sys
import shutil
from collections import deque
from typing import Callable, Deque, Awaitable


class MessageStore:
    def __init__(self, callback: Callable[[Deque], Awaitable[None]], max_size: int):
        """Инициализирует объект хранилища сообщений
        :param callback: функция обратного вызова для обработки новых сообщений
        :param max_size: максимальный размер очереди сообщений
        :return: None"""
        self._deque = deque(maxlen=max_size)
        self._callback = callback

    async def append(self, item):
        """Добавляет новое сообщение в очередь и вызывает функцию обратного вызова
        :param item: сообщение для добавления
        :return: None"""
        self._deque.append(item)
        await self._callback(self._deque)


def save_cursor_position():
    """Сохраняет текущую позицию курсора на экране
    :return: None"""
    sys.stdout.write('\0337')


def restore_cursor_position():
    """Восстанавливает ранее сохраненную позицию курсора на экране.
    :return: None"""
    sys.stdout.write('\0338')


def move_to_top_of_screen():
    """Перемещает курсор в верхний левый угол экрана
    :return: None"""
    sys.stdout.write('\033[H')


def delete_line():
    """Удаляет текущую строку на экране
    :return: None"""
    sys.stdout.write('\033[2K')


def clear_line():
    """Очищает текущую строку на экране и перемещает курсор в начало строки
    :return: None"""
    sys.stdout.write('\033[2K\033[0G')


def move_back_one_char():
    """Перемещает курсор на один символ назад
    :return: None"""
    sys.stdout.write('\033[1D')


def move_to_bottom_of_screen() -> int:
    """Перемещает курсор к нижней части экрана и возвращает количество строк
    :return: количество строк на экране"""
    _, total_rows = shutil.get_terminal_size()
    input_row = total_rows - 1
    sys.stdout.write(f'\033[{input_row}E')
    return total_rows


async def read_line(stdin_reader: StreamReader) -> str:
    """Считывает строку из стандартного ввода асинхронно
    :param stdin_reader: объект чтения данных от стандартного ввода
    :return: считанная строка"""

    def erase_last_char():
        move_back_one_char()
        sys.stdout.write(' ')
        move_back_one_char()

    delete_char = b'\x7f'
    input_buffer = deque()
    while (input_char := await stdin_reader.read(1)) != b'\n':
        if input_char == delete_char:
            if len(input_buffer) > 0:
                input_buffer.pop()
                erase_last_char()
                sys.stdout.flush()
        else:
            input_buffer.append(input_char)
            sys.stdout.write(input_char.decode())
            sys.stdout.flush()
    clear_line()
    return b''.join(input_buffer).decode()


async def create_stdin_reader() -> StreamReader:
    """Создает объект чтения данных от стандартного ввода
    :return: объект чтения данных от стандартного ввода"""
    stream_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return stream_reader


async def send_message(message: str, writer: StreamWriter):
    """Отправляет сообщение через заданный объект записи данных
    :param message: сообщение для отправки
    :param writer: объект записи данных
    :return: None"""
    writer.write((message + '\n').encode())
    await writer.drain()


async def listen_for_messages(reader: StreamReader, message_store: MessageStore):
    """Асинхронно слушает входящие сообщения и добавляет их в хранилище сообщений
    :param reader: объект чтения данных от клиента
    :param message_store: Хранилище сообщений
    :return: None"""
    while (message := await reader.readline()) != b'':
        await message_store.append(message.decode())
    await message_store.append('Server closed connection.')


async def read_and_send(stdin_reader: StreamReader, writer: StreamWriter):
    """Асинхронно считывает сообщения от пользователя и отправляет их серверу
    :param stdin_reader: объект чтения данных от стандартного ввода
    :param writer: объект записи данных
    :return: None"""
    while True:
        message = await read_line(stdin_reader)
        await send_message(message, writer)


async def main():
    async def redraw_output(items: deque):
        """Перерисовывает вывод сообщений на экране
        :param items: очередь сообщений для отображения
        :return: None"""
        save_cursor_position()
        move_to_top_of_screen()
        for item in items:
            delete_line()
            sys.stdout.write(item)
        restore_cursor_position()

    tty.setcbreak(0)
    os.system('clear')
    rows = move_to_bottom_of_screen()

    messages = MessageStore(redraw_output, rows - 1)

    stdin_reader = await create_stdin_reader()
    sys.stdout.write('Введите ваш username: ')
    username = await read_line(stdin_reader)

    reader, writer = await asyncio.open_connection('127.0.0.1', 8000)  # C

    writer.write(f'CONNECT {username}\n'.encode())
    await writer.drain()

    message_listener = asyncio.create_task(listen_for_messages(reader, messages))  # D
    input_listener = asyncio.create_task(read_and_send(stdin_reader, writer))

    try:
        await asyncio.wait([message_listener, input_listener], return_when=asyncio.FIRST_COMPLETED)
    except Exception as e:
        logging.exception(e)
        writer.close()
        await writer.wait_closed()


asyncio.run(main())
