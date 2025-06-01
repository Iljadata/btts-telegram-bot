from aiogram.fsm.state import State, StatesGroup

class IncomeStates(StatesGroup):
    waiting_for_project = State()
    waiting_for_date = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_counterparty = State()
    waiting_for_account = State()
    waiting_for_comment = State()

class ExpenseStates(StatesGroup):
    waiting_for_project = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_counterparty = State()  # <-- добавили это
    waiting_for_account = State()
    waiting_for_comment = State()

class ReportStates(StatesGroup):
    waiting_for_date = State()

class BusinessStatsStates(StatesGroup):
    waiting_for_business = State()
    waiting_for_period = State()
    waiting_for_date = State()
