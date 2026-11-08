from html.parser import HTMLParser
from urllib.request import Request, urlopen


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._in_row = False
        self._in_cell = False
        self._cell_parts = []
        self._row = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._in_row = True
            self._row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._cell_parts = []

    def handle_data(self, data):
        if self._in_cell:
            self._cell_parts.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._row.append("".join(self._cell_parts))
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            self.rows.append(self._row)
            self._in_row = False


def print_grid_from_doc(url: str) -> None:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request) as response:
        html = response.read().decode("utf-8")

    parser = TableParser()
    parser.feed(html)

    points = []
    for row in parser.rows:
        if len(row) < 3:
            continue

        try:
            x = int(row[0].strip())
            y = int(row[2].strip())
        except ValueError:  # Skip the table header
            continue

        character = row[1]
        points.append((x, y, character))

    if not points:
        return

    max_x = max(x for x, _, _ in points)
    max_y = max(y for _, y, _ in points)

    grid = [[" "] * (max_x + 1) for _ in range(max_y + 1)]

    for x, y, character in points:
        grid[y][x] = character

    for y in range(max_y, -1, -1):
        print("".join(grid[y]))
