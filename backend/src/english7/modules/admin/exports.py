import csv
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def conversation_csv(conversation: dict) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["STT", "Thời gian", "Học viên", "AI Tutor", "Ngôn ngữ"])
    for item in conversation["exchanges"]:
        writer.writerow(
            [
                item["sequence_number"],
                item["created_at"].isoformat(),
                item["question"],
                item["answer"],
                item["language"],
            ]
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def conversation_docx(conversation: dict) -> bytes:
    paragraphs = [
        f"Hội thoại: {conversation['title']}",
        f"Học viên: {conversation['student_name'] or conversation['student_email']}",
    ]
    for item in conversation["exchanges"]:
        paragraphs.extend(
            [
                f"Học viên: {item['question']}",
                f"AI Tutor: {item['answer']}",
            ]
        )
    return _docx(paragraphs)


def _docx(paragraphs: list[str]) -> bytes:
    document = "".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
        for text in paragraphs
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
            f"<w:body>{document}<w:sectPr/></w:body></w:document>",
        )
    return buffer.getvalue()


def student_chat_csv(history: dict) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["STT", "Thời gian", "Học viên", "AI Tutor", "Ngôn ngữ"])
    for index, item in enumerate(history["exchanges"], start=1):
        writer.writerow(
            [
                index,
                item["created_at"].isoformat(),
                item["question"],
                item["answer"],
                item["language"],
            ]
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def student_chat_xlsx(history: dict) -> bytes:
    csv_rows = student_chat_csv(history)[3:].decode("utf-8").splitlines()
    return _xlsx(list(csv.reader(csv_rows)), "Lich su AI Tutor")


def student_chat_docx(history: dict) -> bytes:
    paragraphs = [
        "Lịch sử AI Tutor",
        f"Học viên: {history['student_name'] or history['student_email']}",
    ]
    for item in history["exchanges"]:
        timestamp = item["created_at"].isoformat()
        paragraphs.extend(
            [
                f"{timestamp} - Học viên: {item['question']}",
                f"{timestamp} - AI Tutor: {item['answer']}",
            ]
        )
    return _docx(paragraphs)


def student_progress_csv(students: list[dict]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "Họ tên",
            "Email",
            "Trường",
            "Lớp",
            "Bài kiểm tra",
            "Số câu đúng",
            "Tổng số câu",
            "Tỉ lệ đúng (%)",
            "Thẻ đã ôn",
            "Thẻ đến hạn",
            "Thẻ khó",
            "Lượt luyện nói",
        ]
    )
    for item in students:
        writer.writerow(
            [
                item.get("full_name") or "",
                item["email"],
                item.get("school_name") or "",
                item.get("class_name") or "",
                item["completed_quizzes"],
                item["correct_answers"],
                item["total_questions"],
                item["accuracy_percent"],
                item["reviewed_cards"],
                item["due_cards"],
                item["difficult_cards"],
                item["speaking_count"],
            ]
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def student_progress_xlsx(students: list[dict]) -> bytes:
    csv_rows = student_progress_csv(students)[3:].decode("utf-8").splitlines()
    rows = list(csv.reader(csv_rows))
    return _xlsx(rows, "Tien do hoc vien")


def _xlsx(rows: list[list[str]], sheet_name: str) -> bytes:
    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{_column_name(column)}{row_number}" t="inlineStr">'
            f"<is><t>{escape(str(value))}</t></is></c>"
            for column, value in enumerate(row, start=1)
        )
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>'
            "</sheets></workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
            f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>",
        )
    return buffer.getvalue()


def _column_name(number: int) -> str:
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name
