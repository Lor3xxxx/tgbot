    # Вставьте сюда весь ваш код
    # Пожалуйста, вставьте сюда ваш полный код на Python.
import logging
import json
import asyncio
from typing import Optional, List

from aiogram import Bot, Dispatcher, types, F, Router
# В StateFilter добавлена явная проверка на состояние None для публичных хендлеров
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- CONFIGURATION ---
from config import TOKEN

async def safe_edit_message(call: types.CallbackQuery, text: str, reply_markup=None):
    """
    Универсально редактирует сообщение — без ошибок.
    """
    try:
        # пробуем редактировать как текст
        safe_edit_message(call, text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Игнорируем, если текст не изменился
            return
        elif "no text in the message to edit" in str(e):
            # Это фото — редактируем подпись
            try:
                await call.message.edit_caption(caption=text, reply_markup=reply_markup)
            except TelegramBadRequest:
                # Если всё равно ошибка — просто пересылаем новое сообщение
                await call.message.delete()
                await call.message.answer(text, reply_markup=reply_markup)
        else:
            # Любая другая ошибка — удаляем и отправляем новое
            await call.message.delete()
            await call.message.answer(text, reply_markup=reply_markup)

try:
    from security import ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_IDS
except ImportError:
    logging.error("⛔️ ОШИБКА: Не удалось импортировать модуль security.py. Используются заглушки.")
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin123"
    ADMIN_IDS = []

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ---------- File Storage Configuration ----------
REVIEWS_FILE = "reviews.json"
PRODUCTS_FILE = "products.json"
ADMIN_SESSIONS_FILE = "admin_sessions.json"
faqph = "png.png"

CARTS = {}
SNUS_BRANDS = ["KASTA", "LYFT", "DLTA", "DELUXE", "VELLO", "ICEBERG", "CORVUS", "HUSKY", "ТАБАК"]
DISPOSABLE_BRANDS = ["Waka", "Masking", "Elfbar", "HQD"]

# --- Initial Data (UPDATED STRUCTURE FOR DISPOSABLES) ---
DEFAULT_PRODUCTS = {
    "Одноразки": [
        # Теперь name - это только вкус. Бренд и Capacity - отдельные поля.
        {"name": "Вишня", "price": 1100, "brand": "Waka", "capacity": 6000, "available": True},
        {"name": "Арбуз", "price": 1100, "brand": "Waka", "capacity": 6000, "available": True},
        {"name": "Лед", "price": 2000, "brand": "Waka", "capacity": 10000, "available": True},
        {"name": "Тутти-Фрутти", "price": 1500, "brand": "Elfbar", "capacity": 5000, "available": True},
    ],
    "Жидкости": [
        {"name": "Juice 5%", "price": 700, "available": True}
    ],
    "Картриджи": [
        {"name": "Vaporesso", "price": 450, "available": True}
    ],
    "Снюс": []
}

REVIEWS = []
PRODUCTS = DEFAULT_PRODUCTS.copy()
ADMIN_SESSIONS = []

# Load Reviews (existing logic)
try:
    with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
        REVIEWS = json.load(f)
    logging.info(f"Reviews loaded from {REVIEWS_FILE}.")
except (FileNotFoundError, json.JSONDecodeError):
    logging.warning(f"Reviews file {REVIEWS_FILE} not found or corrupted. Starting with empty reviews.")

# Load Products (existing logic)
try:
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        PRODUCTS = json.load(f)
    logging.info(f"Products loaded from {PRODUCTS_FILE}. Total categories: {len(PRODUCTS)}")
except (FileNotFoundError, json.JSONDecodeError):
    PRODUCTS = DEFAULT_PRODUCTS.copy()
    try:
        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(PRODUCTS, f, ensure_ascii=False, indent=4)
        logging.info(f"Products file not found or corrupted. Using default list and creating {PRODUCTS_FILE}.")
    except Exception as e:
        logging.error(f"FATAL: Could not write initial {PRODUCTS_FILE}: {e}")

# Load Admin Sessions (NEW LOGIC)
try:
    with open(ADMIN_SESSIONS_FILE, "r", encoding="utf-8") as f:
        loaded_sessions = json.load(f)
        if isinstance(loaded_sessions, list):
            # Храним ID как строки
            ADMIN_SESSIONS.extend([str(s) for s in loaded_sessions])
    logging.info(f"Admin sessions loaded from {ADMIN_SESSIONS_FILE}. Total: {len(ADMIN_SESSIONS)}")
except (FileNotFoundError, json.JSONDecodeError):
    logging.warning(f"Admin sessions file {ADMIN_SESSIONS_FILE} not found or corrupted. Starting with empty list.")

# --- FAQ Text ---
FAQ_TEXT = (
    "🤗 Частые вопросы (FAQ):\n\n"
    "1. Как оформить заказ? - Просто выберите товары в каталоге, перейдите в корзину и нажмите 'Оформить заказ' 📦\n"
    "2. Оплата и доставка? - Все детали мы обсудим с вами индивидуально после оформления заказа 💳\n"
    "3. Есть вопросы? - Наш менеджер всегда на связи и готов помочь! 💬\n\n"
    "📞 Связь с менеджером: @egogogl"
)


# --- Asynchronous File Helpers ---
async def save_reviews_async():
    try:
        await asyncio.to_thread(
            lambda: json.dump(REVIEWS, open(REVIEWS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
        )
        logging.info("Reviews successfully saved to file.")
    except Exception as e:
        logging.error(f"!!! CRITICAL ERROR: Error saving reviews to {REVIEWS_FILE}: {e}")


async def save_products_async():
    try:
        await asyncio.to_thread(
            lambda: json.dump(PRODUCTS, open(PRODUCTS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
        )
        logging.info("Products successfully saved to file.")
    except Exception as e:
        logging.error(f"!!! CRITICAL ERROR: Error saving products to {PRODUCTS_FILE}: {e}")


async def save_sessions_async():
    try:
        await asyncio.to_thread(
            lambda: json.dump(ADMIN_SESSIONS, open(ADMIN_SESSIONS_FILE, "w", encoding="utf-8"), ensure_ascii=False,
                              indent=4)
        )
        logging.info("Admin sessions successfully saved to file.")
    except Exception as e:
        logging.error(f"!!! CRITICAL ERROR: Error saving sessions to {ADMIN_SESSIONS_FILE}: {e}")


# --- Authentication Helper ---
async def check_admin_auth(state: FSMContext, call_or_message: types.CallbackQuery | types.Message) -> bool:
    user_id = str(call_or_message.from_user.id)

    # 1. Проверяем FSM контекст (временная сессия)
    data = await state.get_data()
    is_auth_fsm = data.get("is_authenticated", False)

    # 2. Проверяем постоянную сессию (сохраненный ID в файле)
    is_auth_persistent = user_id in ADMIN_SESSIONS

    is_auth = is_auth_fsm or is_auth_persistent

    if not is_auth:
        if isinstance(call_or_message, types.CallbackQuery):
            await call_or_message.answer("⛔️ Доступ запрещен. Войдите с помощью /admin.", show_alert=True)
        else:
            await call_or_message.answer("⛔️ Доступ запрещен. Войдите с помощью /admin.")
        return False

    # Если вход произошел через постоянную сессию, убеждаемся, что FSM контекст тоже обновлен
    if is_auth_persistent and not is_auth_fsm:
        await state.update_data(is_authenticated=True)

    return True


# --- Data Helpers ---
def get_product_details_by_index(category: str, index: int) -> dict | None:
    category_products = PRODUCTS.get(category)
    if category_products and 0 <= index < len(category_products):
        return category_products[index]
    return None


# Унифицированная функция для подсчета товаров по бренду (и опционально по capacity)
def get_product_count(category: str, brand: str = None, capacity: Optional[int] = None) -> int:
    category_products = PRODUCTS.get(category)
    if not category_products:
        return 0

    count = 0
    for product in category_products:
        if not product.get('available', False):
            continue

        brand_match = True
        if brand and product.get('brand', '').upper() != brand.upper():
            brand_match = False

        capacity_match = True
        if capacity is not None and product.get('capacity') != capacity:
            capacity_match = False

        if brand_match and capacity_match:
            count += 1
    return count


def trim_product_name(product_name: str, category_name: str) -> str:
    # Оставляем оригинальный trim для снюса/жидкостей, где название может содержать категорию
    cat_lower = category_name.lower()
    name_lower = product_name.lower()

    if name_lower.startswith(cat_lower):
        trim_len = len(cat_lower)
        if len(product_name) == trim_len:
            return product_name
        if len(product_name) > trim_len and product_name[trim_len].isspace():
            trimmed = product_name[trim_len:].lstrip()
            return trimmed if trimmed else product_name
    return product_name


def get_normalized_cat_id(category: str) -> str:
    return category.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')


def get_original_cat_name(normalized_id: str) -> str | None:
    for cat in PRODUCTS.keys():
        if get_normalized_cat_id(cat) == normalized_id:
            return cat
    return None


# --- Callback Data Factories ---
class MenuCallback(CallbackData, prefix="menu"):
    action: str


class CategoryCallback(CallbackData, prefix="cat"):
    action: str
    category_id: str


class SnusBrandCallback(CallbackData, prefix="sbrand"):
    brand: str


class DisposableBrandCallback(CallbackData, prefix="dbrand"):
    brand: str


# NEW: Для выбора количества затяжек
class PuffCallback(CallbackData, prefix="puff"):
    brand: str
    capacity: int


class ProductCallback(CallbackData, prefix="prod"):
    action: str
    category_id: str
    product_index: int


class ReviewCallback(CallbackData, prefix="review"):
    action: str
    value: Optional[int] = None


class AdminAuthCallback(CallbackData, prefix="admin_auth"):
    action: str


# ---------- FSM (States) ----------
class ReviewStates(StatesGroup):
    waiting_rating = State()
    waiting_text = State()


class AdminStates(StatesGroup):
    waiting_new_category = State()
    waiting_new_name = State()  # Для всех товаров, это либо полное имя, либо ВКУС для одноразок
    waiting_new_strength = State()  # Только для Снюса
    waiting_new_brand = State()  # Для Снюса и Одноразок
    waiting_new_capacity = State()  # Только для Одноразок
    waiting_new_price = State()


class AdminLoginStates(StatesGroup):
    waiting_username = State()
    waiting_password = State()


# NEW: Состояния для процесса оформления заказа
class CheckoutStates(StatesGroup):
    waiting_delivery_method = State()
    waiting_address_phone = State()


# ---------- Keyboards ----------
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📦 Каталог товаров", callback_data=MenuCallback(action='catalog').pack()),
        InlineKeyboardButton(text="🛒 Корзина", callback_data=MenuCallback(action='view_cart').pack())
    )
    kb.row(
        InlineKeyboardButton(text="📲 Связь", url="https://t.me/egogogl"),
        InlineKeyboardButton(text="📝 Отзывы", callback_data=MenuCallback(action='reviews_menu').pack())
    )
    # НОВОЕ: Кнопка "Наш канал"
    kb.row(
        InlineKeyboardButton(text="🚀 Наш канал @lor3xvapes", url="https://t.me/lor3xvapes"),
        InlineKeyboardButton(text="❓ Вопросы / FAQ", callback_data=MenuCallback(action='questions').pack())
    )
    return kb.as_markup()


def admin_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Добавить товар",
                                callback_data=MenuCallback(action='admin_add_product_start').pack()))
    kb.row(InlineKeyboardButton(text="🔧 Управлять наличием",
                                callback_data=MenuCallback(action='admin_manage_availability_start').pack()))
    kb.row(
        InlineKeyboardButton(text="🗑️ Удалить товар", callback_data=MenuCallback(action='admin_delete_start').pack()))
    kb.row(InlineKeyboardButton(text="🚪 Выйти из админки", callback_data=AdminAuthCallback(action='logout').pack()))
    kb.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data=MenuCallback(action='back_main').pack()))
    return kb.as_markup()


def catalog_menu():
    kb = InlineKeyboardBuilder()
    for cat in PRODUCTS.keys():
        normalized_id = get_normalized_cat_id(cat)
        kb.button(text=cat, callback_data=CategoryCallback(action='view', category_id=normalized_id).pack())
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data=MenuCallback(action='back_main').pack()))
    return kb.as_markup()


def snus_brands_menu():
    kb = InlineKeyboardBuilder()
    category = "Снюс"
    for brand in SNUS_BRANDS:
        count = get_product_count(category, brand=brand)  # Используем новую унифицированную функцию
        status_text = f"✅ ({count} шт.)" if count > 0 else "❌"
        kb.button(
            text=f"🔥 {brand} {status_text}",
            callback_data=SnusBrandCallback(brand=brand).pack()
        )
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data=MenuCallback(action='catalog').pack()))
    return kb.as_markup()


def disposable_brands_menu():
    kb = InlineKeyboardBuilder()
    category = "Одноразки"
    for brand in DISPOSABLE_BRANDS:
        count = get_product_count(category, brand=brand)  # Используем новую унифицированную функцию
        status_text = f"✅ ({count} шт.)" if count > 0 else "❌"
        kb.button(
            text=f"💨 {brand} {status_text}",
            callback_data=DisposableBrandCallback(brand=brand).pack()
        )
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data=MenuCallback(action='catalog').pack()))
    return kb.as_markup()


# NEW: Для выбора количества затяжек
def disposable_capacity_menu(brand: str, capacities: List[int]):
    kb = InlineKeyboardBuilder()
    category = "Одноразки"

    for capacity in sorted(capacities, reverse=True):
        count = get_product_count(category, brand=brand, capacity=capacity)
        status_text = f"✅ ({count} вкусов)" if count > 0 else "❌"
        kb.button(
            text=f"💨 {capacity} затяжек {status_text}",
            callback_data=PuffCallback(brand=brand, capacity=capacity).pack()
        )

    kb.adjust(1)

    # Кнопка назад возвращает к выбору бренда
    back_data = CategoryCallback(action='view', category_id=get_normalized_cat_id(category)).pack()
    kb.row(InlineKeyboardButton(text="⬅️ Назад к брендам", callback_data=back_data))
    return kb.as_markup()


def products_menu(category: str, brand_filter: str = None, capacity_filter: Optional[int] = None,
                  back_callback_data: str = None):
    kb = InlineKeyboardBuilder()
    normalized_cat_id = get_normalized_cat_id(category)
    filtered_products = []

    for item in PRODUCTS.get(category, []):

        # 1. Фильтр по бренду
        if brand_filter:
            if item.get('brand', '').upper() != brand_filter.upper():
                continue

        # 2. Фильтр по затяжкам (только для одноразок)
        if capacity_filter is not None:
            if item.get('capacity') != capacity_filter:
                continue

        # Собираем только отфильтрованные товары
        filtered_products.append(item)

    # После фильтрации нужно найти индекс, чтобы правильно добавить в корзину
    # NOTE: Это потенциально медленно, но необходимо для сохранения структуры корзины
    for item in filtered_products:
        # Находим оригинальный индекс товара в общем списке категории
        try:
            product_index = PRODUCTS.get(category).index(item)
        except ValueError:
            logging.error(f"Product {item} not found in original list for {category}")
            continue

        # 3. Форматирование отображаемого имени
        # Если есть фильтр по capacity, значит это финальный список вкусов, и имя = name (вкус)
        if capacity_filter is not None:
            # name для одноразок - это только вкус
            display_name = item['name']
        else:
            # Для Снюса или других категорий, где нет capacity-фильтра
            base_name = trim_product_name(item['name'], category)
            display_name = base_name

            if category == "Снюс":
                # ИСПРАВЛЕНО: Для Снюса убрано повторное отображение бренда
                if 'strength' in item:
                    strength_part = f" ({item.get('strength', 'Н/Д')})"
                    display_name += strength_part
            elif 'strength' in item:
                display_name = f"{base_name} ({item['strength']})"

        # 4. Добавление кнопки
        # Упрощенное отображение статуса наличия
        status_emoji = "✅" if item.get('available', True) else "❌"

        kb.button(
            text=f"{status_emoji} {display_name} — {item['price']} сом",
            callback_data=ProductCallback(action='add', category_id=normalized_cat_id,
                                          product_index=product_index).pack()  # Используем оригинальный индекс
        )

    kb.adjust(1)
    if back_callback_data:
        kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback_data))
    kb.row(InlineKeyboardButton(text="🛒 Корзина", callback_data=MenuCallback(action='view_cart').pack()))
    return kb.as_markup()


def admin_categories_kb(action_type: str):
    kb = InlineKeyboardBuilder()
    for cat in PRODUCTS.keys():
        normalized_id = get_normalized_cat_id(cat)
        kb.button(text=cat, callback_data=CategoryCallback(action=action_type, category_id=normalized_id).pack())
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ Назад в Админ-меню", callback_data=MenuCallback(action='admin_menu').pack()))
    return kb.as_markup()


def admin_product_list_kb(category: str):
    kb = InlineKeyboardBuilder()
    normalized_cat_id = get_normalized_cat_id(category)

    for i, item in enumerate(PRODUCTS.get(category, [])):
        # Упрощенный статус наличия
        status_emoji = "✅" if item.get('available', True) else "❌"
        display_name = item['name']

        # Унифицированная логика отображения для админки
        if category == "Снюс":
            brand_part = f" [{item.get('brand', 'БЕЗ БРЕНДА')}]"
            strength_part = f" ({item.get('strength', 'Н/Д')})"
            display_name = f"{item['name']}{brand_part}{strength_part}"
        elif category == "Одноразки":
            # Для одноразок отображаем Бренд + Затяжки + Вкус (name)
            brand_part = item.get('brand', 'БЕЗ БРЕНДА')
            capacity_part = item.get('capacity', 'Н/Д')
            display_name = f"{brand_part} {capacity_part} | Вкус: {item['name']}"
        elif 'strength' in item:
            display_name = f"{item['name']} ({item['strength']})"

        kb.button(
            text=f"{status_emoji} | {display_name} ({item['price']} сом)",
            callback_data=ProductCallback(action='toggle', category_id=normalized_cat_id, product_index=i).pack()
        )

    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Назад к категориям",
                                callback_data=MenuCallback(action='admin_manage_availability_start').pack()))
    return kb.as_markup()


def admin_product_list_kb_delete(category: str):
    kb = InlineKeyboardBuilder()
    normalized_cat_id = get_normalized_cat_id(category)

    for i, item in enumerate(PRODUCTS.get(category, [])):
        display_name = item['name']

        # Унифицированная логика отображения для админки (для удаления)
        if category == "Снюс":
            brand_part = f" [{item.get('brand', 'БЕЗ БРЕНДА')}]"
            strength_part = f" ({item.get('strength', 'Н/Д')})"
            display_name = f"{item['name']}{brand_part}{strength_part}"
        elif category == "Одноразки":
            # Для одноразок отображаем Бренд + Затяжки + Вкус (name)
            brand_part = item.get('brand', 'БЕЗ БРЕНДА')
            capacity_part = item.get('capacity', 'Н/Д')
            display_name = f"{brand_part} {capacity_part} | Вкус: {item['name']}"
        elif 'strength' in item:
            display_name = f"{item['name']} ({item['strength']})"

        kb.button(
            text=f"❌ УДАЛИТЬ: {display_name} ({item['price']} сом)",
            callback_data=ProductCallback(action='delete', category_id=normalized_cat_id, product_index=i).pack()
        )

    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Назад к категориям",
                                callback_data=MenuCallback(action='admin_delete_start').pack()))
    return kb.as_markup()


def admin_snus_brands_kb():
    kb = InlineKeyboardBuilder()
    for brand in SNUS_BRANDS:
        kb.button(text=brand, callback_data=SnusBrandCallback(brand=brand).pack())
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack()))
    return kb.as_markup()


def admin_disposable_brands_kb():
    kb = InlineKeyboardBuilder()
    for brand in DISPOSABLE_BRANDS:
        kb.button(text=brand, callback_data=DisposableBrandCallback(brand=brand).pack())
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack()))
    return kb.as_markup()


def reviews_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🌟 Оставить отзыв", callback_data=ReviewCallback(action='leave').pack()),
        InlineKeyboardButton(text="📄 Посмотреть все отзывы", callback_data=ReviewCallback(action='view').pack())
    )
    kb.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data=MenuCallback(action='back_main').pack()))
    return kb.as_markup()


def reviews_filter_kb():
    kb = InlineKeyboardBuilder()
    for rating in range(5, 0, -1):
        stars = '⭐' * rating
        kb.row(InlineKeyboardButton(
            text=f"Показать {stars} отзывы",
            callback_data=ReviewCallback(action='filter', value=rating).pack()
        ))
    kb.row(
        InlineKeyboardButton(text="⬅️ Назад в меню отзывов", callback_data=MenuCallback(action='reviews_menu').pack()))
    return kb.as_markup()


def rating_menu():
    kb = InlineKeyboardBuilder()
    for rating in range(1, 6):
        stars = '⭐' * rating
        kb.row(InlineKeyboardButton(text=f"{stars} ({rating} из 5)",
                                    callback_data=ReviewCallback(action='rate', value=rating).pack()))
    kb.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data=MenuCallback(action='back_main').pack()))
    return kb.as_markup()


def view_cart_kb(user_id: str):
    kb = InlineKeyboardBuilder()
    cart = CARTS.get(user_id, [])

    grouped_cart = {}
    for item in cart:
        key = (item['name'], item['cat_id'], item['prod_idx'])
        grouped_cart.setdefault(key, {'qty': 0, 'category': item['category']})
        grouped_cart[key]['qty'] += item['qty']

    for (name, cat_id, prod_idx), data in grouped_cart.items():
        kb.button(
            text=f"❌ Удалить {name} (1 шт.)",
            callback_data=ProductCallback(action='remove_by_id', category_id=cat_id, product_index=prod_idx).pack()
        )

    if cart:
        kb.row(InlineKeyboardButton(text="✅ Оформить заказ", callback_data=MenuCallback(action='checkout').pack()))
        kb.row(InlineKeyboardButton(text="🗑️ Очистить корзину", callback_data=MenuCallback(action='clear_cart').pack()))

    kb.row(
        InlineKeyboardButton(text="⬅️ Каталог", callback_data=MenuCallback(action='catalog').pack()),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCallback(action='back_main').pack())
    )
    kb.adjust(1)
    return kb.as_markup()


# NEW: Клавиатура для выбора доставки
def delivery_options_kb():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="🚗 Yandex Доставка (Предоплата)",
        callback_data=MenuCallback(action='delivery_yandex').pack()
    ))
    kb.row(InlineKeyboardButton(
        text="🚶 Личный Курьер (300-400 сом, Оплата при получении)",
        callback_data=MenuCallback(action='delivery_courier').pack()
    ))
    kb.row(InlineKeyboardButton(
        text="✈️ В Регионы (300 сом, Предоплата)",
        callback_data=MenuCallback(action='delivery_regions').pack()
    ))
    kb.row(InlineKeyboardButton(text="⬅️ Назад в корзину", callback_data=MenuCallback(action='view_cart').pack()))
    kb.adjust(1)
    return kb.as_markup()


# --- Основные хендлеры ---
@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    try:
        await state.clear()
        user_id = str(message.from_user.id)

        # NEW: Если ID пользователя есть в списке ADMIN_SESSIONS, сразу даем доступ
        if user_id in ADMIN_SESSIONS:
            await state.update_data(is_authenticated=True)
            user_name = message.from_user.first_name or "Администратор"
            await message.answer(
                f"👋 С возвращением, {user_name}! ✨\n"
                "Ваша сессия активна. Выберите действие в Админ-меню.",
                reply_markup=admin_menu_kb()
            )
            return

            # Оригинальная логика для обычного пользователя
        user_name = message.from_user.first_name or "дорогой друг"
        await message.answer(
            f"👋 Привет-привет, {user_name}! ✨\n"
            "Я ваш помощник по заказу товаров. Моя миссия — сделать ваш выбор лёгким и весёлым! 😊\n"
            "Выберите действие в меню.",
            reply_markup=main_menu()
        )
    except Exception as e:
        logging.error(f"Error in start_cmd: {e}")
        await message.answer("❌ Произошла ошибка при загрузке главного меню. Попробуйте позже.")


@router.message(Command("admin"))
async def admin_login_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)

    # 1. Проверка FSM контекста
    if (await state.get_data()).get("is_authenticated", False):
        await message.answer("🔑 Вы уже вошли в админ-панель:", reply_markup=admin_menu_kb())
        return

    # 2. NEW: Проверка постоянной сессии
    if user_id in ADMIN_SESSIONS:
        await state.update_data(is_authenticated=True)
        await state.set_state(None)
        await message.answer(
            "🔑 Сессия найдена. Добро пожаловать в Админ-панель.",
            reply_markup=admin_menu_kb()
        )
        return

        # Если сессии нет, начинаем стандартный процесс входа
    await message.answer(
        "🔐 Вход в панель администратора\n"
        f"Введите логин (Username). Подсказка: `{ADMIN_USERNAME}`"
    )
    await state.set_state(AdminLoginStates.waiting_username)


@router.message(AdminLoginStates.waiting_username)
async def admin_login_username(message: types.Message, state: FSMContext):
    username_input = message.text.strip()

    if username_input == ADMIN_USERNAME:
        await state.update_data(login_attempt=username_input)
        await message.answer("✅ Логин принят. Введите пароль (Password):")
        await state.set_state(AdminLoginStates.waiting_password)
    else:
        await message.answer("❌ Неверный логин. Попробуйте снова или нажмите /start для выхода.")


@router.message(AdminLoginStates.waiting_password)
async def admin_login_password(message: types.Message, state: FSMContext):
    password_input = message.text.strip()
    data = await state.get_data()
    username_attempt = data.get("login_attempt")
    user_id = str(message.from_user.id)

    if password_input == ADMIN_PASSWORD and username_attempt == ADMIN_USERNAME:
        await state.update_data(is_authenticated=True)
        await state.set_state(None)

        # NEW: Сохраняем ID пользователя в список постоянных сессий и записываем файл
        if user_id not in ADMIN_SESSIONS:
            ADMIN_SESSIONS.append(user_id)
            await save_sessions_async()

        await message.answer(
            f"🎉 Вход успешен! Добро пожаловать в Админ-панель. Сессия сохранена.",
            reply_markup=admin_menu_kb()
        )
    else:
        await state.clear()
        await message.answer("❌ Неверный пароль. Доступ запрещен.")


@router.callback_query(AdminAuthCallback.filter(F.action == "logout"))
async def admin_logout_handler(call: types.CallbackQuery, state: FSMContext):
    user_id = str(call.from_user.id)

    # NEW: Удаляем ID пользователя из списка постоянных сессий и записываем файл
    if user_id in ADMIN_SESSIONS:
        ADMIN_SESSIONS.remove(user_id)
        await save_sessions_async()

    await call.answer("Вы вышли из админ-панели. Сессия сброшена.")
    await state.update_data(is_authenticated=False)
    await state.clear()

    safe_edit_message(call=call , text = "🔒 Вы вышли из админ-панели. Главное меню:", reply_markup=main_menu())


@router.callback_query(MenuCallback.filter(F.action == "back_main"))
async def back_to_main_menu(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()

    user_id = str(call.from_user.id)

    # NEW: Если ID пользователя есть в списке ADMIN_SESSIONS, сразу перенаправляем в админку
    if user_id in ADMIN_SESSIONS:
        await state.update_data(is_authenticated=True)
        safe_edit_message(call= call, text="🏠 Вы в главном меню. Перенаправление в Админ-панель:",
                                     reply_markup=admin_menu_kb())
        return

    safe_edit_message(call=call, text="🏠 Вы в главном меню. Выберите действие:", reply_markup=main_menu())


# --- Каталог и корзина ---
@router.callback_query(MenuCallback.filter(F.action == "catalog"))
async def catalog_handler(call: types.CallbackQuery):
    await call.answer()
    safe_edit_message(call=call, text="Выберите категорию:", reply_markup=catalog_menu())


@router.callback_query(CategoryCallback.filter(F.action == "view"))
async def category_handler(call: types.CallbackQuery, callback_data: CategoryCallback):
    await call.answer()
    category = get_original_cat_name(callback_data.category_id)

    if not category:
        await call.answer("Неизвестная категория.", show_alert=True)
        return

    if category == "Снюс":
        safe_edit_message(call=call, text=f"💪 {category}\nВыберите бренд:", reply_markup=snus_brands_menu())
    elif category == "Одноразки":
        # Одноразки теперь ведут на выбор бренда
        (f"💨 {category}\nВыберите бренд:", reply_markup=disposable_brands_menu())
    else:
        # Для категорий без брендов
        await call.message.edit_text(
            f"📦 Товары категории: {category}",
            reply_markup=products_menu(
                category=category,
                brand_filter=None,
                back_callback_data=MenuCallback(action='catalog').pack()
            )
        )


# 🔥 ИСПРАВЛЕНИЕ: Добавлен StateFilter(None).
@router.callback_query(StateFilter(None), SnusBrandCallback.filter())
async def snus_brand_products_handler(call: types.CallbackQuery, callback_data: SnusBrandCallback):
    await call.answer()
    brand = callback_data.brand
    category = "Снюс"

    available_count = get_product_count(category, brand=brand)  # Используем новую унифицированную функцию

    if not available_count:
        text = f"❌ Нет доступных товаров бренда {brand}."
        back_data = CategoryCallback(action='view', category_id=get_normalized_cat_id(category)).pack()
        await call.message.edit_text(
            text,
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_data)).as_markup()
        )
        return

    text = f"🔥 Товары бренда {brand}"

    back_data = CategoryCallback(action='view', category_id=get_normalized_cat_id(category)).pack()
    await call.message.edit_text(
        text,
        # Передаем только бренд-фильтр
        reply_markup=products_menu(category=category, brand_filter=brand, back_callback_data=back_data)
    )


# 🔥 ИСПРАВЛЕНИЕ: Добавлен StateFilter(None). Теперь ведет на выбор затяжек.
@router.callback_query(StateFilter(None), DisposableBrandCallback.filter())
async def disposable_brand_products_handler(call: types.CallbackQuery, callback_data: DisposableBrandCallback):
    await call.answer()
    brand = callback_data.brand
    category = "Одноразки"

    # 1. Собираем все уникальные значения capacity для этого бренда
    all_brand_items = PRODUCTS.get(category, [])

    # Фильтруем по бренду, доступности и убеждаемся, что capacity существует и является числом
    capacities = set(
        item['capacity']
        for item in all_brand_items
        if item.get('brand', '').upper() == brand.upper()
        and item.get('available', True)
        and isinstance(item.get('capacity'), int)  # <- ДОБАВЛЕНО: Защита от отсутствия ключа 'capacity'
    )

    if not capacities:
        text = f"❌ Нет доступных товаров бренда {brand}."
        back_data = CategoryCallback(action='view', category_id=get_normalized_cat_id(category)).pack()
        await call.message.edit_text(
            text,
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_data)).as_markup()
        )
        return

    text = f"💨 Выбран бренд {brand}. Выберите количество затяжек:"

    await call.message.edit_text(
        text,
        reply_markup=disposable_capacity_menu(brand, list(capacities))
    )


# NEW: Хендлер для выбора количества затяжек (Capacity)
@router.callback_query(StateFilter(None), PuffCallback.filter())
async def puff_capacity_products_handler(call: types.CallbackQuery, callback_data: PuffCallback):
    await call.answer()
    brand = callback_data.brand
    capacity = callback_data.capacity
    category = "Одноразки"

    available_count = get_product_count(category, brand=brand, capacity=capacity)

    if not available_count:
        await call.answer(f"❌ Нет доступных вкусов для {brand} {capacity}.", show_alert=True)
        # Возвращаем на меню выбора затяжек (повторно)
        back_data = DisposableBrandCallback(brand=brand).pack()
        # Для возврата на предыдущее меню, нужно повторно вызвать хендлер, который его строит:
        # NOTE: В данном случае, нужно вызвать функцию, которая строит меню capacity,
        # но так как это сложно, я просто возвращаю на меню выбора бренда.
        await disposable_brand_products_handler(call, DisposableBrandCallback(brand=brand))
        return

    # Back button goes to the capacity selection menu
    back_data = DisposableBrandCallback(brand=brand).pack()

    # Теперь вызываем products_menu с двумя фильтрами: brand и capacity
    await call.message.edit_text(
        f"💨 {brand} {capacity} затяжек.\n\nВыберите вкус:",
        reply_markup=products_menu(
            category=category,
            brand_filter=brand,
            capacity_filter=capacity,
            back_callback_data=back_data
        )
    )


@router.callback_query(ProductCallback.filter(F.action == "add"))
async def add_to_cart_handler(call: types.CallbackQuery, callback_data: ProductCallback):
    user_id = str(call.from_user.id)
    category = get_original_cat_name(callback_data.category_id)
    product_index = callback_data.product_index

    if not category:
        await call.answer("Ошибка: не удалось найти категорию.", show_alert=True)
        return

    details = get_product_details_by_index(category, product_index)

    if not details:
        await call.answer("Продукт не найден.", show_alert=True)
        return

    # Унифицированная логика отображения имени для корзины
    display_name = details['name']

    if category == "Снюс":
        brand_part = f" [{details.get('brand', '')}]"
        strength_part = f" ({details.get('strength', 'Н/Д')})"
        display_name = f"{details['name']}{brand_part}{strength_part}"
    elif category == "Одноразки":
        # В корзине должно быть полное имя
        brand_part = details.get('brand', '')
        capacity_part = details.get('capacity', 'Н/Д')
        display_name = f"{brand_part} {capacity_part} | Вкус: {details['name']}"
    elif 'strength' in details:
        display_name = f"{details['name']} ({details['strength']})"

    if details.get('available', True):
        CARTS.setdefault(user_id, []).append({
            "name": display_name,
            "price": details['price'],
            "qty": 1,
            "category": category,
            "cat_id": callback_data.category_id,
            "prod_idx": product_index
        })
        await call.answer(f"✅ {display_name} добавлен в корзину")
    else:
        await call.answer("❌ Этот товар временно недоступен", show_alert=True)


@router.callback_query(MenuCallback.filter(F.action == "view_cart"))
async def view_cart_handler(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)
    cart = CARTS.get(user_id, [])

    if not cart:
        text = "🛒 Ваша корзина пуста."
    else:
        total_price = sum(item['price'] * item['qty'] for item in cart)
        grouped_cart = {}
        for item in cart:
            key = (item['name'], item['price'], item.get('cat_id'), item.get('prod_idx'))
            grouped_cart.setdefault(key, {'qty': 0, 'category': item['category']})
            grouped_cart[key]['qty'] += item['qty']

        items_list = []
        for (name, price, _, _), data in grouped_cart.items():
            qty = data['qty']
            items_list.append(f"🔸 {name} (x{qty}) - {price * qty} сом")

        text = (
            "🛒 Ваша корзина:\n"
            f"{'—' * 20}\n"
            f"{'\n'.join(items_list)}\n"
            f"{'—' * 20}\n"
            f"ИТОГО: {total_price} сом"
        )

    # Удаляем старое сообщение
    await call.message.delete()

    # Отправляем новое сообщение с картинкой
    photo = FSInputFile("images/korz.png")  # путь к твоему фото
    await call.message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=view_cart_kb(user_id)
    )


@router.callback_query(ProductCallback.filter(F.action == "remove_by_id"))
async def remove_from_cart_by_id_handler(call: types.CallbackQuery, callback_data: ProductCallback):
    user_id = str(call.from_user.id)
    target_cat_id = callback_data.category_id
    target_prod_idx = callback_data.product_index

    if user_id in CARTS:
        cart_list = CARTS[user_id]
        try:
            # Ищем с конца, чтобы удалить последнюю добавленную единицу
            index_to_remove = next(i for i in reversed(range(len(cart_list)))
                                   if cart_list[i].get('cat_id') == target_cat_id and cart_list[i].get(
                'prod_idx') == target_prod_idx)
            product_name = cart_list[index_to_remove]['name']
            del cart_list[index_to_remove]
            await call.answer(f"➖ Один {product_name} удален.")
            await view_cart_handler(call)
        except StopIteration:
            await call.answer("Товар не найден в корзине.", show_alert=False)
    else:
        await call.answer("Корзина пуста.", show_alert=False)


@router.callback_query(MenuCallback.filter(F.action == "clear_cart"))
async def clear_cart_handler(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    if user_id in CARTS:
        del CARTS[user_id]
        await call.answer("🗑️ Корзина очищена.", show_alert=False)
    await view_cart_handler(call)


# --- НОВЫЙ ХЕНДЛЕР: НАЧАЛО ОФОРМЛЕНИЯ ЗАКАЗА И ВЫБОР ДОСТАВКИ ---
@router.callback_query(MenuCallback.filter(F.action == "checkout"))
async def checkout_start_handler(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    user_id = str(call.from_user.id)
    cart = CARTS.get(user_id, [])

    if not cart:
        await call.message.edit_text("Ваша корзина пуста. Нечего оформлять.", reply_markup=main_menu())
        return

    # Calculate and prepare cart summary for storage
    total_price = sum(item['price'] * item['qty'] for item in cart)

    grouped_cart_summary = []
    grouped_cart = {}
    for item in cart:
        # Grouping by name and price for display purposes
        key = (item['name'], item['price'])
        grouped_cart.setdefault(key, 0)
        grouped_cart[key] += item['qty']

    for (name, price), qty in grouped_cart.items():
        grouped_cart_summary.append(f" - {name} (x{qty}) - {price * qty} сом")

    cart_summary_text = '\n'.join(grouped_cart_summary)

    # Store cart summary and total price in state
    await state.update_data(
        checkout_cart_summary=cart_summary_text,
        checkout_total_price=total_price,
        checkout_cart=cart
    )

    text = (
        "🚚 **Выберите способ доставки:**\n\n"
        "1. **Yandex Доставка**: Намного быстрее и дешевле, но требуется оплата заранее.\n"
        "2. **Личный Курьер**: Ожидание побольше, цена фиксированная (300-400 сом). Оплата возможна при получении.\n"
        "3. **В Регионы**: Цена фиксированная (300 сом). Требуется оплата заранее."
    )

    await call.message.edit_text(text, reply_markup=delivery_options_kb(), parse_mode="Markdown")
    await state.set_state(CheckoutStates.waiting_delivery_method)


# --- НОВЫЙ ХЕНДЛЕР: ВЫБОР СПОСОБА ДОСТАВКИ ---
@router.callback_query(CheckoutStates.waiting_delivery_method, MenuCallback.filter(F.action.startswith("delivery_")))
async def delivery_method_handler(call: types.CallbackQuery, state: FSMContext, callback_data: MenuCallback):
    await call.answer()

    delivery_method = ""
    if callback_data.action == 'delivery_yandex':
        delivery_method = "Yandex Доставка (Предоплата)"
    elif callback_data.action == 'delivery_courier':
        delivery_method = "Личный Курьер (300-400 сом, Оплата при получении)"
    elif callback_data.action == 'delivery_regions':
        delivery_method = "В Регионы (300 сом, Предоплата)"

    if not delivery_method:
        await call.answer("Произошла ошибка выбора.", show_alert=True)
        return

    await state.update_data(delivery_method=delivery_method)

    prompt = (
        f"✅ Вы выбрали: **{delivery_method}**\n\n"
        "➡️ **Пожалуйста, введите ваш полный адрес и номер телефона.**\n\n"
        "**Пример формата:**\n"
        "`ул. Пушкина, дом 5, кв. 12, подъезд 3`\n"
        "`+996 555 123456`\n"
        "\n_Ваш менеджер свяжется с вами по указанному номеру._"
    )

    await call.message.edit_text(prompt, parse_mode="Markdown")
    await state.set_state(CheckoutStates.waiting_address_phone)


# --- НОВЫЙ ХЕНДЛЕР: ВВОД АДРЕСА И ТЕЛЕФОНА И ФИНАЛЬНАЯ ОТПРАВКА ---
@router.message(CheckoutStates.waiting_address_phone, F.text)
async def address_phone_handler(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Ввод не может быть пустым. Пожалуйста, введите полный адрес и номер телефона.")
        return

    contact_info = message.text.strip()

    if len(contact_info) < 10 or len(contact_info.split('\n')) < 2:  # Простая проверка на минимальный объем данных
        await message.answer("⚠️ Пожалуйста, введите полный адрес и номер телефона в формате, где они разделены переносом строки (или хотя бы минимальный набор данных).")
        return

    data = await state.get_data()
    cart_summary_text = data.get("checkout_cart_summary", "Нет данных о товарах.")
    total_price = data.get("checkout_total_price", 0)
    delivery_method = data.get("delivery_method", "Не указан")

    # ------------------ Final Order Message ------------------
    order_message = (
        f"🚨 НОВЫЙ ЗАКАЗ (С ДОСТАВКОЙ)! 🚨\n"
        f"От пользователя: @{message.from_user.username or message.from_user.id}\n"
        f"ID: `{message.from_user.id}`\n"
        f"\n**🚚 Способ доставки:** {delivery_method}\n"
        f"**📍 Контактные данные (Адрес + Телефон):**\n{contact_info}\n"
        f"\n**🛒 Состав заказа:**\n"
        f"{cart_summary_text}\n"
        f"\n**💵 Общая сумма:** {total_price} сом"
    )

    # Send to admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=order_message, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send order notification to admin ID {admin_id}: {e}")

    # Clear user data
    user_id = str(message.from_user.id)
    if user_id in CARTS:
        del CARTS[user_id]

    await message.answer(
        "🎉 **Заказ принят!**\n"
        "Мы отправили ваши данные менеджеру. Он свяжется с вами по указанному номеру для подтверждения адреса, деталей доставки и оплаты.\n"
        "\n_Спасибо за покупку!_",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )
    await state.clear()


@router.callback_query(MenuCallback.filter(F.action == "questions"))
async def questions_handler(call: types.CallbackQuery):
    await call.answer()

    # Путь к твоему фото
    photo = FSInputFile("images/png.jpg")  # например, положи фото в папку /images рядом с ботом

    # Удаляем старое сообщение (если хочешь заменить его полностью)
    await call.message.delete()

    # Отправляем новое сообщение с фото и текстом
    await call.message.answer_photo(
        photo=photo,
        caption=FAQ_TEXT,  # твой текст, можно оставить как есть
        reply_markup=main_menu()
    )



# --- Отзывы ---
@router.callback_query(MenuCallback.filter(F.action == "reviews_menu"))
async def reviews_menu_handler(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text("Отзывы магазина:", reply_markup=reviews_menu_kb())


@router.callback_query(ReviewCallback.filter(F.action == "leave"))
async def leave_review_start(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("🌟 Выберите рейтинг:", reply_markup=rating_menu())
    await state.set_state(ReviewStates.waiting_rating)


@router.callback_query(ReviewStates.waiting_rating, ReviewCallback.filter(F.action == "rate"))
async def handle_rating_selection(call: types.CallbackQuery, state: FSMContext, callback_data: ReviewCallback):
    await call.answer()
    rating = callback_data.value
    await state.update_data(rating=rating)
    stars = '⭐' * rating

    await call.message.edit_text(
        f"✅ Ваш рейтинг: {stars}\n\nТеперь напишите свой отзыв (текст):",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='back_main').pack())
        ).as_markup()
    )
    await state.set_state(ReviewStates.waiting_text)


@router.message(ReviewStates.waiting_text, F.text)
async def review_text_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rating = data.get("rating", 5)

    if not message.text:
        await message.answer("⚠️ Текст отзыва не может быть пустым. Пожалуйста, напишите ваш отзыв.")
        return

    text_review = message.text
    user_display = message.from_user.username or message.from_user.full_name or str(message.from_user.id)

    REVIEWS.append({
        "user": user_display,
        "rating": rating,
        "text": text_review
    })

    await save_reviews_async()

    user_name = message.from_user.first_name or "дорогой друг"
    await message.answer(
        f"🎉 Спасибо огромное за поддержку, {user_name}! 🤩\n"
        f"Ваш ценный отзыв ({'⭐' * rating}) принят и очень важен для нас! 🙏",
        reply_markup=main_menu()
    )
    await state.clear()


@router.callback_query(ReviewCallback.filter(F.action == "view"))
async def view_reviews_handler(call: types.CallbackQuery):
    await call.answer()
    if not REVIEWS:
        await call.message.edit_text("Отзывы еще не оставлены.", reply_markup=reviews_menu_kb())
        return

    total_reviews = len(REVIEWS)
    total_rating = sum(int(r['rating']) for r in REVIEWS)
    avg_rating = total_rating / total_reviews if total_reviews > 0 else 0
    stars_avg = '⭐' * round(avg_rating)

    rating_counts = {i: 0 for i in range(1, 6)}
    for r in REVIEWS:
        rating_counts[int(r.get('rating', 5))] += 1

    rating_stats = []
    for rating in range(5, 0, -1):
        count = rating_counts[rating]
        percent = (count / total_reviews) * 100 if total_reviews > 0 else 0
        stars = '⭐' * rating
        rating_stats.append(f"{stars}: {count} ({percent:.1f}%)")

    reviews_display = []
    for r in reversed(REVIEWS):
        user_display = r['user']
        rating_stars = '⭐' * int(r['rating'])
        reviews_display.append(f"{user_display} ({rating_stars}):\n{r['text']}")

    text = (
        f"📊 Общий рейтинг магазина:\n"
        f"Средняя оценка: {stars_avg} ({avg_rating:.2f}/5)\n"
        f"Всего отзывов: {total_reviews}\n"
        f"\nРаспределение оценок:\n"
        f"{'\n'.join(rating_stats)}\n"
        f"\n{'-' * 20}\n"
        f"Последние отзывы:\n"
        f"{'\n\n'.join(reviews_display)}"
    )

    review_view_kb = InlineKeyboardBuilder()
    review_view_kb.row(InlineKeyboardButton(text="🔎 Выбрать отзывы по рейтингу",
                                            callback_data=ReviewCallback(action='filter_reviews_menu').pack()))
    review_view_kb.row(
        InlineKeyboardButton(text="⬅️ Меню отзывов", callback_data=MenuCallback(action='reviews_menu').pack()),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data=MenuCallback(action='back_main').pack())
    )

    await call.message.edit_text(text, reply_markup=review_view_kb.as_markup())


@router.callback_query(ReviewCallback.filter(F.action == "filter_reviews_menu"))
async def filter_reviews_menu_handler(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text("🔎 Выберите рейтинг для фильтрации:", reply_markup=reviews_filter_kb())


@router.callback_query(ReviewCallback.filter(F.action == "filter"))
async def filter_reviews_by_rating_handler(call: types.CallbackQuery, callback_data: ReviewCallback):
    await call.answer()
    target_rating = callback_data.value

    filtered_reviews = [r for r in REVIEWS if int(r.get('rating', 0)) == target_rating]
    stars = '⭐' * target_rating

    if not filtered_reviews:
        text = f"❌ Нет отзывов с рейтингом {stars}."
    else:
        reviews_display = []
        for r in reversed(filtered_reviews):
            user_display = r['user']
            reviews_display.append(f"{user_display}:\n{r['text']}")

        text = (
            f"📄 Отзывы с рейтингом {stars} ({len(filtered_reviews)} шт.):\n"
            f"{'-' * 20}\n"
            f"{'\n\n'.join(reviews_display)}"
        )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Назад к фильтрам",
                                callback_data=ReviewCallback(action='filter_reviews_menu').pack()))
    kb.row(InlineKeyboardButton(text="📝 Меню отзывов", callback_data=MenuCallback(action='reviews_menu').pack()))

    await call.message.edit_text(text, reply_markup=kb.as_markup())


# --- Админ панель ---
@router.callback_query(MenuCallback.filter(F.action == "admin_menu"))
async def admin_menu_handler(call: types.CallbackQuery, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    await call.message.edit_text("🔑 Панель Администратора\nВыберите действие:", reply_markup=admin_menu_kb())


# --- Добавление товара (ИСПРАВЛЕННЫЙ FSM) ---
@router.callback_query(MenuCallback.filter(F.action == "admin_add_product_start"))
async def admin_add_product_start_handler(call: types.CallbackQuery, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()

    kb = InlineKeyboardBuilder()
    for cat in PRODUCTS.keys():
        normalized_id = get_normalized_cat_id(cat)
        kb.button(text=cat, callback_data=CategoryCallback(action='admin_add', category_id=normalized_id).pack())
    kb.row(InlineKeyboardButton(text="➕ Новая категория",
                                callback_data=CategoryCallback(action='admin_add', category_id='other').pack()))
    kb.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack()))
    kb.adjust(2)

    await call.message.edit_text(
        "➕ Добавление товара\nВыберите существующую категорию или создайте новую:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(AdminStates.waiting_new_category)


@router.callback_query(AdminStates.waiting_new_category, CategoryCallback.filter(F.action == "admin_add"))
async def admin_add_category_handler(call: types.CallbackQuery, state: FSMContext, callback_data: CategoryCallback):
    if not await check_admin_auth(state, call):
        return
    await call.answer()

    normalized_id = callback_data.category_id

    if normalized_id == "other":
        await call.message.edit_text(
            "📝 Введите название новой категории:",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
            ).as_markup()
        )
    else:
        category = get_original_cat_name(normalized_id)
        if not category:
            await call.answer("Ошибка: не удалось найти категорию.", show_alert=True)
            return

        await state.update_data(category=category)

        prompt_text = "📝 Теперь введите название нового товара:"
        if category == "Одноразки":
            # Если одноразки, то просим ввести только ВКУС
            prompt_text = "📝 Введите название вкуса (например: Вишня):"

        await call.message.edit_text(
            f"✅ Категория: {category}\n\n{prompt_text}",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
            ).as_markup()
        )
        await state.set_state(AdminStates.waiting_new_name)


@router.message(AdminStates.waiting_new_category, F.text)
async def admin_new_category_input(message: types.Message, state: FSMContext):
    if not await check_admin_auth(state, message):
        return

    category = message.text.strip()
    if not category:
        await message.answer("⚠️ Название категории не может быть пустым.")
        return

    await state.update_data(category=category)

    prompt_text = "📝 Теперь введите название нового товара:"
    if category == "Одноразки":
        prompt_text = "📝 Введите название вкуса (например: Вишня):"

    await message.answer(
        f"✅ Категория: {category}\n\n{prompt_text}",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
        ).as_markup()
    )
    await state.set_state(AdminStates.waiting_new_name)


@router.message(AdminStates.waiting_new_name, F.text)
async def admin_new_name_input(message: types.Message, state: FSMContext):
    if not await check_admin_auth(state, message):
        return

    product_name = message.text.strip()
    if not product_name:
        await message.answer("⚠️ Название товара не может быть пустым.")
        return

    await state.update_data(name=product_name)
    data = await state.get_data()
    category = data.get("category")

    if category == "Снюс":
        await message.answer(
            f"✅ Название: {product_name}\n\n💪 Теперь введите мощность (например: 75мг):",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
            ).as_markup()
        )
        await state.set_state(AdminStates.waiting_new_strength)
    elif category == "Одноразки":
        # Одноразки переходят к выбору бренда
        await message.answer(
            f"✅ Вкус: {product_name}\n\n🎯 Теперь выберите бренд:",
            reply_markup=admin_disposable_brands_kb()
        )
        await state.set_state(AdminStates.waiting_new_brand)
    else:
        # Остальные категории сразу переходят к цене
        await message.answer(
            f"✅ Название: {product_name}\n\n💰 Теперь введите цену (только число, например: 950):",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
            ).as_markup()
        )
        await state.set_state(AdminStates.waiting_new_price)


@router.message(AdminStates.waiting_new_strength, F.text)
async def admin_new_strength_input(message: types.Message, state: FSMContext):
    if not await check_admin_auth(state, message):
        return

    strength = message.text.strip()
    if not strength:
        await message.answer("⚠️ Мощность не может быть пустой.")
        return

    await state.update_data(strength=strength)
    data = await state.get_data()
    product_name = data.get("name")

    # Снюс переходит к выбору бренда после мощности
    await message.answer(
        f"✅ Название: {product_name}\n✅ Мощность: {strength}\n\n🎯 Теперь выберите бренд:",
        reply_markup=admin_snus_brands_kb()
    )
    await state.set_state(AdminStates.waiting_new_brand)


# Хендлер для выбора бренда СНЮСА в админке
@router.callback_query(AdminStates.waiting_new_brand, SnusBrandCallback.filter())
async def admin_new_brand_snus_input(call: types.CallbackQuery, state: FSMContext, callback_data: SnusBrandCallback):
    if not await check_admin_auth(state, call):
        return
    await call.answer()

    brand = callback_data.brand
    await state.update_data(brand=brand)
    data = await state.get_data()
    product_name = data.get("name")
    strength = data.get("strength")

    # Снюс переходит к цене
    await call.message.edit_text(
        f"✅ Название: {product_name}\n✅ Мощность: {strength}\n✅ Бренд: {brand}\n\n💰 Теперь введите цену:",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
        ).as_markup()
    )
    await state.set_state(AdminStates.waiting_new_price)


# Хендлер для выбора бренда ОДНОРАЗОК в админке. NEW: Теперь ведет на выбор затяжек
@router.callback_query(AdminStates.waiting_new_brand, DisposableBrandCallback.filter())
async def admin_new_brand_disposable_input(call: types.CallbackQuery, state: FSMContext,
                                           callback_data: DisposableBrandCallback):
    if not await check_admin_auth(state, call):
        return
    await call.answer()

    brand = callback_data.brand
    await state.update_data(brand=brand)
    data = await state.get_data()
    product_name = data.get("name")  # Вкус

    await call.message.edit_text(
        f"✅ Вкус: {product_name}\n✅ Бренд: {brand}\n\n💨 Теперь введите количество затяжек (только число):",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
        ).as_markup()
    )
    # NEW STATE
    await state.set_state(AdminStates.waiting_new_capacity)


# NEW: Хендлер для ввода количества затяжек
@router.message(AdminStates.waiting_new_capacity, F.text)
async def admin_new_capacity_input(message: types.Message, state: FSMContext):
    if not await check_admin_auth(state, message):
        return

    try:
        capacity = int(message.text.strip())
        if capacity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверный формат затяжек. Введите целое положительное число:")
        return

    await state.update_data(capacity=capacity)
    data = await state.get_data()
    product_name = data.get("name")  # Вкус
    brand = data.get("brand")

    # Переход к цене
    await message.answer(
        f"✅ Вкус: {product_name}\n✅ Бренд: {brand}\n✅ Затяжки: {capacity}\n\n💰 Теперь введите цену (только число, например: 950):",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️ Отмена", callback_data=MenuCallback(action='admin_menu').pack())
        ).as_markup()
    )
    await state.set_state(AdminStates.waiting_new_price)


@router.message(AdminStates.waiting_new_price, F.text)
async def admin_new_price_input(message: types.Message, state: FSMContext):
    if not await check_admin_auth(state, message):
        return

    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите целое положительное число:")
        return

    data = await state.get_data()
    category = data.get("category")
    product_name = data.get("name")
    strength = data.get("strength")
    brand = data.get("brand")
    capacity = data.get("capacity")  # NEW

    new_product = {
        "name": product_name,
        "price": price,
        "available": True
    }

    # Добавляем специальные поля
    if category == "Снюс":
        new_product["strength"] = strength
        new_product["brand"] = brand
    elif category == "Одноразки":
        new_product["brand"] = brand
        new_product["capacity"] = capacity  # NEW

    if category not in PRODUCTS:
        PRODUCTS[category] = []

    PRODUCTS[category].append(new_product)

    logging.info(f"Added product: {new_product} to category: {category}")

    await save_products_async()

    confirmation_text = f"🎉 Товар успешно добавлен!\nКатегория: {category}\nНазвание: {product_name}\nЦена: {price} сом\nСтатус: ✅ В НАЛИЧИИ"
    if brand:
        confirmation_text += f"\nБренд: {brand}"
    if strength and category == "Снюс":
        confirmation_text += f"\nМощность: {strength}"
    if capacity and category == "Одноразки":  # NEW
        confirmation_text += f"\nЗатяжки: {capacity}"

    await message.answer(confirmation_text, reply_markup=admin_menu_kb())
    await state.clear()


# --- Остальные админ хендлеры ---
@router.callback_query(MenuCallback.filter(F.action == "admin_manage_availability_start"))
async def admin_manage_availability_start_handler(call: types.CallbackQuery, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    await call.message.edit_text("Выберите категорию для управления наличием:",
                                 reply_markup=admin_categories_kb("admin_manage"))


@router.callback_query(MenuCallback.filter(F.action == "admin_delete_start"))
async def admin_delete_start_handler(call: types.CallbackQuery, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    await call.message.edit_text("Выберите категорию для удаления товара:",
                                 reply_markup=admin_categories_kb("admin_delete"))


@router.callback_query(CategoryCallback.filter(F.action == "admin_manage"))
async def admin_manage_category_handler(call: types.CallbackQuery, callback_data: CategoryCallback, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    category = get_original_cat_name(callback_data.category_id)
    if category in PRODUCTS:
        await call.message.edit_text(
            f"🔧 Управление наличием: {category}",
            reply_markup=admin_product_list_kb(category)
        )


@router.callback_query(CategoryCallback.filter(F.action == "admin_delete"))
async def admin_delete_category_handler(call: types.CallbackQuery, callback_data: CategoryCallback, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    category = get_original_cat_name(callback_data.category_id)
    if category in PRODUCTS:
        await call.message.edit_text(
            f"🗑️ Удаление товаров: {category}",
            reply_markup=admin_product_list_kb_delete(category)
        )


@router.callback_query(ProductCallback.filter(F.action == "toggle"))
async def admin_toggle_product_handler(call: types.CallbackQuery, callback_data: ProductCallback, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    category = get_original_cat_name(callback_data.category_id)
    product_index = callback_data.product_index

    if category and 0 <= product_index < len(PRODUCTS.get(category, [])):
        product = PRODUCTS[category][product_index]
        product['available'] = not product.get('available', True)
        await save_products_async()

        status_text = '✅' if product['available'] else '❌'  # Упрощенный текст
        await call.answer(f"Статус изменен на: {status_text}", show_alert=True)

        await call.message.edit_text(
            f"🔧 Управление наличием: {category}",
            reply_markup=admin_product_list_kb(category)
        )


@router.callback_query(ProductCallback.filter(F.action == "delete"))
async def admin_delete_product_handler(call: types.CallbackQuery, callback_data: ProductCallback, state: FSMContext):
    if not await check_admin_auth(state, call):
        return
    await call.answer()
    category = get_original_cat_name(callback_data.category_id)
    product_index = callback_data.product_index

    if category and 0 <= product_index < len(PRODUCTS.get(category, [])):
        deleted_product = PRODUCTS[category].pop(product_index)
        if not PRODUCTS[category]:
            del PRODUCTS[category]
        await save_products_async()
        await call.answer(f"Товар '{deleted_product['name']}' удален", show_alert=True)

        if category in PRODUCTS:
            await call.message.edit_text(
                f"🗑️ Удаление товаров: {category}",
                reply_markup=admin_product_list_kb_delete(category)
            )
        else:
            await call.message.edit_text("Категория удалена. Выберите другую:",
                                         reply_markup=admin_categories_kb("admin_delete"))


@router.message(F.text)
async def handle_non_command_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    # Разрешаем ввод только в определенных состояниях, которые ожидают текст
    if current_state and current_state not in [
        AdminLoginStates.waiting_username,
        AdminLoginStates.waiting_password,
        ReviewStates.waiting_text,
        AdminStates.waiting_new_category,  # Для новой категории
        AdminStates.waiting_new_name,  # Для названия/вкуса
        AdminStates.waiting_new_strength,  # Для мощности снюса
        AdminStates.waiting_new_capacity,  # Для затяжек одноразок
        AdminStates.waiting_new_price,  # Для цены
        CheckoutStates.waiting_address_phone # Для адреса и телефона
    ]:
        await message.answer(
            "⚠️ Вы находитесь в процессе ввода данных. Воспользуйтесь кнопками отмены или завершите ввод.")
        return

    # Обычная обработка текста, если не находимся ни в одном FSM-состоянии или в ожидании отзыва
    if not current_state or current_state == ReviewStates.waiting_text:
        # Если в ReviewStates.waiting_text, то хендлер review_text_handler уже отработает.
        # Если не в FSM-состоянии, то показываем главное меню.
        if not current_state:
            await message.answer("Используйте кнопки меню или команду /start.", reply_markup=main_menu())


# ---------- STARTUP ----------
async def main():
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by KeyboardInterrupt.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
