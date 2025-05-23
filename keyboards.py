# keyboards.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Выбрать корм", callback_data="menu:feed_type"),
        InlineKeyboardButton(text="Акции", callback_data="menu:promo"),
        InlineKeyboardButton(text="Корзина", callback_data="menu:cart"),
        InlineKeyboardButton(text="Помощь", callback_data="menu:help"),
    )
    builder.adjust(2)
    return builder.as_markup()

def back_to_main():
    # Можно вернуть пустую клавиатуру или ReplyKeyboardRemove, если не нужна реплай-клавиатура
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()

__all__ = ["main_menu", "back_to_main"]

