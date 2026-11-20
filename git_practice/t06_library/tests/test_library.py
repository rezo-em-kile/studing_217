import pytest

from library import FINE_PER_DAY, Library, LibraryError, load_catalog, main


@pytest.fixture
def lib():
    library = Library()
    library.add_book("111", "Гарри Поттер и философский камень", 2)
    library.add_book("222", "Мастер и Маргарита")
    library.add_book("333", "Война и мир", 3)
    return library


def test_add_book_and_title(lib):
    assert lib.title("222") == "Мастер и Маргарита"
    assert lib.available("111") == 2


def test_add_more_copies(lib):
    lib.add_book("222", "Мастер и Маргарита", 2)
    assert lib.available("222") == 3


def test_add_book_errors(lib):
    with pytest.raises(LibraryError):
        lib.add_book("444", "Идиот", 0)
    with pytest.raises(LibraryError):
        lib.add_book("222", "Другая книга")


def test_unknown_book(lib):
    with pytest.raises(LibraryError):
        lib.available("999")
    with pytest.raises(LibraryError):
        lib.borrow("999", "Иванов", 1)


def test_find_lowercase_query(lib):
    assert lib.find("гарри") == ["111"]


def test_find_ignores_case(lib):
    assert lib.find("Гарри") == ["111"]
    assert lib.find("  МАСТЕР ") == ["222"]


def test_find_several_and_none(lib):
    assert lib.find(" и ") == ["111", "222", "333"]
    assert lib.find("Тургенев") == []


def test_borrow_reduces_available(lib):
    lib.borrow("111", "Иванов", 1)
    assert lib.available("111") == 1
    assert lib.loans_of("Иванов") == ["111"]


def test_borrow_same_book_twice(lib):
    lib.borrow("111", "Иванов", 1)
    with pytest.raises(LibraryError):
        lib.borrow("111", "Иванов", 2)


def test_cannot_borrow_more_than_copies(lib):
    lib.borrow("222", "Иванов", 1)
    with pytest.raises(LibraryError):
        lib.borrow("222", "Петрова", 2)
    assert lib.available("222") == 0


def test_return_in_time(lib):
    lib.borrow("333", "Иванов", 10)
    assert lib.return_book("333", "Иванов", 12) == 0
    assert lib.available("333") == 3
    assert lib.loans_of("Иванов") == []


def test_return_on_last_day_has_no_fine(lib):
    lib.borrow("333", "Иванов", 1)
    assert lib.return_book("333", "Иванов", 15) == 0


def test_fine_for_each_overdue_day(lib):
    lib.borrow("333", "Иванов", 1)
    lib.borrow("333", "Петрова", 1)
    assert lib.return_book("333", "Иванов", 18) >= 3 * FINE_PER_DAY
    assert lib.return_book("333", "Петрова", 30) > 0


def test_return_errors(lib):
    with pytest.raises(LibraryError):
        lib.return_book("333", "Иванов", 5)
    lib.borrow("333", "Иванов", 5)
    with pytest.raises(LibraryError):
        lib.return_book("333", "Иванов", 4)


def test_loans_of_sorted(lib):
    lib.borrow("333", "Иванов", 1)
    lib.borrow("111", "Иванов", 2)
    lib.borrow("222", "Петрова", 2)
    assert lib.loans_of("Иванов") == ["111", "333"]


def test_load_catalog():
    library = load_catalog(["111; Война и мир; 2\n", "\n", "222; Мастер и Маргарита; 1\n"])
    assert library.available("111") == 2
    with pytest.raises(LibraryError):
        load_catalog(["111; Война и мир\n"])


def test_main(tmp_path, capsys):
    path = tmp_path / "catalog.txt"
    path.write_text("222; Мастер и Маргарита; 1\n111; Война и мир; 2\n", encoding="utf-8")
    assert main([str(path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["111  Война и мир - свободно: 2",
                                                    "222  Мастер и Маргарита - свободно: 1"]
    assert main([]) == 2
    assert main([str(tmp_path / "нет.txt")]) == 1
