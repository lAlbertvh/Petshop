import sys
import os
import logging
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove, KeyboardButton, FSInputFile, InlineKeyboardMarkup, ReplyKeyboardMarkup
from database import User, Product, get_session
from sqlalchemy.orm import Session as SessionType
from sqlalchemy.orm.attributes import flag_modified
from keyboards import main_menu # Убедись, что keyboards.py корректно определен

# Добавляем путь к текущей директории для импортов
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

logging.info("Script started: Initializing bot and dispatcher.")

# Инициализация бота и диспетчера
try:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN environment variable is not set. Bot cannot start.")
        raise ValueError("BOT_TOKEN is not set in .env file.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    logging.info("Bot and Dispatcher initialized successfully.")

    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        logging.warning("ADMIN_ID environment variable is not set. Admin notifications will not work.")
except Exception as e:
    logging.critical(f"FATAL ERROR during Bot/Dispatcher initialization: {e}", exc_info=True)
    sys.exit(1)


# Определяем состояния пользователя
class UserState(StatesGroup):
    MAIN_MENU = State()
    CHOOSING_CATEGORY = State()
    CHOOSING_SUBCATEGORY = State()
    VIEWING_PRODUCT = State()
    IN_CART = State()
    ENTERING_ADDRESS = State()
    ENTERING_CONTACT = State()
    CONFIRMING_ORDER = State()
    WAITING_FOR_HELP_MESSAGE = State()
    WAITING_FOR_HELP_CONTACT = State()

# Определяем состояния для заказа
class OrderStates(StatesGroup):
    waiting_for_address = State()
    waiting_for_contact = State()

# Определяем состояния для помощи
class HelpStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_contact = State()

# Вспомогательная функция для редактирования или отправки сообщения
async def edit_or_send_message(callback: types.CallbackQuery, text: str = None, photo: FSInputFile = None, reply_markup=None):
    is_reply_keyboard_type = isinstance(reply_markup, (ReplyKeyboardRemove, ReplyKeyboardMarkup))
    # Проверяем, является ли оригинальное сообщение, на которое был сделан callback, фотографией
    is_original_message_photo = callback.message.photo is not None

    logging.info(f"edit_or_send_message called. Photo: {photo is not None}, Reply_markup type: {type(reply_markup)}, Is Reply Keyboard: {is_reply_keyboard_type}, Original message was photo: {is_original_message_photo}, Text: '{text}'")

    try:
        if photo: # Если мы хотим отправить новое сообщение с фото
            new_message = await callback.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
            try:
                await callback.message.delete() # Удаляем старое сообщение
            except Exception as e:
                logging.debug(f"Could not delete old message (photo context): {e}")
            return new_message
        # Если это Reply-клавиатура ИЛИ оригинальное сообщение было фото (и мы не отправляем новое фото)
        elif is_reply_keyboard_type or is_original_message_photo:
            # В этих случаях мы не можем использовать edit_text, поэтому отправляем новое сообщение
            new_message = await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
            try:
                # Пытаемся удалить оригинальное сообщение (которое могло быть Inline-клавиатурой или фото)
                await callback.message.delete()
            except Exception as e:
                logging.debug(f"Could not delete old message after sending new ReplyKeyboard/Photo-to-text: {e}")
            return new_message
        else: # В противном случае, пытаемся отредактировать текст существующего сообщения
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            return callback.message
    except Exception as e:
        logging.warning(f"Failed to edit message. Sending new one. Error: {e}")
        # Запасной вариант: всегда отправляем новое сообщение, если редактирование не удалось
        try:
            if photo:
                new_message = await callback.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
            else:
                new_message = await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
            try:
                await callback.message.delete()
            except Exception as delete_e:
                logging.debug(f"Could not delete old message after failed edit: {delete_e}")
            return new_message
        except Exception as send_e:
            logging.error(f"Failed to send new message after edit failure: {send_e}")
            return None

# Middleware для управления сессиями базы данных
@dp.update.middleware()
async def db_session_middleware(handler, event, data):
    with get_session() as session:
        data["session"] = session
        result = await handler(event, data)
        session.commit()
    return result

# Обработчик команды /start
@dp.message(Command("start"))
async def handle_start(message: types.Message, state: FSMContext, session: SessionType):
    user_id = message.from_user.id
    logging.info(f"handle_start called for user ID: {user_id}")
    
    user = session.query(User).filter_by(id=user_id).first()
    
    if not user:
        logging.info(f"User {user_id} not found in DB. Creating new user.")
        user = User(id=user_id, cart=[], state=UserState.MAIN_MENU.state)
        session.add(user)
        await message.answer("Добро пожаловать в PetShopBot! Выберите действие:", reply_markup=main_menu())
    else:
        logging.info(f"User {user_id} found in DB. Updating state.")
        user.state = UserState.MAIN_MENU.state
        await message.answer("С возвращением в PetShopBot! Чем могу помочь?", reply_markup=main_menu())
    await state.set_state(UserState.MAIN_MENU)

# Обработчик кнопки "В главное меню"
@dp.callback_query(F.data == "menu:main")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserState.MAIN_MENU)
    
    try:
        await callback.message.answer("Возвращаемся в главное меню...", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logging.debug(f"Could not send ReplyKeyboardRemove message in back_to_main_menu: {e}")

    await edit_or_send_message(callback, text="Главное меню:", reply_markup=main_menu())


# Обработчик кнопки "Выбрать корм"
@dp.callback_query(F.data == "menu:feed_type")
async def feed_type_menu(callback: types.CallbackQuery, state: FSMContext):
    logging.info("feed_type_menu called!")
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="Корм для кошек", callback_data="feed:cats"),
        types.InlineKeyboardButton(text="Корм для собак", callback_data="feed:dogs"),
        # Если захотите вернуть корм для ежей и попугаев, раскомментируйте эти строки:
        # types.InlineKeyboardButton(text="Корм для ежей", callback_data="feed:other"),
        # types.InlineKeyboardButton(text="Корм для попугаев", callback_data="feed:birds"),
    )
    builder.adjust(2)
    builder.row(types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"))
    await edit_or_send_message(callback, text="Выберите категорию:", reply_markup=builder.as_markup())
    await state.set_state(UserState.CHOOSING_CATEGORY)

# Обработчик кнопки "Акции"
@dp.callback_query(F.data == "menu:promo")
async def promo_menu(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"))
    await edit_or_send_message(callback, text="Акция: Возьмите 10 пачек и одну получите бонусом!", reply_markup=builder.as_markup())
    await callback.answer()
    await state.set_state(UserState.MAIN_MENU)

# Вспомогательная функция для отображения корзины
async def show_cart_with_session(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer()
    user = session.query(User).filter_by(id=callback.from_user.id).first()
    if not user or not user.cart:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"))
        await edit_or_send_message(callback, text="Корзина пуста!", reply_markup=builder.as_markup())
        await state.set_state(UserState.IN_CART)
        return
    
    total = 0
    text = "🛒 Ваша корзина:\n\n"
    cart_items_builder = InlineKeyboardBuilder()
    
    for i, item in enumerate(user.cart):
        product = session.query(Product).filter_by(id=item["product_id"]).first()
        if product:
            item_total_price = product.price * item['quantity']
            total += item_total_price
            text += f"{i+1}. {product.name}\n"
            text += f"    Количество: {item['quantity']} шт. | Цена за шт.: {product.price} руб.\n"
            text += f"    Общая цена: {item_total_price} руб.\n\n"
            cart_items_builder.row(
                types.InlineKeyboardButton(text=f"➖", callback_data=f"cart_item:remove_one:{i}"),
                types.InlineKeyboardButton(text=f"🗑️", callback_data=f"cart_item:delete_all:{i}"),
                types.InlineKeyboardButton(text=f"➕", callback_data=f"cart_item:add_one:{i}")
            )
        else:
            text += f"{i+1}. Неизвестный товар (ID: {item['product_id']})\n"
            text += f"    Количество: {item['quantity']} шт.\n\n"
            cart_items_builder.row(
                types.InlineKeyboardButton(text=f"🗑️ Удалить неизвестный", callback_data=f"cart_item:delete_all:{i}")
            )
    
    text += f"💵 Итого: {total} руб."
    
    main_cart_buttons_builder = InlineKeyboardBuilder()
    main_cart_buttons_builder.add(
        types.InlineKeyboardButton(text="Очистить корзину", callback_data="cart:clear"),
        types.InlineKeyboardButton(text="Оформить заказ", callback_data="cart:checkout"),
    )
    main_cart_buttons_builder.adjust(2)
    main_cart_buttons_builder.row(types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"))
    
    final_markup_builder = InlineKeyboardBuilder()
    final_markup_builder.attach(cart_items_builder)
    final_markup_builder.attach(main_cart_buttons_builder)
    
    await edit_or_send_message(callback, text=text, reply_markup=final_markup_builder.as_markup())
    await state.set_state(UserState.IN_CART)

# Обработчик увеличения количества товара в корзине
@dp.callback_query(F.data.startswith("cart_item:add_one:"), UserState.IN_CART)
async def add_one_to_cart_item(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer()
    item_index = int(callback.data.split(":")[2])
    user = session.query(User).filter_by(id=callback.from_user.id).first()
    if user and len(user.cart) > item_index:
        updated_cart = list(user.cart)
        updated_cart[item_index]["quantity"] += 1
        user.cart = updated_cart
        flag_modified(user, "cart")
        session.commit()
        await show_cart_with_session(callback, state, session)
    else:
        await callback.answer("Ошибка: Товар не найден в корзине.", show_alert=True)

# Обработчик уменьшения количества товара в корзине
@dp.callback_query(F.data.startswith("cart_item:remove_one:"), UserState.IN_CART)
async def remove_one_from_cart_item(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer()
    item_index = int(callback.data.split(":")[2])
    user = session.query(User).filter_by(id=callback.from_user.id).first()
    if user and len(user.cart) > item_index:
        updated_cart = list(user.cart)
        if updated_cart[item_index]["quantity"] > 1:
            updated_cart[item_index]["quantity"] -= 1
        else:
            del updated_cart[item_index]
        user.cart = updated_cart
        flag_modified(user, "cart")
        session.commit()
        await show_cart_with_session(callback, state, session)
    else:
        await callback.answer("Ошибка: Товар не найден в корзине.", show_alert=True)

# Обработчик удаления всех единиц товара из корзины
@dp.callback_query(F.data.startswith("cart_item:delete_all:"), UserState.IN_CART)
async def delete_all_from_cart_item(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer("Товар удален из корзины.", show_alert=True)
    item_index = int(callback.data.split(":")[2])
    user = session.query(User).filter_by(id=callback.from_user.id).first()
    if user and len(user.cart) > item_index:
        updated_cart = list(user.cart)
        del updated_cart[item_index]
        user.cart = updated_cart
        flag_modified(user, "cart")
        session.commit()
        await show_cart_with_session(callback, state, session)
    else:
        await callback.answer("Ошибка: Товар не найден в корзине.", show_alert=True)

# Меню выбора корма для кошек
@dp.callback_query(F.data == "feed:cats")
async def cats_menu(callback: types.CallbackQuery, session: SessionType):
    builder = InlineKeyboardBuilder()
    # Получаем продукты для кошек из базы данных
    cat_products = session.query(Product).filter_by(category="cats").all()
    for product in cat_products:
        builder.add(types.InlineKeyboardButton(text=product.name, callback_data=f"product:{product.id}"))
    builder.adjust(1)
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="menu:feed_type"),
        types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"),
    )
    await edit_or_send_message(callback, text="Выберите корм для кошек:", reply_markup=builder.as_markup())
    await callback.answer()

# Меню выбора корма для собак
@dp.callback_query(F.data == "feed:dogs")
async def dogs_menu(callback: types.CallbackQuery, session: SessionType):
    builder = InlineKeyboardBuilder()
    # Получаем продукты для собак из базы данных
    dog_products = session.query(Product).filter_by(category="dogs").all()
    for product in dog_products:
        builder.add(types.InlineKeyboardButton(text=product.name, callback_data=f"product:{product.id}"))
    builder.adjust(1)
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="menu:feed_type"),
        types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"),
    )
    await edit_or_send_message(callback, text="Выберите корм для собак:", reply_markup=builder.as_markup())
    await callback.answer()

# Закомментированные функции для ежей и попугаев (если решите их вернуть)
# @dp.callback_query(F.data == "feed:other")
# async def other_menu(callback: types.CallbackQuery, session: SessionType):
#     builder = InlineKeyboardBuilder()
#     other_products = session.query(Product).filter_by(category="other").all()
#     for product in other_products:
#         builder.add(types.InlineKeyboardButton(text=product.name, callback_data=f"product:{product.id}"))
#     builder.adjust(1)
#     builder.row(
#         types.InlineKeyboardButton(text="Назад", callback_data="menu:feed_type"),
#         types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"),
#     )
#     await edit_or_send_message(callback, text="Выберите корм для ежей:", reply_markup=builder.as_markup())
#     await callback.answer()

# @dp.callback_query(F.data == "feed:birds")
# async def birds_menu(callback: types.CallbackQuery, session: SessionType):
#     builder = InlineKeyboardBuilder()
#     bird_products = session.query(Product).filter_by(category="birds").all()
#     for product in bird_products:
#         builder.add(types.InlineKeyboardButton(text=product.name, callback_data=f"product:{product.id}"))
#     builder.adjust(1)
#     builder.row(
#         types.InlineKeyboardButton(text="Назад", callback_data="menu:feed_type"),
#         types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"),
#     )
#     await edit_or_send_message(callback, text="Выберите корм для попугаев:", reply_markup=builder.as_markup())
#     await callback.answer()


# Вспомогательная функция для отображения продукта по ID
async def show_product_by_id(callback: types.CallbackQuery, state: FSMContext, session: SessionType, product_id: int):
    await callback.answer()
    logging.info(f"show_product_by_id: START. product_id received: {product_id}")
    
    product = session.query(Product).filter_by(id=product_id).first()
    
    if not product:
        logging.error(f"show_product_by_id: Product with ID {product_id} not found.")
        await edit_or_send_message(callback, text="Товар не найден.", reply_markup=main_menu())
        return

    # Определяем callback для кнопки "Назад" на основе категории товара
    if product.category == "cats":
        back_callback = "feed:cats"
    elif product.category == "dogs":
        back_callback = "feed:dogs"
    # Если захотите вернуть корм для ежей и попугаев, раскомментируйте эти строки:
    # elif product.category == "other":
    #     back_callback = "feed:other"
    # elif product.category == "birds":
    #     back_callback = "feed:birds"
    else:
        back_callback = "menu:main" # Запасной вариант

    image_path = os.path.join("/app/images", product.image_path)
    if not os.path.exists(image_path):
        logging.warning(f"Image file not found: {image_path}. Using placeholder.")
        photo = None
        image_warning = "\n\n(Изображение не найдено)"
    else:
        photo = FSInputFile(image_path)
        image_warning = ""

    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="Добавить в корзину",
            callback_data=f"cart:add:{product.id}" # Передаем только ID продукта
        ),
    )
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data=f"back:{back_callback}"),
        types.InlineKeyboardButton(text="В главное меню", callback_data="menu:main"),
    )
    
    await edit_or_send_message(
        callback,
        photo=photo,
        text=f"<b>{product.name}</b>\n{product.description}\nЦена: {product.price} руб.{image_warning}",
        reply_markup=builder.as_markup()
    )

# Универсальный обработчик для всех товаров (кошки и собаки)
@dp.callback_query(F.data.startswith("product:"))
async def show_product(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    product_id = int(callback.data.split(":")[1])
    await show_product_by_id(callback, state, session, product_id=product_id)


# Обработчик добавления товара в корзину
@dp.callback_query(F.data.startswith("cart:add:"))
async def add_to_cart(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    logging.info(f"Attempting to add to cart. Callback data: {callback.data}")
    await callback.answer("Добавляю товар в корзину...")

    parts = callback.data.split(":")
    
    if len(parts) < 3: # Теперь ожидаем cart:add:product_id
        logging.error(f"Invalid callback data format for cart:add: {callback.data}")
        await callback.answer("Ошибка: Неверный формат данных для добавления в корзину.", show_alert=True)
        await edit_or_send_message(callback, text="Произошла ошибка. Возвращаю в главное меню.", reply_markup=main_menu())
        return

    try:
        product_id = int(parts[2])
    except ValueError:
        logging.error(f"Invalid product_id in callback data: {parts[2]}")
        await callback.answer("Ошибка: Неверный ID товара.", show_alert=True)
        await edit_or_send_message(callback, text="Произошла ошибка. Возвращаю в главное меню.", reply_markup=main_menu())
        return

    user_id = callback.from_user.id
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        logging.info(f"User {user_id} not found, creating new user.")
        user = User(id=user_id, cart=[], state=UserState.MAIN_MENU.state)
        session.add(user)

    product = session.query(Product).filter_by(id=product_id).first()
    logging.info(f"Product fetched from DB in add_to_cart: {product}")

    if not product:
        logging.error(f"Product with ID {product_id} NOT found in database when adding to cart.")
        await callback.answer("Ошибка: Товар не найден.", show_alert=True)
        await edit_or_send_message(callback, text="Товар не найден. Возвращаю в главное меню.", reply_markup=main_menu())
        return

    found_in_cart = False
    temp_cart = list(user.cart)
    for item in temp_cart:
        if item["product_id"] == product_id:
            item["quantity"] += 1
            found_in_cart = True
            logging.info(f"Product {product_id} already in cart, incrementing quantity to {item['quantity']}")
            break
    if not found_in_cart:
        temp_cart.append({"product_id": product_id, "quantity": 1})
        logging.info(f"Product {product_id} not in cart, adding new item.")
    
    user.cart = temp_cart
    flag_modified(user, "cart")

    logging.info(f"Product {product.name} (ID: {product_id}) successfully added/updated in cart for user {user_id}.")
    await callback.answer(f"{product.name} добавлен в корзину!", show_alert=True)
    # После добавления в корзину, возвращаемся к просмотру этого же продукта
    await show_product_by_id(callback, state, session, product_id=product.id)

# Обработчик кнопки "Корзина"
@dp.callback_query(F.data == "menu:cart")
async def show_cart(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer()
    await show_cart_with_session(callback, state, session)

# Обработчик очистки корзины
@dp.callback_query(F.data == "cart:clear")
async def clear_cart(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer("Корзина очищена.", show_alert=True)
    user = session.query(User).filter_by(id=callback.from_user.id).first()
    if user:
        user.cart = []
        flag_modified(user, "cart")
    await edit_or_send_message(callback, text="Корзина очищена.", reply_markup=main_menu())

# Начало оформления заказа
@dp.callback_query(F.data == "cart:checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext, session: SessionType):
    await callback.answer()
    user = session.query(User).filter_by(id=callback.from_user.id).first()
    if not user or not user.cart:
        await callback.answer("Ваша корзина пуста! Нечего оформлять.", show_alert=True)
        await show_cart_with_session(callback, state, session)
        return
    await state.set_state(OrderStates.waiting_for_address)
    await edit_or_send_message(callback, text="Введите ваш адрес:", reply_markup=ReplyKeyboardRemove())

# Обработка введенного адреса
@dp.message(OrderStates.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(OrderStates.waiting_for_contact)
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Поделиться контактом", request_contact=True))
    await message.answer("Отправьте ваш контакт, нажав на кнопку 'Поделиться контактом':", reply_markup=kb.as_markup(resize_keyboard=True, one_time_keyboard=True))

# ОБНОВЛЕННЫЙ ОБРАБОТЧИК: для текстовых сообщений, когда ожидается контакт
@dp.message(OrderStates.waiting_for_contact, F.text)
async def handle_non_contact_in_order(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Поделиться контактом", request_contact=True))
    await message.answer("Пожалуйста, поделитесь своим контактом, нажав на кнопку ниже. Вводить текст не нужно.", reply_markup=kb.as_markup(resize_keyboard=True, one_time_keyboard=True))

# Обработка отправленного контакта и завершение заказа
@dp.message(OrderStates.waiting_for_contact, F.contact)
async def process_contact(message: types.Message, state: FSMContext, session: SessionType):
    try:
        await message.delete() 
    except Exception as e:
        logging.debug(f"Could not delete user's contact message: {e}")

    data = await state.get_data()
    user = session.query(User).filter_by(id=message.from_user.id).first()
    cart_items = user.cart if user else []
    cart_text = ""
    total = 0
    for item in cart_items:
        product = session.query(Product).filter_by(id=item["product_id"]).first()
        if product:
            cart_text += f"- {product.name} ({item['quantity']} шт.) - {product.price * item['quantity']} руб.\n"
            total += product.price * item["quantity"]
        else:
            cart_text += f"- Неизвестный товар (ID: {item['product_id']}) - {item['quantity']} шт.\n"

    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🔥 Новый заказ!\n"
                f"👤 Пользователь: @{message.from_user.username if message.from_user.username else message.from_user.full_name} (ID: {message.from_user.id})\n"
                f"📦 Адрес: {data['address']}\n"
                f"📱 Контакт: {message.contact.phone_number}\n"
                f"🛒 Корзина:\n{cart_text}\n"
                f"💵 Итого: {total} руб."
            )
        except Exception as e:
            logging.error(f"Failed to send order message to admin: {e}")
            await message.answer("Произошла ошибка при оформлении заказа. Пожалуйста, попробуйте позже.", reply_markup=ReplyKeyboardRemove())
            await message.answer("Главное меню:", reply_markup=main_menu())
            await state.clear()
            return

    await message.answer("Заказ оформлен! Мы свяжемся с вами в ближайшее время.", reply_markup=ReplyKeyboardRemove())
    await message.answer("Главное меню:", reply_markup=main_menu())
    await state.clear()

    if user:
        user.cart = []
        flag_modified(user, "cart")

# Обработчик кнопки "Назад"
@dp.callback_query(F.data.startswith("back:"))
async def back_from_product(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    back_callback = callback.data.split(":", 1)[1]
    if back_callback == "feed:cats":
        # Исправлено: передача сессии напрямую в обработчик, а не через data
        await cats_menu(callback, session=callback.bot.get('session')) 
    elif back_callback == "feed:dogs":
        # Исправлено: передача сессии напрямую в обработчик, а не через data
        await dogs_menu(callback, session=callback.bot.get('session')) 
    elif back_callback == "menu:feed_type":
        await feed_type_menu(callback, state)
    # Если захотите вернуть корм для ежей и попугаев, раскомментируйте эти строки:
    # elif back_callback == "feed:other":
    #     await other_menu(callback, session=callback.bot.get('session'))
    # elif back_callback == "feed:birds":
    #     await birds_menu(callback, session=callback.bot.get('session'))
    elif back_callback == "menu:main":
        await back_to_main_menu(callback, state)
    else:
        logging.warning(f"Unhandled back_callback: {back_callback}")
        await edit_or_send_message(callback, text="Ошибка возврата. Возвращаю в главное меню.", reply_markup=main_menu())

# --- ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ ДЛЯ ФУНКЦИИ "ПОМОЩЬ" ---

@dp.callback_query(F.data == "menu:help")
async def start_help_dialog(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserState.WAITING_FOR_HELP_MESSAGE)
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="Отмена"))
    await edit_or_send_message(
        callback,
        text="Напишите ваше сообщение, и мы обязательно вам ответим. Если хотите, чтобы мы связались с вами, можете также поделиться своим контактом. Для отмены нажмите 'Отмена'.",
        reply_markup=kb.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )

@dp.message(UserState.WAITING_FOR_HELP_MESSAGE, F.text)
async def process_help_message(message: types.Message, state: FSMContext, session: SessionType):
    if message.text == "Отмена":
        await state.set_state(UserState.MAIN_MENU)
        await message.answer("Диалог с помощью отменен.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Главное меню:", reply_markup=main_menu())
        return

    user_info = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    admin_message_text = (
        f"🆘 Сообщение от пользователя {user_info} (ID: {message.from_user.id}):\n\n"
        f"Текст сообщения: {message.text}"
    )
    
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_message_text)
            await message.answer("Ваше сообщение отправлено. Ожидайте ответа.", reply_markup=ReplyKeyboardRemove())
            await message.answer("Главное меню:", reply_markup=main_menu())
            await state.set_state(UserState.MAIN_MENU)
        except Exception as e:
            logging.error(f"Failed to send help message to admin: {e}")
            await message.answer("Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.", reply_markup=ReplyKeyboardRemove())
            await message.answer("Главное меню:", reply_markup=main_menu())
            await state.set_state(UserState.MAIN_MENU)
    else:
        await message.answer("Не удалось отправить сообщение администратору. Пожалуйста, попробуйте позже.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Главное меню:", reply_markup=main_menu())
        await state.set_state(UserState.MAIN_MENU)


@dp.message(UserState.WAITING_FOR_HELP_MESSAGE, F.contact)
async def process_help_contact(message: types.Message, state: FSMContext, session: SessionType):
    user_info = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    admin_message_text = (
        f"🆘 Запрос на обратную связь от пользователя {user_info} (ID: {message.from_user.id}):\n\n"
        f"Контакт: {message.contact.phone_number}\n"
        f"Имя: {message.contact.first_name} {message.contact.last_name if message.contact.last_name else ''}"
    )

    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_message_text)
            await message.answer("Ваш контакт отправлен. Мы свяжемся с вами.", reply_markup=ReplyKeyboardRemove())
            await message.answer("Главное меню:", reply_markup=main_menu())
            await state.set_state(UserState.MAIN_MENU)
        except Exception as e:
            logging.error(f"Failed to send help contact to admin: {e}")
            await message.answer("Произошла ошибка при отправке контакта. Пожалуйста, попробуйте позже.", reply_markup=ReplyKeyboardRemove())
            await message.answer("Главное меню:", reply_markup=main_menu())
            await state.set_state(UserState.MAIN_MENU)
    else:
        await message.answer("Не удалось отправить контакт администратору. Пожалуйста, попробуйте позже.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Главное меню:", reply_markup=main_menu())
        await state.set_state(UserState.MAIN_MENU)

# Глобальный echo-обработчик (должен быть в самом конце!)
@dp.message()
async def echo_all(message: types.Message):
    if message.text in ("Старт", "/start"):
        return
    await message.answer("Я получил ваше сообщение!")

# Запуск бота
async def main():
    logging.info("Starting bot main function...")
    try:
        # Устанавливаем сессию в контекст бота, чтобы она была доступна в обработчиках
        # Это нужно, если вы хотите получать сессию через callback.bot.get('session')
        # Хотя middleware уже добавляет ее в data, это может быть полезно для других сценариев.
        # dp.run_polling(bot) сам по себе запускает опрос и блокирует выполнение.
        # Если вы используете middleware, то session уже будет в data.
        # Для простоты и надежности, можно просто запустить polling здесь.
        logging.info("Attempting to start polling...")
        await dp.start_polling(bot)
        logging.info("Polling started successfully.")
    except Exception as e:
        logging.critical(f"Bot failed to start polling: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    logging.info("Running asyncio.run(main())...")
    # Регистрируем middleware здесь, до запуска polling
    # Это важно, чтобы middleware было активно с самого начала.
    # Если middleware уже зарегистрировано через @dp.update.middleware(),
    # то эта строка может быть избыточной, но не повредит.
    # dp.update.middleware(DbSessionMiddleware(session_factory=get_session)) # Эта строка не нужна, если уже есть декоратор

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user via KeyboardInterrupt.")
    except Exception as e:
        logging.error(f"An unexpected error occurred in main execution: {e}", exc_info=True)
    logging.info("asyncio.run(main()) finished. Exiting script.")
