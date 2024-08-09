import os

from senfd.documents.base import to_file

CONTENT = "foo bar baz"
FILENAME = "testtofile.txt"


def test_to_file_without_a_path(tmp_path):

    orig = os.getcwd()
    os.chdir(tmp_path)

    path = to_file(CONTENT, FILENAME)
    back = path.read_text()

    os.chdir(orig)
    assert back == CONTENT


def test_to_file_with_a_dirpath(tmp_path):

    path = to_file(CONTENT, FILENAME, tmp_path)
    back = path.read_text()

    assert back == CONTENT


def test_to_file_with_a_filepath(tmp_path):

    path = to_file(CONTENT, FILENAME, tmp_path / FILENAME)
    back = path.read_text()

    assert back == CONTENT
