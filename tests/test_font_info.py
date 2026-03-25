import fitz


def _make_pdf(tmp_path):
    path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world", fontsize=12)
    doc.save(str(path))
    doc.close()
    return str(path)


def _extract_fonts(pdf_path):
    rows = []
    doc = fitz.open(pdf_path)
    try:
        for pg_idx in range(doc.page_count):
            page = doc[pg_idx]
            for item in page.get_fonts(full=True):
                rows.append(
                    {
                        "page": pg_idx + 1,
                        "name": item[3] or item[4] or "(unknown)",
                        "type": item[2],
                        "encoding": item[5] or "",
                        "embedded": bool(item[0] > 0),
                        "subset": bool(item[3] and "+" in item[3]),
                    }
                )
    finally:
        doc.close()
    return rows


def test_extraction_returns_list(tmp_path):
    path = _make_pdf(tmp_path)
    result = _extract_fonts(path)
    assert isinstance(result, list)


def test_rows_have_required_keys(tmp_path):
    path = _make_pdf(tmp_path)
    result = _extract_fonts(path)
    assert len(result) > 0
    required = {"page", "name", "type", "encoding", "embedded", "subset"}
    for row in result:
        assert required.issubset(row.keys()), f"Missing keys in row: {row}"


def test_plain_pdf_returns_at_least_one_font(tmp_path):
    path = _make_pdf(tmp_path)
    result = _extract_fonts(path)
    assert len(result) >= 1


def test_embedded_flag_is_bool(tmp_path):
    path = _make_pdf(tmp_path)
    result = _extract_fonts(path)
    for row in result:
        assert isinstance(row["embedded"], bool), f"embedded is not bool: {row}"


def test_page_number_starts_at_one(tmp_path):
    path = _make_pdf(tmp_path)
    result = _extract_fonts(path)
    assert len(result) > 0
    assert all(row["page"] >= 1 for row in result)
    assert result[0]["page"] == 1
