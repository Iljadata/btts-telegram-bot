import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from datetime import datetime
from states import IncomeStates, ExpenseStates, ReportStates, BusinessStatsStates
from gsheets import get_report_by_range, get_summary_period, get_report_for_date, append_transaction, get_business_stats
from datetime import datetime, timedelta
import sys
import matplotlib.pyplot as plt
import io
import os
import tempfile


API_TOKEN = "7616834856:AAGEBvPoeNZTtNZGeOJDTAumSi9zSlFX794"

# URL Google таблицы
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1XvlXSgs4N0ztCP-aAfu3ZsC4a2p99tCFolXYPOFOvS4/edit?gid=1475886138#gid=1475886138"

logging.basicConfig(level=logging.INFO)
router = Router()

def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Доход", callback_data="add_income")],
        [InlineKeyboardButton(text="➖ Расход", callback_data="add_expense")],
        [InlineKeyboardButton(text="📊 Отчёт", callback_data="report")],
        [InlineKeyboardButton(text="📋 Таблица", callback_data="open_gsheet")],
        [InlineKeyboardButton(text="📈 Статистика бизнеса", callback_data="business_stats")]
    ])
    return kb

# Универсальная команда для возврата в главное меню из любого состояния
@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Очищаем любое текущее состояние
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=main_menu())

# Обработчик для кнопки с ссылкой на Google таблицу
@router.callback_query(F.data == "open_gsheet")
async def open_google_sheet(callback: CallbackQuery):
    await callback.message.answer(
        f"📋 <b>Ссылка на Google таблицу:</b>\n\n"
        f"<a href='{GSHEET_URL}'>Открыть таблицу</a>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()
    
    # Автоматически показываем главное меню после выдачи ссылки
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())

# ============ СТАТИСТИКА БИЗНЕСА ============

@router.callback_query(F.data == "business_stats")
async def business_stats_menu(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="CopyPro1", callback_data="stats_cp1")],
        [InlineKeyboardButton(text="ДомБыта ЛП58", callback_data="stats_lp58")],
        [InlineKeyboardButton(text="ДомБыта Панфиловцам", callback_data="stats_pan")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Выберите бизнес для просмотра статистики:", reply_markup=kb)
    await state.set_state(BusinessStatsStates.waiting_for_business)

@router.callback_query(BusinessStatsStates.waiting_for_business)
async def select_business_period(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
    
    business_map = {
        "stats_cp1": "CopyPro1",
        "stats_lp58": "ДомБыта Ленинградский проспект 58",
        "stats_pan": "ДомБыта Героям Панфиловцам 35"
    }
    
    business_name = business_map.get(callback.data)
    await state.update_data(business=business_name)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="bs_today")],
        [InlineKeyboardButton(text="🧮 За неделю", callback_data="bs_week")],
        [InlineKeyboardButton(text="📈 За месяц", callback_data="bs_month")],
        [InlineKeyboardButton(text="📚 За год", callback_data="bs_year")],
        [InlineKeyboardButton(text="📌 По дате", callback_data="bs_by_date")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_business_menu")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    
    await callback.message.answer(f"Выберите период для статистики бизнеса <b>{business_name}</b>:", 
                                 reply_markup=kb, 
                                 parse_mode=ParseMode.HTML)
    await state.set_state(BusinessStatsStates.waiting_for_period)

@router.callback_query(BusinessStatsStates.waiting_for_period)
async def handle_business_period(callback: CallbackQuery, state: FSMContext):
    if callback.data == "back_to_business_menu":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="CopyPro1", callback_data="stats_cp1")],
            [InlineKeyboardButton(text="ДомБыта ЛП58", callback_data="stats_lp58")],
            [InlineKeyboardButton(text="ДомБыта Панфиловцам", callback_data="stats_pan")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="return_to_main")]
        ])
        await callback.message.answer("Выберите бизнес для просмотра статистики:", reply_markup=kb)
        await state.set_state(BusinessStatsStates.waiting_for_business)
        await callback.answer()
        return
    
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
    
    data = await state.get_data()
    business = data.get("business")
    today = datetime.today()
    
    # Кнопки навигации для отчетов
    nav_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Другой период", callback_data="back_to_business_menu")],
        [InlineKeyboardButton(text="📈 Другой бизнес", callback_data="business_stats")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    
    if callback.data == "bs_today":
        date = today.strftime("%d.%m.%Y")
        stats, income_data, expense_data = get_business_stats(business, "day", date)
        
        # Создаем все диаграммы
        pie_chart_buf = create_pie_chart(business, "Сегодня", income_data, expense_data)
        bar_chart_buf = create_bar_chart(business, "Сегодня", income_data, expense_data)
        
        # Отправляем текстовый отчет с кнопками навигации
        await callback.message.answer(stats, reply_markup=nav_kb)
        
        # Отправляем диаграммы
        await callback.message.answer_photo(pie_chart_buf, caption=f"📊 Структура доходов и расходов {business} за сегодня")
        await callback.message.answer_photo(bar_chart_buf, caption=f"📊 Сравнение доходов и расходов {business} за сегодня", reply_markup=nav_kb)
        await callback.answer()
        return
    
    if callback.data == "bs_week":
        stats, income_data, expense_data = get_business_stats(business, "week")
        
        # Создаем все диаграммы
        pie_chart_buf = create_pie_chart(business, "За неделю", income_data, expense_data)
        bar_chart_buf = create_bar_chart(business, "За неделю", income_data, expense_data)
        
        # Отправляем текстовый отчет с кнопками навигации
        await callback.message.answer(stats, reply_markup=nav_kb)
        
        # Отправляем диаграммы
        await callback.message.answer_photo(pie_chart_buf, caption=f"📊 Структура доходов и расходов {business} за неделю")
        await callback.message.answer_photo(bar_chart_buf, caption=f"📊 Сравнение доходов и расходов {business} за неделю", reply_markup=nav_kb)
        await callback.answer()
        return
    
    if callback.data == "bs_month":
        stats, income_data, expense_data = get_business_stats(business, "month")
        
        # Создаем все диаграммы
        pie_chart_buf = create_pie_chart(business, "За месяц", income_data, expense_data)
        bar_chart_buf = create_bar_chart(business, "За месяц", income_data, expense_data)
        
        # Отправляем текстовый отчет с кнопками навигации
        await callback.message.answer(stats, reply_markup=nav_kb)
        
        # Отправляем диаграммы
        await callback.message.answer_photo(pie_chart_buf, caption=f"📊 Структура доходов и расходов {business} за месяц")
        await callback.message.answer_photo(bar_chart_buf, caption=f"📊 Сравнение доходов и расходов {business} за месяц", reply_markup=nav_kb)
        await callback.answer()
        return
    
    if callback.data == "bs_year":
        stats, income_data, expense_data = get_business_stats(business, "year")
        
        # Создаем все диаграммы
        pie_chart_buf = create_pie_chart(business, "За год", income_data, expense_data)
        bar_chart_buf = create_bar_chart(business, "За год", income_data, expense_data)
        
        # Отправляем текстовый отчет с кнопками навигации
        await callback.message.answer(stats, reply_markup=nav_kb)
        
        # Отправляем диаграммы
        await callback.message.answer_photo(pie_chart_buf, caption=f"📊 Структура доходов и расходов {business} за год")
        await callback.message.answer_photo(bar_chart_buf, caption=f"📊 Сравнение доходов и расходов {business} за год", reply_markup=nav_kb)
        await callback.answer()
        return
    
    if callback.data == "bs_by_date":
        await callback.message.answer("Введите дату в формате ДД.ММ.ГГГГ:")
        await state.set_state(BusinessStatsStates.waiting_for_date)
        await callback.answer()
        return
    
    await callback.message.answer("Неизвестный период.", reply_markup=nav_kb)
    await callback.answer()

@router.message(BusinessStatsStates.waiting_for_date)
async def handle_business_custom_date(message: Message, state: FSMContext):
    # Кнопки навигации для отчетов
    nav_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Другой период", callback_data="back_to_business_menu")],
        [InlineKeyboardButton(text="📈 Другой бизнес", callback_data="business_stats")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    
    try:
        date = message.text.strip()
        data = await state.get_data()
        business = data.get("business")
        
        stats, income_data, expense_data = get_business_stats(business, "day", date)
        
        # Создаем все диаграммы
        pie_chart_buf = create_pie_chart(business, f"за {date}", income_data, expense_data)
        bar_chart_buf = create_bar_chart(business, f"за {date}", income_data, expense_data)
        
        # Отправляем текстовый отчет с кнопками навигации
        await message.answer(stats, reply_markup=nav_kb)
        
        # Отправляем диаграммы
        await message.answer_photo(pie_chart_buf, caption=f"📊 Структура доходов и расходов {business} за {date}")
        await message.answer_photo(bar_chart_buf, caption=f"📊 Сравнение доходов и расходов {business} за {date}", reply_markup=nav_kb)
    except Exception as e:
        await message.answer(f"Ошибка: {e}", reply_markup=nav_kb)
    
    # Очищаем состояние, так как навигация будет через кнопки
    await state.clear()

# Функции для создания диаграмм
def create_pie_chart(business: str, period: str, income_data: dict, expense_data: dict):
    """Создает круговую диаграмму структуры доходов и расходов"""
    # Создаем две круговые диаграммы: для доходов и расходов
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    # Диаграмма доходов
    if income_data:
        income_labels = list(income_data.keys())
        income_values = list(income_data.values())
        ax1.pie(income_values, labels=None, autopct='%1.1f%%', startangle=90)
        ax1.set_title('Структура доходов')
        ax1.legend(income_labels, loc="center left", bbox_to_anchor=(0, -0.1))
    else:
        ax1.text(0.5, 0.5, 'Нет данных о доходах', horizontalalignment='center', verticalalignment='center')
        ax1.axis('off')
    
    # Диаграмма расходов
    if expense_data:
        expense_labels = list(expense_data.keys())
        expense_values = list(expense_data.values())
        ax2.pie(expense_values, labels=None, autopct='%1.1f%%', startangle=90)
        ax2.set_title('Структура расходов')
        ax2.legend(expense_labels, loc="center right", bbox_to_anchor=(1, -0.1))
    else:
        ax2.text(0.5, 0.5, 'Нет данных о расходах', horizontalalignment='center', verticalalignment='center')
        ax2.axis('off')
    
    plt.suptitle(f'Структура доходов и расходов {business} {period}')
    plt.tight_layout()
    
    # Сохраняем график во временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(temp_file.name, format='png')
    plt.close(fig)
    
    return FSInputFile(temp_file.name)

def create_bar_chart(business: str, period: str, income_data: dict, expense_data: dict):
    """Создает столбчатую диаграмму сравнения доходов и расходов"""
    # Подготовка данных для графика
    categories = list(set(list(income_data.keys()) + list(expense_data.keys())))
    categories.sort()
    
    income_values = [income_data.get(cat, 0) for cat in categories]
    expense_values = [expense_data.get(cat, 0) for cat in categories]
    
    # Создание графика
    x = range(len(categories))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 7))
    rects1 = ax.bar([i - width/2 for i in x], income_values, width, label='Доходы', color='green')
    rects2 = ax.bar([i + width/2 for i in x], expense_values, width, label='Расходы', color='red')
    
    # Добавление подписей и заголовка
    ax.set_title(f'Сравнение доходов и расходов {business} {period}')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45, ha='right')
    ax.legend()
    
    # Добавление значений над столбцами
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                ax.annotate(f'{height:.0f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),
                            textcoords="offset points",
                            ha='center', va='bottom')
    
    autolabel(rects1)
    autolabel(rects2)
    
    plt.tight_layout()
    
    # Сохраняем график во временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(temp_file.name, format='png')
    plt.close(fig)
    
    return FSInputFile(temp_file.name)

# ============ ДОХОД ============

@router.callback_query(F.data == "add_income")
async def income_start(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ДомБыта ЛП58", callback_data="project_lp58")],
        [InlineKeyboardButton(text="CopyPro1", callback_data="project_cp1")],
        [InlineKeyboardButton(text="ДомБыта Панфиловцам", callback_data="project_pan")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Выберите проект:", reply_markup=kb)
    await state.set_state(IncomeStates.waiting_for_project)
    await callback.answer()

@router.callback_query(IncomeStates.waiting_for_project)
async def income_project(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    projects = {
        "project_lp58": "ДомБыта Ленинградский проспект 58",
        "project_cp1": "CopyPro1",
        "project_pan": "ДомБыта Героям Панфиловцам 35"
    }
    await state.update_data(
        project=projects.get(callback.data),
        date=datetime.today().strftime("%d.%m.%Y"),
        counterparty="Никита Л"
    )
    await callback.message.answer("Введите сумму:")
    await state.set_state(IncomeStates.waiting_for_amount)
    await callback.answer()

@router.message(IncomeStates.waiting_for_amount)
async def income_amount(message: Message, state: FSMContext):
    await state.update_data(amount=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Полиграф. Услуги", callback_data="cat_print")],
        [InlineKeyboardButton(text="Фото Услуги", callback_data="cat_photo")],
        [InlineKeyboardButton(text="Печати", callback_data="cat_stamp")],
        [InlineKeyboardButton(text="Продажа Допов", callback_data="cat_dops")],
        [InlineKeyboardButton(text="Ключи", callback_data="cat_keys")],
        [InlineKeyboardButton(text="Одежда", callback_data="cat_clothes")],
        [InlineKeyboardButton(text="Часы", callback_data="cat_watches")],
        [InlineKeyboardButton(text="Обувь", callback_data="cat_shoes")],
        [InlineKeyboardButton(text="Другое", callback_data="cat_other")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await message.answer("Выберите статью дохода:", reply_markup=kb)
    await state.set_state(IncomeStates.waiting_for_category)

@router.callback_query(IncomeStates.waiting_for_category)
async def income_category(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    categories = {
        "cat_print": "Полиграф. Услуги",
        "cat_photo": "Фото Услуги",
        "cat_stamp": "Печати",
        "cat_dops": "Продажа Допов",
        "cat_keys": "Ключи",
        "cat_clothes": "Одежда",
        "cat_watches": "Часы",
        "cat_shoes": "Обувь",
        "cat_other": "Другое"
    }
    await state.update_data(category=categories.get(callback.data))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Наличка", callback_data="Наличка")],
        [InlineKeyboardButton(text="Альфа", callback_data="Альфа")],
        [InlineKeyboardButton(text="Оплата по счёту", callback_data="Оплата по счёту")],
        [InlineKeyboardButton(text="Эквайринг", callback_data="Эквайринг")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])

    await callback.message.answer("Выберите счёт:", reply_markup=kb)
    await state.set_state(IncomeStates.waiting_for_account)
    await callback.answer()

@router.callback_query(IncomeStates.waiting_for_account)
async def income_account(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    await state.update_data(account=callback.data)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="— Нет комментария", callback_data="no_comment")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Комментарий (если есть):", reply_markup=kb)
    await state.set_state(IncomeStates.waiting_for_comment)
    await callback.answer()

@router.callback_query(IncomeStates.waiting_for_comment, F.data == "no_comment")
async def income_no_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment="-")
    await save_income(callback.message, state)
    await callback.answer()

@router.callback_query(IncomeStates.waiting_for_comment, F.data == "return_to_main")
async def income_return_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())
    await callback.answer()

@router.message(IncomeStates.waiting_for_comment)
async def income_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await save_income(message, state)

async def save_income(message: Message, state: FSMContext):
    data = await state.get_data()
    row = [
        data['date'],
        data['account'],
        data['amount'].replace(" ", "").replace(".", ","),
        data['category'],
        data['counterparty'],
        data['project'],
        data['comment'],
        "доход"
    ]
    try:
        append_transaction(row)
        result = "✅ Доход добавлен!"
    except Exception as e:
        result = f"❌ Ошибка записи: {e}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Ещё запись", callback_data="add_income")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await message.answer(result, reply_markup=kb)
    await state.clear()

# ============ РАСХОД ============

@router.callback_query(F.data == "add_expense")
async def expense_start(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ДомБыта ЛП58", callback_data="exp_lp58")],
        [InlineKeyboardButton(text="CopyPro1", callback_data="exp_cp1")],
        [InlineKeyboardButton(text="ДомБыта Панфиловцам", callback_data="exp_pan")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Выберите проект:", reply_markup=kb)
    await state.set_state(ExpenseStates.waiting_for_project)
    await callback.answer()

@router.callback_query(ExpenseStates.waiting_for_project)
async def expense_project(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    projects = {
        "exp_lp58": "ДомБыта Ленинградский проспект 58",
        "exp_cp1": "CopyPro1",
        "exp_pan": "ДомБыта Героям Панфиловцам 35"
    }
    await state.update_data(
        project=projects.get(callback.data),
        date=datetime.today().strftime("%d.%m.%Y"),
        counterparty="Никита Л"
    )
    await callback.message.answer("Введите сумму:")
    await state.set_state(ExpenseStates.waiting_for_amount)
    await callback.answer()

@router.message(ExpenseStates.waiting_for_amount)
async def expense_amount(message: Message, state: FSMContext):
    await state.update_data(amount=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Зарплата", callback_data="ecat_salary")],
        [InlineKeyboardButton(text="Швея", callback_data="ecat_tailor")],
        [InlineKeyboardButton(text="Материалы/расходники/ключи", callback_data="ecat_materials")],
        [InlineKeyboardButton(text="Другое", callback_data="ecat_other")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await message.answer("Выберите статью расхода:", reply_markup=kb)
    await state.set_state(ExpenseStates.waiting_for_category)

@router.callback_query(ExpenseStates.waiting_for_category)
async def expense_category(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    categories = {
        "ecat_salary": "Зарплата",
        "ecat_tailor": "Швея",
        "ecat_materials": "Материалы/расходники/ключи",
        "ecat_other": "Другое"
    }
    await state.update_data(category=categories.get(callback.data))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Никита Л", callback_data="ctr_nikita")],
        [InlineKeyboardButton(text="Костя", callback_data="ctr_kostya")],
        [InlineKeyboardButton(text="Швея", callback_data="ctr_shveya")],
        [InlineKeyboardButton(text="Ксения", callback_data="ctr_ksenia")],
        [InlineKeyboardButton(text="Александр", callback_data="ctr_alex")],
        [InlineKeyboardButton(text="Бухгалтер", callback_data="ctr_buh")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Выберите контрагента:", reply_markup=kb)
    await state.set_state(ExpenseStates.waiting_for_counterparty)
    await callback.answer()

@router.callback_query(ExpenseStates.waiting_for_counterparty)
async def expense_counterparty(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    counterparty_map = {
        "ctr_nikita": "Никита Л",
        "ctr_kostya": "Костя",
        "ctr_shveya": "Швея",
        "ctr_ksenia": "Ксения",
        "ctr_alex": "Александр",
        "ctr_buh": "Бухгалтер"
    }
    await state.update_data(counterparty=counterparty_map.get(callback.data))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Наличка", callback_data="Наличка")],
        [InlineKeyboardButton(text="Альфа", callback_data="Альфа")],
        [InlineKeyboardButton(text="Оплата по счёту", callback_data="Оплата по счёту")],
        [InlineKeyboardButton(text="Эквайринг", callback_data="Эквайринг")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Выберите счёт:", reply_markup=kb)
    await state.set_state(ExpenseStates.waiting_for_account)
    await callback.answer()


@router.callback_query(ExpenseStates.waiting_for_account)
async def expense_account(callback: CallbackQuery, state: FSMContext):
    if callback.data == "return_to_main":
        await state.clear()
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        await callback.answer()
        return
        
    await state.update_data(account=callback.data)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="— Нет комментария", callback_data="eno_comment")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Комментарий (если есть):", reply_markup=kb)
    await state.set_state(ExpenseStates.waiting_for_comment)
    await callback.answer()

@router.callback_query(ExpenseStates.waiting_for_comment, F.data == "eno_comment")
async def expense_no_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment="-")
    await save_expense(callback.message, state)
    await callback.answer()

@router.callback_query(ExpenseStates.waiting_for_comment, F.data == "return_to_main")
async def expense_return_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())
    await callback.answer()

@router.message(ExpenseStates.waiting_for_comment)
async def expense_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await save_expense(message, state)

async def save_expense(message: Message, state: FSMContext):
    data = await state.get_data()
    row = [
        data['date'],
        data['account'],
        data['amount'].replace(" ", "").replace(".", ","),
        data['category'],
        data['counterparty'],
        data['project'],
        data['comment'],
        "расход"
    ]
    try:
        append_transaction(row)
        result = "✅ Расход добавлен!"
    except Exception as e:
        result = f"❌ Ошибка записи: {e}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Ещё запись", callback_data="add_expense")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await message.answer(result, reply_markup=kb)
    await state.clear()

# ============ ПОВТОР / МЕНЮ ============

@router.callback_query(F.data == "start_over")
async def start_over(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())
    await callback.answer()

# Универсальный обработчик для возврата в главное меню
@router.callback_query(F.data == "return_to_main")
async def return_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())
    await callback.answer()

@router.callback_query(F.data == "report")
async def report_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="r_today")],
        [InlineKeyboardButton(text="🧮 За неделю", callback_data="r_week")],
        [InlineKeyboardButton(text="📈 За месяц", callback_data="r_month")],
        [InlineKeyboardButton(text="📚 За год", callback_data="r_year")],
        [InlineKeyboardButton(text="📌 По дате", callback_data="r_by_date")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    await callback.message.answer("Выберите период для отчёта:", reply_markup=kb)
    await callback.answer()
    

@router.callback_query(F.data.startswith("r_"))
async def handle_report_period(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    today = datetime.today()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Другой отчёт", callback_data="report")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])

    if data == "r_today":
        date = today.strftime("%d.%m.%Y")
        report = get_report_for_date(date)
        await callback.message.answer(report, reply_markup=kb)
        await callback.answer()
        return

    if data == "r_yesterday":
        date = (today - timedelta(days=1)).strftime("%d.%m.%Y")
        report = get_report_for_date(date)
        await callback.message.answer(report, reply_markup=kb)
        await callback.answer()
        return

    if data == "r_week":
        report = get_summary_period("За неделю")
        await callback.message.answer(report, reply_markup=kb)
        await callback.answer()
        return

    if data == "r_month":
        report = get_summary_period("За месяц")
        await callback.message.answer(report, reply_markup=kb)
        await callback.answer()
        return

    if data == "r_year":
        report = get_summary_period("За год")
        await callback.message.answer(report, reply_markup=kb)
        await callback.answer()
        return

    if data == "r_by_date":
        kb_cancel = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Отмена и возврат в меню", callback_data="return_to_main")]
        ])
        await callback.message.answer("Введите дату в формате ДД.ММ.ГГГГ:", reply_markup=kb_cancel)
        await state.set_state(ReportStates.waiting_for_date)
        await callback.answer()
        return

    await callback.message.answer("Неизвестный период.", reply_markup=kb)
    await callback.answer()

@router.message(ReportStates.waiting_for_date)
async def handle_custom_date(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Другой отчёт", callback_data="report")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="return_to_main")]
    ])
    
    try:
        date = message.text.strip()
        from gsheets import get_report_for_date
        result = get_report_for_date(date)
        await message.answer(result, reply_markup=kb)
    except Exception as e:
        await message.answer(f"Ошибка: {e}", reply_markup=kb)
    await state.clear()

# Обработчик для любых текстовых сообщений
@router.message()
async def catch_all(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("⚠️ Предыдущий ввод сброшен.")
    await message.answer("Выберите действие или используйте /start для возврата в главное меню:", reply_markup=main_menu())

# ============ ЗАПУСК ============

async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
