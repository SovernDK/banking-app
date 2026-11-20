"""Every piece of text the app shows, in each supported language."""

from app.banking.errors import BankErrorCode
from app.i18n import Plural, Text
from app.spending import Comparison, Period

LANGUAGE = Text(pl="Język", en="Language", ja="言語")
TOGGLE_DARK_MODE = Text(
    pl="Przełącz tryb ciemny", en="Toggle dark mode", ja="ダークモードの切り替え"
)
SETTINGS = Text(pl="Ustawienia", en="Settings", ja="設定")

OVERVIEW = Text(pl="Przegląd", en="Overview", ja="概要")
SANDBOX = Text(pl="Sandbox", en="Sandbox", ja="サンドボックス")
CONNECT_BANK = Text(pl="Połącz bank", en="Connect bank", ja="銀行を接続")
RECONNECT_BANK = Text(pl="Połącz ponownie", en="Reconnect", ja="再接続")
CONNECTION_ENDS_TODAY = Text(
    pl="Połączenie z bankiem wygasa dziś.",
    en="Your bank connection ends today.",
    ja="銀行との接続は今日で終了します。",
)
CONNECTION_ENDS_IN = Plural(
    pl=(
        "Połączenie z bankiem wygasa za {count} dzień.",
        "Połączenie z bankiem wygasa za {count} dni.",
        "Połączenie z bankiem wygasa za {count} dni.",
    ),
    en=(
        "Your bank connection ends in {count} day.",
        "Your bank connection ends in {count} days.",
    ),
    ja="銀行との接続はあと{count}日で終了します。",
)
NO_TRANSACTIONS = Text(
    pl="Brak transakcji. Połącz konto bankowe, aby zobaczyć historię.",
    en="No transactions yet. Connect a bank account to see your history.",
    ja="取引はまだありません。履歴を表示するには銀行口座を接続してください。",
)
NO_RECENT_SPENDING = Text(
    pl="Brak wydatków w ostatnim miesiącu.",
    en="No spending in the last month.",
    ja="過去1か月の支出はありません。",
)
NO_SPENDING_IN_PERIOD = Text(
    pl="Brak wydatków w tym okresie.",
    en="No spending in this period.",
    ja="この期間の支出はありません。",
)

PERIOD = Text(pl="Okres", en="Period", ja="期間")
PERIODS = {
    Period.LAST_WEEK: Text(pl="Ostatni tydzień", en="Last week", ja="過去1週間"),
    Period.LAST_MONTH: Text(pl="Ostatni miesiąc", en="Last month", ja="過去1か月"),
}
PERIODS_IN_SENTENCE = {
    Period.LAST_WEEK: Text(pl="ostatni tydzień", en="last week", ja="過去1週間"),
    Period.LAST_MONTH: Text(pl="ostatni miesiąc", en="last month", ja="過去1か月"),
}

COMPARE_WITH = Text(pl="Porównaj z", en="Compare with", ja="比較対象")
COMPARISONS = {
    Comparison.MONTH: Text(pl="m/m", en="M2M", ja="前月比"),
    Comparison.YEAR: Text(pl="r/r", en="Y2Y", ja="前年比"),
}
COMPARISONS_AGO = {
    Comparison.MONTH: Text(pl="sprzed miesiąca", en="a month ago", ja="1か月前"),
    Comparison.YEAR: Text(pl="sprzed roku", en="a year ago", ja="1年前"),
}
COMPARED_SERIES = {
    Comparison.MONTH: Text(pl="Miesiąc wcześniej", en="A month ago", ja="1か月前"),
    Comparison.YEAR: Text(pl="Rok wcześniej", en="A year ago", ja="1年前"),
}

SPENT = Text(pl="Wydano, {period}", en="Spent, {period}", ja="支出、{period}")
SPENT_ON = Text(
    pl="Wydano na {subject}, {period}",
    en="Spent on {subject}, {period}",
    ja="{subject}への支出、{period}",
)
SPENT_UNCATEGORISED = Text(
    pl="Wydano bez kategorii, {period}",
    en="Spent on uncategorised, {period}",
    ja="未分類の支出、{period}",
)
COMPARED_TOTAL = Text(pl="wobec {amount} {ago}", en="vs {amount} {ago}", ja="{ago}の{amount}と比較")
SPENDING_PER_DAY = Text(pl="Wydatki dzienne", en="Spending per day", ja="1日あたりの支出")
SPENDING_PER_DAY_VS = Text(
    pl="Wydatki dzienne wobec okresu {ago}",
    en="Spending per day vs {ago}",
    ja="1日あたりの支出（{ago}と比較）",
)
CONVERTED_COMPARISON = Text(
    pl="Przeliczono po kursie z każdego dnia, więc porównanie obejmuje zmiany kursów walut.",
    en="Converted at each day's rate, so the comparison includes exchange-rate changes.",
    ja="各日のレートで換算しているため、比較には為替レートの変動が含まれます。",
)
THIS_PERIOD = Text(pl="Ten okres", en="This period", ja="今期")

CURRENCY = Text(pl="Waluta", en="Currency", ja="通貨")
NO_RATE = Text(pl="brak kursu", en="no rate", ja="レートなし")
RATES_UNAVAILABLE = Text(
    pl="Nie udało się pobrać kursów walut; kwoty mogą korzystać ze starszych kursów.",
    en="Exchange rates could not be updated; amounts may use older rates.",
    ja="為替レートを更新できませんでした。金額は古いレートで表示される場合があります。",
)
NOT_CONVERTED = Plural(
    pl=(
        "Pominięto {count} płatność: brak kursu {currency} z jej dnia.",
        "Pominięto {count} płatności: brak kursów {currency} z ich dni.",
        "Pominięto {count} płatności: brak kursów {currency} z ich dni.",
    ),
    en=(
        "{count} payment is left out: no exchange rate to {currency} for its day.",
        "{count} payments are left out: no exchange rate to {currency} for their days.",
    ),
    ja="{count}件の支払いは、その日の{currency}への為替レートがないため除外されています。",
)

COUNTERPARTY = Text(pl="Kontrahent", en="Counterparty", ja="取引先")
COUNTERPARTIES = Text(pl="Kontrahenci", en="Counterparties", ja="取引先")
CATEGORY = Text(pl="Kategoria", en="Category", ja="カテゴリ")
CATEGORIES = Text(pl="Kategorie", en="Categories", ja="カテゴリ")
ALL = Text(pl="Wszystkie", en="All", ja="すべて")
OTHER = Text(pl="Inne", en="Other", ja="その他")
UNCATEGORISED = Text(pl="Bez kategorii", en="Uncategorised", ja="未分類")
CLEAR_FILTERS = Text(pl="Wyczyść filtry", en="Clear filters", ja="フィルターをクリア")

PICK_CATEGORY_HINT = Text(
    pl="Wybierz kategorię dla każdej nazwy; obejmie wszystkie jej płatności",
    en="Pick a category for each name; it applies to all their payments",
    ja="名前ごとにカテゴリを選んでください。その名前のすべての支払いに適用されます",
)
CATEGORISE_WITH_AI = Text(
    pl="Przypisz kategorie z AI", en="Categorise with AI", ja="AIでカテゴリを割り当て"
)
AI_NOT_CONFIGURED = Text(
    pl="Dodaj klucz OLLAMA_API_KEY, aby AI przypisywało kategorie.",
    en="Add an OLLAMA_API_KEY to let AI assign categories.",
    ja="AIにカテゴリを割り当てさせるには OLLAMA_API_KEY を設定してください。",
)
AI_ASSIGNED_BADGE = Text(pl="AI", en="AI", ja="AI")
AI_ASSIGNED = Text(pl="Kategorię wybrało AI", en="Category chosen by AI", ja="AIが選んだカテゴリ")
AI_CATEGORISED = Plural(
    pl=(
        "AI przypisało kategorię {count} kontrahentowi.",
        "AI przypisało kategorie {count} kontrahentom.",
        "AI przypisało kategorie {count} kontrahentom.",
    ),
    en=(
        "AI assigned a category to {count} counterparty.",
        "AI assigned categories to {count} counterparties.",
    ),
    ja="AIが{count}件の取引先にカテゴリを割り当てました。",
)
AI_NOTHING_ASSIGNED = Text(
    pl="AI nie znalazło nic do przypisania.",
    en="AI found nothing it could assign.",
    ja="AIが割り当てられるものはありませんでした。",
)
AI_UNAVAILABLE = Text(
    pl="AI jest teraz niedostępne. Spróbuj później.",
    en="AI is unavailable right now. Try again later.",
    ja="現在AIを利用できません。後でもう一度お試しください。",
)
CATEGORY_FOR = Text(pl="Kategoria dla {name}", en="Category for {name}", ja="{name}のカテゴリ")
CATEGORY_NAME_OF = Text(pl="Nazwa kategorii {name}", en="Name of {name}", ja="{name}の名前")
DONE = Text(pl="Gotowe", en="Done", ja="完了")
CANCEL = Text(pl="Anuluj", en="Cancel", ja="キャンセル")
DELETE = Text(pl="Usuń", en="Delete", ja="削除")
DELETE_NAMED = Text(pl="Usuń {name}", en="Delete {name}", ja="{name}を削除")
CONFIRM_DELETE = Text(pl="Usunąć {name}?", en="Delete {name}?", ja="{name}を削除しますか？")
CONFIRM_DELETE_IN_USE = Plural(
    pl=(
        "Usunąć {name}? {count} kontrahent trafi do „Bez kategorii”.",
        "Usunąć {name}? {count} kontrahenci trafią do „Bez kategorii”.",
        "Usunąć {name}? {count} kontrahentów trafi do „Bez kategorii”.",
    ),
    en=(
        "Delete {name}? {count} counterparty will become Uncategorised.",
        "Delete {name}? {count} counterparties will become Uncategorised.",
    ),
    ja="{name}を削除しますか？{count}件の取引先が未分類になります。",
)
CATEGORY_NAME_LENGTH = Text(
    pl="Nazwa kategorii musi mieć od 1 do 40 znaków.",
    en="A category name needs 1 to 40 characters.",
    ja="カテゴリ名は1〜40文字で入力してください。",
)
CATEGORY_EXISTS = Text(
    pl="Kategoria o nazwie {name} już istnieje.",
    en="A category named {name} already exists.",
    ja="「{name}」という名前のカテゴリは既にあります。",
)

BANK_ERRORS = {
    BankErrorCode.ACCESS_DENIED: Text(
        pl="Bank nie udzielił dostępu. Spróbuj połączyć się ponownie.",
        en="The bank did not grant access. Try connecting again.",
        ja="銀行がアクセスを許可しませんでした。もう一度接続してください。",
    ),
    BankErrorCode.INVALID_CALLBACK: Text(
        pl="Bank zwrócił nieoczekiwaną odpowiedź. Spróbuj połączyć się ponownie.",
        en="The bank returned an unexpected response. Try connecting again.",
        ja="銀行から予期しない応答がありました。もう一度接続してください。",
    ),
    BankErrorCode.INVALID_STATE: Text(
        pl="Ten link do połączenia z bankiem jest już nieważny. Rozpocznij nowe połączenie.",
        en="This bank connection link is no longer valid. Start a new connection.",
        ja="この銀行接続リンクは無効になりました。新しく接続を開始してください。",
    ),
    BankErrorCode.BANK_UNAVAILABLE: Text(
        pl="Usługa banku jest teraz niedostępna. Spróbuj później.",
        en="The bank service is unavailable right now. Try again later.",
        ja="銀行サービスは現在利用できません。しばらくしてからお試しください。",
    ),
    BankErrorCode.SESSION_EXPIRED: Text(
        pl="Połączenie z bankiem wygasło. Połącz się ponownie, aby je odświeżyć.",
        en="Your bank connection has expired. Connect again to refresh it.",
        ja="銀行との接続の有効期限が切れました。もう一度接続して更新してください。",
    ),
    BankErrorCode.NOT_CONFIGURED: Text(
        pl="Dostęp do banku nie jest skonfigurowany. Ustaw dane Enable Banking w pliku .env.",
        en="Bank access is not configured. Set the Enable Banking credentials in .env.",
        ja=(
            "銀行アクセスが設定されていません。"
            ".env に Enable Banking の認証情報を設定してください。"
        ),
    ),
}
