#Варіант 49. Витрати матеріалів майстерні
#Завдання. Опрацювання реєстру: витрати матеріалів майстерні
from __future__ import annotations

from dataclasses import dataclass
import functools
import inspect
import json
import re
import sys
import time
from typing import Any, Callable
#межи
DATABASE_FILE: str = "lab10_database.json"
MAX_RECORDS: int = 200
ID_MIN: int = 1
ID_MAX: int = 9999
VAL_MIN: int = 0
VAL_MAX: int = 10000
DELTA_MIN: int = -10000
DELTA_MAX: int = 10000

GROUP_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,7}$")
#За умовою
DICTIONARY: dict[str, dict[str, str]] = {
    "groups": {
        "A": "Деревина",
        "B": "Метал",
        "C": "Витратні матеріали",
        "TEAM": "Робоча добірка",
        "CHECK": "На перевірці",
        "NEW": "Нові записи",
    },
    "fields": {
        "id": "Ідентифікатор",
        "group": "Група",
        "a": "Фактично використаний обсяг у цілих одиницях",
        "b": "Дозволений обсяг у тих самих одиницях",
        "s": "Обсяг перевищення дозволеного ліміту",
    },
}

COMMAND_STATUS_MESSAGES: dict[str, str] = {
    "OK": "Команда {i} - виконано.",
    "ДАНІ": "Команда {i} - відхилено. Некоректні дані команди.",
    "ДУБЛЬ": "Команда {i} - відхилено. Запис із таким ідентифікатором уже існує.",
    "НЕМАЄ": "Команда {i} - відхилено. Запис із таким ідентифікатором відсутній.",
    "МЕЖІ": "Команда {i} - відхилено. Порушено допустимі межі запису або реєстру.",
}

#перевірки типів і меж
def _is_strict_int(value: Any) -> bool:
    return type(value) is int


def _is_valid_id(value: Any) -> bool:
    return _is_strict_int(value) and ID_MIN <= value <= ID_MAX


def _is_valid_group(value: Any) -> bool:
    return type(value) is str and bool(GROUP_PATTERN.fullmatch(value))


def _is_valid_ab(value: Any) -> bool:
    return _is_strict_int(value) and VAL_MIN <= value <= VAL_MAX


def _is_valid_delta(value: Any) -> bool:
    return _is_strict_int(value) and DELTA_MIN <= value <= DELTA_MAX


def _reject_non_standard_json_constants(constant: str) -> Any:
    raise ValueError(f"Недопустима константа JSON: {constant}")


def _parse_strict_json(raw_text: str) -> Any:
    return json.loads(raw_text, parse_constant=_reject_non_standard_json_constants)

#Перевищення
def _metric_s(record: Record) -> int:
    diff = record.a - record.b
    return diff if diff > 0 else 0


def _format_group(code: str, dictionary: dict) -> str:
    groups_map = dictionary.get("groups", {})
    if isinstance(groups_map, dict) and code in groups_map:
        return f"{code} ({groups_map[code]})"
    return code

#Вигляд запису
@dataclass
class Record:
    id: int
    group: str
    a: int
    b: int


def _validate_record_instance(rec: Any) -> Record:
    if not isinstance(rec, Record):
        raise ValueError("ДАНІ")
    if not (
        _is_valid_id(rec.id)
        and _is_valid_group(rec.group)
        and _is_valid_ab(rec.a)
        and _is_valid_ab(rec.b)
    ):
        raise ValueError("ДАНІ")
    return Record(id=rec.id, group=rec.group, a=rec.a, b=rec.b)


def _parse_record_dict(obj: Any) -> Record:
    if type(obj) is not dict:
        raise ValueError("ДАНІ")
    if set(obj.keys()) != {"id", "group", "a", "b"}:
        raise ValueError("ДАНІ")
    rec_id = obj["id"]
    group = obj["group"]
    a = obj["a"]
    b = obj["b"]
    if not (
        _is_valid_id(rec_id)
        and _is_valid_group(group)
        and _is_valid_ab(a)
        and _is_valid_ab(b)
    ):
        raise ValueError("ДАНІ")
    return Record(id=rec_id, group=group, a=a, b=b)

#Реєстр записів
class Registry:
    def __init__(self, records: list[Record]) -> None:
        if type(records) is not list or len(records) > MAX_RECORDS:
            raise ValueError("ДАНІ")
        copied: list[Record] = []
        seen_ids: set[int] = set()
        for item in records:
            rec = _validate_record_instance(item)
            if rec.id in seen_ids:
                raise ValueError("ДАНІ")
            seen_ids.add(rec.id)
            copied.append(rec)
        self.records: list[Record] = copied

    def snapshot(self) -> list[Record]:
        return [
            Record(id=rec.id, group=rec.group, a=rec.a, b=rec.b)
            for rec in self.records
        ]

#Читання та запис бази даних у JSON
def load_registry(path: str) -> Registry:
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
    if content.strip() == "":
        raise json.JSONDecodeError("Порожній файл JSON", content, 0)
    try:
        data = _parse_strict_json(content)
    except ValueError as exc:
        if isinstance(exc, json.JSONDecodeError):
            raise
        raise json.JSONDecodeError(str(exc), content, 0) from exc

    if type(data) is not list:
        raise ValueError("ДАНІ")

    records = [_parse_record_dict(item) for item in data]
    return Registry(records)


def save_registry(registry: Registry, path: str) -> None:
    ordered = sorted(registry.snapshot(), key=lambda r: r.id)
    payload = [
        {"id": r.id, "group": r.group, "a": r.a, "b": r.b}
        for r in ordered
    ]
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

#Пошук записів за ідентифікатором
def linear_search(records: list[Record], q: int) -> Record | None:
    for rec in records:
        if rec.id == q:
            return rec
    return None


def binary_search(records: list[Record], q: int) -> Record | None:
    left = 0
    right = len(records) - 1
    while left <= right:
        mid = (left + right) // 2
        mid_id = records[mid].id
        if mid_id == q:
            return records[mid]
        if mid_id < q:
            left = mid + 1
        else:
            right = mid - 1
    return None

#Перевірка узгодженості
def analyze(
    registry: Registry,
    group: str,
    threshold: int,
    search_id: int,
    dictionary: dict,
) -> list[str]:

    current = registry.snapshot()
    sorted_records = sorted(current, key=lambda r: r.id)

    lin_found = linear_search(current, search_id)
    bin_found = binary_search(sorted_records, search_id)

    if (lin_found is None) != (bin_found is None) or (
        lin_found is not None and bin_found is not None and lin_found != bin_found
    ):
        raise RuntimeError("Розбіжність між лінійним і бінарним пошуком.")

    fields = dictionary.get("fields", {})
    label_id = fields.get("id", "id")
    label_group = fields.get("group", "group")
    label_a = fields.get("a", "a")
    label_b = fields.get("b", "b")
    label_s = fields.get("s", "s")

    lines: list[str] = []

    if bin_found is not None:
        s_val = _metric_s(bin_found)
        grp_str = _format_group(bin_found.group, dictionary)
        lines.append(
            f"Знайдений запис. {label_id} - {bin_found.id}. "
            f"{label_group} - {grp_str}. "
            f"{label_a} - {bin_found.a}. "
            f"{label_b} - {bin_found.b}. "
            f"{label_s} - {s_val}."
        )
    else:
        lines.append("Запис із заданим ідентифікатором не знайдено.")

    selected = [
        rec
        for rec in current
        if (group == "*" or rec.group == group) and _metric_s(rec) == threshold
    ]
    selected.sort(key=lambda r: (_metric_s(r), r.group, r.id))

    if selected:
        ids_part = ", ".join(f"№{rec.id}" for rec in selected)
        lines.append(f"Відібрані записи - {ids_part}.")
        total_s = sum(_metric_s(rec) for rec in selected)
        lines.append(f"Сума показників «{label_s}» - {total_s}.")

        by_group: dict[str, list[int]] = {}
        for rec in selected:
            by_group.setdefault(rec.group, []).append(_metric_s(rec))

        for grp_code in sorted(by_group.keys()):
            values = by_group[grp_code]
            grp_title = _format_group(grp_code, dictionary)
            lines.append(
                f"Група {grp_title}. Записів - {len(values)}. "
                f"Сума показників - {sum(values)}. "
                f"Найбільший показник - {max(values)}."
            )
    else:
        lines.append("За умовою відбору записів немає.")
        lines.append("Сума показників відібраних записів - 0.")
        lines.append("Підсумків за групами немає.")

    return lines

#Розбір і виконання команд за уомовю ADD ADJUST MOVE DELETE
def _raw_apply_command(registry: Registry, raw: str) -> str:

    if type(raw) is not str:
        raise ValueError("ДАНІ")
    try:
        cmd = _parse_strict_json(raw)
    except ValueError as exc:
        raise ValueError("ДАНІ") from exc

    if type(cmd) is not dict or "op" not in cmd or type(cmd["op"]) is not str:
        raise ValueError("ДАНІ")

    op = cmd["op"]

    if op == "ADD":
        if set(cmd.keys()) != {"op", "record"}:
            raise ValueError("ДАНІ")
        new_rec = _parse_record_dict(cmd["record"])
        for existing in registry.records:
            if existing.id == new_rec.id:
                raise ValueError("ДУБЛЬ")
        if len(registry.records) >= MAX_RECORDS:
            raise ValueError("МЕЖІ")
        registry.records.append(new_rec)
        return "OK"

    if op == "ADJUST":
        if set(cmd.keys()) != {"op", "id", "da", "db"}:
            raise ValueError("ДАНІ")
        rec_id = cmd["id"]
        da = cmd["da"]
        db = cmd["db"]
        if not (_is_valid_id(rec_id) and _is_valid_delta(da) and _is_valid_delta(db)):
            raise ValueError("ДАНІ")
        target = linear_search(registry.records, rec_id)
        if target is None:
            raise ValueError("НЕМАЄ")
        new_a = target.a + da
        new_b = target.b + db
        if not (_is_valid_ab(new_a) and _is_valid_ab(new_b)):
            raise ValueError("МЕЖІ")
        target.a = new_a
        target.b = new_b
        return "OK"

    if op == "MOVE":
        if set(cmd.keys()) != {"op", "id", "group"}:
            raise ValueError("ДАНІ")
        rec_id = cmd["id"]
        new_group = cmd["group"]
        if not (_is_valid_id(rec_id) and _is_valid_group(new_group)):
            raise ValueError("ДАНІ")
        target = linear_search(registry.records, rec_id)
        if target is None:
            raise ValueError("НЕМАЄ")
        target.group = new_group
        return "OK"

    if op == "DELETE":
        if set(cmd.keys()) != {"op", "id"}:
            raise ValueError("ДАНІ")
        rec_id = cmd["id"]
        if not _is_valid_id(rec_id):
            raise ValueError("ДАНІ")
        for idx, existing in enumerate(registry.records):
            if existing.id == rec_id:
                registry.records.pop(idx)
                return "OK"
        raise ValueError("НЕМАЄ")

    raise ValueError("ДАНІ")

#Створює декоратор вимірювання часу
def timed(
    label: str,
    log: list,
    clock: Callable[[], float] = time.perf_counter,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = clock()
            try:
                result = func(*args, **kwargs)
            except BaseException:
                elapsed = max(0.0, float(clock() - start))
                log.append((label, False, elapsed))
                raise
            else:
                elapsed = max(0.0, float(clock() - start))
                log.append((label, True, elapsed))
                return result

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return decorator


journal: list[tuple[str, bool, float]] = []
apply_command = timed("change", journal)(_raw_apply_command)

# Перевірка збереженних даних
def check_metadata(original: Callable[..., Any], wrapped: Callable[..., Any]) -> bool:
    if getattr(wrapped, "__wrapped__", None) is not original:
        return False
    if getattr(original, "__name__", None) != getattr(wrapped, "__name__", None):
        return False
    if getattr(original, "__doc__", None) != getattr(wrapped, "__doc__", None):
        return False
    if getattr(original, "__annotations__", None) != getattr(
        wrapped, "__annotations__", None
    ):
        return False
    try:
        orig_sig = inspect.signature(original)
        wrap_sig = inspect.signature(wrapped)
    except (TypeError, ValueError):
        return False
    return orig_sig == wrap_sig


def check_call(
    original: Callable[..., Any],
    wrapped: Callable[..., Any],
    before: Registry,
    after: Registry,
    args: tuple,
    observed: tuple,
) -> bool:
    if not check_metadata(original, wrapped):
        return False
    if type(observed) is not tuple or len(observed) != 2:
        return False

    reg_copy = Registry(before.snapshot())
    try:
        expected_res = original(reg_copy, *args)
    except Exception as exc:
        expected_outcome: tuple[bool, Any] = (False, (type(exc), str(exc)))
    else:
        expected_outcome = (True, expected_res)

    if observed != expected_outcome:
        return False

    return reg_copy.records == after.records


def _is_valid_journal_entry(entry: Any, expected_label: str, expected_success: bool) -> bool:
    if type(entry) is not tuple or len(entry) != 3:
        return False
    lbl, ok, elapsed = entry
    if lbl != expected_label:
        return False
    if type(ok) is not bool or ok != expected_success:
        return False
    if type(elapsed) not in (int, float) or elapsed < 0:
        return False
    return True


def format_report(
    status: str = "FORMAT_ERROR",
    func_name: str = "evaluate",
    calls: int = 0,
    saved: str = "-",
    json_status: str = "-",
) -> str:
    lines = [
        "",
        f"Статус: {status}",
        f"Функція: {func_name}",
        f"Виклики: {calls}",
        f"Збережено: {saved}",
        f"JSON: {json_status}",
    ]
    return "\n".join(lines)


def _read_stdin_lines(count: int) -> list[str]:
    result: list[str] = []
    for _ in range(count):
        line = sys.stdin.readline()
        if line == "":
            break
        result.append(line.rstrip("\r\n"))
    return result

#Виконання всіх команд
def main() -> None:
    lines = _read_stdin_lines(4)
    if len(lines) < 4:
        sys.stdout.write(format_report() + "\n")
        sys.stdout.flush()
        return

    ops_filename = lines[0].strip()
    filter_group = lines[1].strip()
    filter_threshold = int(lines[2].strip())
    search_id = int(lines[3].strip())

    #Починаємо вивід результату з нового рядка після введеного значення
    sys.stdout.write("\n")
    sys.stdout.flush()

    journal.clear()

    try:
        registry = load_registry(DATABASE_FILE)
    except FileNotFoundError:
        print("Помилка. Файл бази відсутній.")
        return
    except json.JSONDecodeError:
        print("Помилка. Файл бази містить некоректний JSON.")
        return
    except ValueError:
        print("Помилка. База містить недопустиму структуру або записи.")
        return

    commands: list[str] = []
    with open(ops_filename, "r", encoding="utf-8") as ops_file:
        for raw_line in ops_file:
            commands.append(raw_line.rstrip("\r\n"))

    original_func = getattr(apply_command, "__wrapped__", _raw_apply_command)
    all_calls_valid = True
    valid_journal_entries = 0

    for idx, raw_cmd in enumerate(commands, start=1):
        before_reg = Registry(registry.snapshot())
        journal_len_before = len(journal)

        try:
            res = apply_command(registry, raw_cmd)
        except ValueError as exc:
            code = str(exc)
            observed: tuple[bool, Any] = (False, (type(exc), code))
            expected_success = False
            status_line = COMMAND_STATUS_MESSAGES.get(
                code, COMMAND_STATUS_MESSAGES["ДАНІ"]
            ).format(i=idx)
        else:
            observed = (True, res)
            expected_success = True
            status_line = COMMAND_STATUS_MESSAGES["OK"].format(i=idx)

        print(status_line)

        if len(journal) == journal_len_before + 1 and _is_valid_journal_entry(
            journal[-1], "change", expected_success
        ):
            valid_journal_entries += 1

        if not check_call(
            original_func,
            apply_command,
            before_reg,
            registry,
            (raw_cmd,),
            observed,
        ):
            all_calls_valid = False

    print(f"У реєстрі записів - {len(registry.records)}.")

    analysis_lines = analyze(
        registry,
        filter_group,
        filter_threshold,
        search_id,
        DICTIONARY,
    )
    for line in analysis_lines:
        print(line)

    calls_count = len(commands)
    if calls_count > 0:
        verdict = (
            "Метадані й поведінку збережено."
            if (all_calls_valid and valid_journal_entries == calls_count)
            else "Метадані або поведінка змінилися."
        )
    else:
        verdict = (
            "Метадані збережено."
            if check_metadata(original_func, apply_command)
            else "Метадані змінилися."
        )

    print(
        f"Перевірка декоратора. Викликів - {calls_count}. "
        f"Коректних записів журналу - {valid_journal_entries}. {verdict}"
    )

    save_registry(registry, DATABASE_FILE)


if __name__ == "__main__":
    main()